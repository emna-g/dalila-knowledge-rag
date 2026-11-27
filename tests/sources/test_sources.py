"""Tests du module sources, sans Internet ni base : un petit serveur web local joue le rôle des sites officiels.

python -m tests.sources.test_sources      (ou : python -m pytest tests/sources)
"""
import http.server, json, tempfile, threading, pathlib
from dalila.sources import lire as lecteur
from dalila.sources.appliquer import appliquer, en_attente
from dalila.sources.base import lignes as lignes_base
from dalila.sources.decoupage import decouper, langue
from dalila.sources.empreinte import empreinte_octets, empreinte_texte
from dalila.sources.inventaire import nouvelles_lignes, plus_citees, urls_corpus, urls_reference
from dalila.sources.rafraichir import Etat, executer, rapport, valider

PAGE = ("<html><head><title>AFI</title><script>var x='ignore'</script></head><body><nav>Accueil | Contact</nav>"
        "<h1>Nos services</h1><p>Acquisition d'un lot : {prix} DT.</p>"
        "<p>La demande d'acquisition est adressée au bureau d'ordre central de l'AFI avec les pièces du dossier.</p>"
        "<footer>© 2026</footer></body></html>")


def pdf_texte(phrase):
    """Un vrai petit PDF avec une ligne de texte (pour tester l'extraction sans fichier externe)."""
    flux = f"BT /F1 12 Tf 20 100 Td ({phrase}) Tj ET".encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(flux) + flux + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, pos = b"%PDF-1.4\n", []
    for i, o in enumerate(objs):
        pos.append(len(out))
        out += b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o for o in pos)
    out += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % x
    return out.decode("latin-1")


CONTENU = {  # chemin -> (code, type, corps) ; modifiable pendant les tests
    "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /interdit/\n"),
    "/services": (200, "text/html; charset=utf-8", PAGE.format(prix=50)),
    "/cahier.pdf": (200, "application/pdf", "%PDF-1.4 contenu"),
    "/captcha": (403, "text/html", "<html><body><div class='g-recaptcha'>Vérifiez que vous êtes humain</div></body></html>"),
    "/formulaire": (200, "text/html", "<html><body><script src='recaptcha/api.js'></script><p>" + "Texte utile. " * 200
                    + "</p><div class='g-recaptcha'></div></body></html>"),
    "/interdit/page": (200, "text/html", "<p>secret</p>"),
    "/contact": (200, "text/html", "<html><body>" + "<p>Rubrique du menu</p>" * 70 + "<form><img src='captcha.asp'>"
                 "<input name='code'></form></body></html>"),       # comme la page Contact de l'APII : pas un mur
    "/mur": (200, "text/html", "<html><body><div class='cf-challenge'>Checking your browser before accessing."
             "</div></body></html>"),
    "/ailleurs": (302, "text/html", ""),
    "/texte.pdf": (200, "application/pdf", pdf_texte("Prix du lot : 50 DT le metre carre dans la zone industrielle de Sfax")),
    "/elementor": (200, "text/html", "<html><body><div class='elementor elementor-location-header'><div>Menu</div>"
                   "<div>Accueil</div></div><div><p>Contenu de la page</p></div>"
                   "<div class='elementor-location-footer'>Plan du site</div></body></html>"),
}


class Site(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code, typ, corps = CONTENU.get(self.path, (404, "text/html", "introuvable"))
        if self.path == "/cahier.pdf" and self.headers.get("If-None-Match") == '"v1"':
            self.send_response(304)
            self.end_headers()
            return
        self.send_response(code)
        self.send_header("Content-Type", typ)
        if self.path == "/cahier.pdf":
            self.send_header("ETag", '"v1"')
        if code == 302:  # vers un autre « site » (localhost au lieu de 127.0.0.1)
            self.send_header("Location", f"http://localhost:{PORT}/services")
        self.end_headers()
        self.wfile.write(corps.encode("latin-1") if typ == "application/pdf" else corps.encode("utf-8"))

    def log_message(self, *a):
        pass


serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
PORT = serveur.server_address[1]
threading.Thread(target=serveur.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}"
lecteur.PAUSE_S = 0


def src(chemin, organisme="AFI"):
    return {"url": BASE + chemin, "organisme": organisme, "delai_jours": "7"}


def test_empreinte_ignore_la_mise_en_forme():
    assert empreinte_texte("Zone  industrielle\n de Sfax ") == empreinte_texte("Zone industrielle de Sfax")
    assert empreinte_texte("prix 50 DT") != empreinte_texte("prix 60 DT")


def test_texte_sans_menus_ni_scripts():
    t = lecteur.texte_html(PAGE.format(prix=50))
    assert "Nos services" in t and "50 DT" in t
    assert "Accueil" not in t and "ignore" not in t and "2026" not in t


def test_lecture_page_pdf_et_echecs():
    lecteur.oublier_sites()
    l = lecteur.lire(BASE + "/services")
    assert l.ok and l.type == "page" and "50 DT" in l.texte
    p = lecteur.lire(BASE + "/cahier.pdf")
    assert p.ok and p.type == "pdf" and p.etag == '"v1"'
    assert p.empreinte == empreinte_octets("%PDF-1.4 contenu".encode())       # lu par morceaux = même empreinte
    assert lecteur.lire(BASE + "/cahier.pdf", etag='"v1"').non_modifie        # 304 : pas retéléchargé
    assert lecteur.lire(BASE + "/absente").statut_http == 404
    assert lecteur.lire(BASE + "/interdit/page").interdit_robots                # robots.txt respecté
    assert "redirection hors de la liste" in lecteur.lire(BASE + "/ailleurs").erreur
    assert lecteur.lire(BASE + "/formulaire").ok                                # reCAPTCHA d'un formulaire : pas un mur
    assert lecteur.lire(BASE + "/contact").ok                                   # page courte avec CAPTCHA de formulaire
    lecteur.oublier_sites()
    try:
        lecteur.lire(BASE + "/mur")
        assert False, "une page de vérification anti-robot doit arrêter la lecture"
    except lecteur.Captcha:
        pass
    lecteur.oublier_sites()
    try:
        lecteur.lire(BASE + "/captcha")
        assert False, "le CAPTCHA doit arrêter la lecture"
    except lecteur.Captcha:
        pass


def test_url_arabe_et_espaces():
    u = lecteur.vers_uri("https://www.afi.nat.tn/تشجيعات-و-حوافز/cahier des charges.pdf")
    assert u.isascii() and " " not in u and u.startswith("https://www.afi.nat.tn/%D8")


def test_cycle_complet():
    lecteur.oublier_sites()
    with tempfile.TemporaryDirectory() as d:
        etat = Etat(pathlib.Path(d))
        sources = [src("/services"), src("/cahier.pdf"), src("/absente")]
        r = {s["url"][len(BASE):]: v for s, v, _ in executer(sources, etat, "2026-11-27 10:00:00")}
        assert r == {"/services": "nouvelle", "/cahier.pdf": "nouvelle", "/absente": "disparue"}
        etat.enregistrer()

        # 3 jours plus tard : rien n'est dû ; avec tout=True : inchangé
        r = {s["url"][len(BASE):]: v for s, v, _ in executer(sources, Etat(pathlib.Path(d)), "2026-11-30 10:00:00")}
        assert set(r.values()) == {"pas_due"}

        # une semaine plus tard, le prix a changé sur la page
        CONTENU["/services"] = (200, "text/html; charset=utf-8", PAGE.format(prix=60))
        etat = Etat(pathlib.Path(d))
        res = executer(sources, etat, "2026-12-04 10:00:00")
        r = {s["url"][len(BASE):]: v for s, v, _ in res}
        assert r["/services"] == "changee" and r["/cahier.pdf"] == "inchangee"
        diff = next(x for s, v, x in res if v == "changee")
        assert "-Acquisition d'un lot : 50 DT." in diff and "+Acquisition d'un lot : 60 DT." in diff
        e = etat.de(BASE + "/services")
        assert e["a_relire"] and e["empreinte_validee"] != e["empreinte_lue"]   # l'ancienne version reste validée
        assert etat.de(BASE + "/absente")["echecs_consecutifs"] == 2
        texte = rapport(res, etat, "2026-12-04 10:00:00", True)
        assert "Changées : à relire" in texte and "À relire depuis le 2026-12-04" in texte

        # relu et validé : n'est plus à relire
        valider(etat, BASE + "/services")
        assert not etat.de(BASE + "/services")["a_relire"]
        assert "60 DT" in etat.texte(BASE + "/services", "valide")
        CONTENU["/services"] = (200, "text/html; charset=utf-8", PAGE.format(prix=50))


def test_reprise_apres_arret():
    lecteur.oublier_sites()
    with tempfile.TemporaryDirectory() as d:
        etat = Etat(pathlib.Path(d))
        executer([src("/services"), src("/cahier.pdf")], etat, "2026-11-27 10:00:00", sauver_tous=1)
        repris = Etat(pathlib.Path(d))                     # comme après un arrêt de l'ordinateur
        assert set(repris.sources) == {BASE + "/services", BASE + "/cahier.pdf"}
        res = executer([src("/services"), src("/cahier.pdf")], repris, "2026-11-27 11:00:00")
        assert [v for _, v, _ in res] == ["pas_due", "pas_due"]


def test_captcha_arrete_le_site():
    lecteur.oublier_sites()
    with tempfile.TemporaryDirectory() as d:
        res = executer([src("/captcha"), src("/services")], Etat(pathlib.Path(d)), "2026-11-27 10:00:00")
        assert [v for _, v, _ in res] == ["captcha", "non_lue"]


def test_inventaire():
    trouvees = urls_reference()
    assert any("nos-services" in u for u in trouvees)
    assert any(" " in u for u in trouvees)                                     # nom de PDF avec espaces gardé entier
    lignes = nouvelles_lignes([], {"https://carte.afi.nat.tn/zone/1": {"x"}, "https://www.tia.gov.tn/a": {"x"}})
    assert {(l["organisme"], l["actif"]) for l in lignes} == {("AFI", 0), ("TIA", 1)}
    liste = [{"url": "https://a/ancien", "actif": "1", "utilise_par": "db/reference/x.csv"},
             {"url": "https://a/corpus", "actif": "1", "utilise_par": "corpus"},
             {"url": "https://a/garde", "actif": "1", "utilise_par": "db/reference/x.csv"}]
    assert [r["url"] for r in plus_citees(liste, {"https://a/garde"}, corpus_present=False)] == ["https://a/ancien"]
    assert len(plus_citees(liste, {"https://a/garde"}, corpus_present=True)) == 2
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "passages.jsonl"
        f.write_text('{"source_url": "https://investintunisia.tn/x"}\n{"source_url": ""}\n', encoding="utf-8")
        assert set(urls_corpus(f)) == {"https://investintunisia.tn/x"}


def test_pdf_texte_et_entetes_elementor():
    lecteur.oublier_sites()
    l = lecteur.lire(BASE + "/texte.pdf")
    assert l.ok and l.type == "pdf" and not l.scanne and "=== page 1 ===" in l.texte and "50 DT" in l.texte
    t = lecteur.lire(BASE + "/elementor").texte
    assert t == "Contenu de la page"                                        # en-tête et pied de page retirés
    assert lecteur.decoder(bytes([99, 97, 102, 0xE9, 32, 108, 0x92, 117]), "iso-8859-1") == "café l’u"  # comme un navigateur
    assert lecteur.decoder(b'<meta charset="windows-1252">' + bytes([0xE9])).endswith("é")   # encodage de la page


def test_decoupage_comme_la_fusion():
    texte = "=== page 1 ===" + chr(10) + (chr(10) * 2).join(f"Paragraphe {i} " + "mot " * 60 for i in range(10))
    parts = decouper(texte)
    assert len(parts) > 1 and all(len(t) <= 1400 for _, _, t in parts) and parts[0][0] == 1
    assert langue("المنطقة الصناعية بصفاقس") == "ar" and langue("zone de Sfax") == "fr"


def _corpus(dossier, passages):
    f = dossier / "passages.jsonl"
    f.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in passages), encoding="utf-8")
    return f


def test_appliquer_et_retour_arriere():
    lecteur.oublier_sites()
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        url = BASE + "/services"
        anciens = [{"id": "p000001", "type": "site_officiel", "titre": "AFI : Nos services", "texte": "ancien texte",
                    "source_url": url, "langue": "fr"},
                   {"id": "p000002", "type": "loi", "titre": "Autre", "texte": "autre source", "source_url": "x"}]
        corpus = _corpus(d, anciens)
        etat = Etat(d / "etat")
        executer([src("/services")], etat, "2026-11-27 10:00:00")          # référence
        CONTENU["/services"] = (200, "text/html; charset=utf-8", PAGE.format(prix=70))
        executer([src("/services")], etat, "2026-12-04 10:00:00")          # changée : à relire
        assert en_attente(etat) == []                                       # rien sans relecture
        valider(etat, url)
        assert en_attente(etat) == [url]

        echec = [("étape qui échoue", ["-c", "import sys; sys.exit(1)"])]
        plan, erreur = appliquer(etat, corpus=corpus, etapes=echec)
        assert erreur and "ÉCHEC" in erreur
        assert [json.loads(l)["id"] for l in open(corpus, encoding="utf-8")] == ["p000001", "p000002"]  # remis
        assert en_attente(etat) == [url]                                    # pas marqué appliqué

        ok = [("étape qui réussit", ["-c", "print('ok')"])]
        plan, erreur = appliquer(etat, corpus=corpus, etapes=ok)
        assert erreur is None and plan[0][1] == "remplacer"
        P = [json.loads(l) for l in open(corpus, encoding="utf-8")]
        assert P[-1]["id"] == "p000002"                                     # les autres sources ne bougent pas
        nouveaux = [p for p in P if p["source_url"] == url]
        assert nouveaux and all(p["id"].startswith("s") and len(p["id"]) == 12 for p in nouveaux)
        assert "70 DT" in nouveaux[0]["texte"] and nouveaux[0]["titre"] == "AFI : Nos services"
        assert nouveaux[0]["langue"] == "fr" and not nouveaux[0]["texte_ocr"]
        assert nouveaux[0]["date_source"] == etat.de(url)["applique_le"][:10]
        assert en_attente(etat) == []
        assert len(list((d / "sauvegardes").glob("*.jsonl"))) == 2          # corpus d'avant gardé à chaque fois
        CONTENU["/services"] = (200, "text/html; charset=utf-8", PAGE.format(prix=50))


def test_texte_trop_court_ne_supprime_rien():
    from dalila.sources.appliquer import preparer
    with tempfile.TemporaryDirectory() as d:
        etat = Etat(pathlib.Path(d))
        etat.sources = {"u": {"empreinte_validee": "b", "empreinte_appliquee": "a", "a_relire": False}}
        etat.ecrire_texte("u", "valide", "Menu")
        anciens = [{"id": "p1", "texte": "texte", "source_url": "u"}]
        nouveau, plan = preparer(etat, anciens, "2026-12-04 10:00:00")
        assert nouveau == anciens and plan[0][1] == "attente"


def test_lignes_agent_source_status():
    etat = Etat(pathlib.Path(tempfile.gettempdir()) / "dalila_test_inexistant")
    etat.sources = {"https://a": {"derniere_lecture_ok": "2026-11-27 10:00:00", "empreinte_lue": "h",
                                  "echecs_consecutifs": 0, "derniere_erreur": "ancienne"},
                    "https://b": {"echecs_consecutifs": 2, "derniere_erreur": "HTTP 500",
                                  "derniere_erreur_le": "2026-11-27 10:00:00"}}
    assert list(lignes_base(etat)) == [("https://a", "2026-11-27 10:00:00", None, None, "h"),
                                       ("https://b", None, "HTTP 500", "2026-11-27 10:00:00", None)]


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
