"""Relit les sources de la liste fermée (config_sources.csv) et dit ce qui a changé depuis la dernière lecture.

python -m dalila.sources.rafraichir                   lit les sources dues, montre les changements (état non modifié)
python -m dalila.sources.rafraichir --enregistrer     … et enregistre le nouvel état
python -m dalila.sources.rafraichir --tout            ignore le délai (relit tout)
python -m dalila.sources.rafraichir --organisme FIPA --limite 5
python -m dalila.sources.rafraichir --valider URL     le changement d'une source a été relu : il devient la version validée

Pour chaque source (docs/decisions.md, « Fraîcheur des données ») :
  - empreinte inchangée (ou réponse 304 du site) : seule la date de lecture avance ;
  - empreinte changée : la source passe « à relire » ; la version validée reste celle que Dalila utilise ;
  - échec de lecture : la dernière version reste utilisée, l'échec est compté ; alerte après ECHECS_ALERTE échecs
    de suite ou si la page a disparu (404, 410) ;
  - CAPTCHA : arrêt de la lecture de ce site pour ce passage (jamais contourné) ; robots.txt respecté.
Le texte d'une page est une donnée : il est comparé, jamais exécuté ni interprété.

État (hors git, comme les données) : donnees/sources/etat.json, textes des pages dans donnees/sources/textes/,
rapports dans donnees/sources/rapports/. Étape suivante (pas encore faite) : recopier cet état dans la table
agent_source_status et découper les textes validés en passages (charger, vectoriser, construire_abox, tests).
"""
import argparse, collections, datetime as dt, difflib, hashlib, json, sys
from dalila.config import DONNEES
from dalila.sources import lire as lecteur
from dalila.sources.inventaire import CONFIG, sources_actives

DOSSIER = DONNEES / "sources"
ECHECS_ALERTE = 3


def maintenant():
    return dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def cle(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


class Etat:
    """L'état de chaque source, dans un fichier JSON (et les textes des pages à côté)."""

    def __init__(self, dossier=DOSSIER):
        self.dossier = dossier
        self.fichier = dossier / "etat.json"
        self.sources = json.loads(self.fichier.read_text(encoding="utf-8")) if self.fichier.exists() else {}

    def de(self, url):
        return self.sources.get(url, {})

    def texte(self, url, version):  # version : "valide" ou "lu"
        f = self.dossier / "textes" / f"{cle(url)}.{version}.txt"
        return f.read_text(encoding="utf-8") if f.exists() else None

    def ecrire_texte(self, url, version, texte):
        (self.dossier / "textes").mkdir(parents=True, exist_ok=True)
        (self.dossier / "textes" / f"{cle(url)}.{version}.txt").write_text(texte, encoding="utf-8")

    def enregistrer(self):
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.fichier.write_text(json.dumps(self.sources, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def due(etat_source, delai_jours, quand):
    derniere = etat_source.get("derniere_tentative")
    if not derniere:
        return True
    return quand - dt.datetime.fromisoformat(derniere) >= dt.timedelta(days=float(delai_jours or 7))


def traiter(src, etat, quand):
    """Lit une source, met à jour son état (en mémoire) et rend (verdict, détail)."""
    url = src["url"]
    avant = dict(etat.de(url))
    e = etat.sources.setdefault(url, {"organisme": src["organisme"], "premiere_lecture": quand})
    e["derniere_tentative"] = quand
    l = lecteur.lire(url, etag=avant.get("etag"), modifie_le=avant.get("modifie_le"))

    if not l.ok:
        e["echecs_consecutifs"] = avant.get("echecs_consecutifs", 0) + 1
        e["derniere_erreur"], e["derniere_erreur_le"], e["statut_http"] = l.erreur, quand, l.statut_http
        if l.interdit_robots:
            return "interdit_robots", l.erreur
        if l.statut_http in (404, 410):
            return "disparue", l.erreur
        return "echec", l.erreur

    e.update(echecs_consecutifs=0, derniere_lecture_ok=quand, statut_http=l.statut_http)
    if l.non_modifie:
        return ("a_relire" if avant.get("a_relire") else "inchangee"), "réponse 304 du site"
    e.update(type=l.type, taille=l.taille, etag=l.etag, modifie_le=l.modifie_le, empreinte_lue=l.empreinte,
             scanne=l.scanne, utilise_par=src.get("utilise_par", ""))
    if l.texte:
        etat.ecrire_texte(url, "lu", l.texte)
    if not avant.get("empreinte_validee"):
        # première lecture : elle sert de référence ; le corpus en place a été relu lors de la fusion, il est
        # considéré comme à jour pour cette version (empreinte_appliquee)
        e.update(empreinte_validee=l.empreinte, empreinte_appliquee=l.empreinte, a_relire=False)
        if l.texte:
            etat.ecrire_texte(url, "valide", l.texte)
        return "nouvelle", f"{l.type}, {l.taille} octets" + (", scanné (sans texte)" if l.scanne else "")
    if l.empreinte == avant["empreinte_validee"]:
        e["a_relire"] = False
        return "inchangee", ""
    if not avant.get("a_relire"):
        e["change_depuis"] = quand
    e["a_relire"] = True
    if l.texte:
        return "changee", difference(etat.texte(url, "valide"), l.texte)
    return "changee", f"{l.type.upper()} modifié ({avant.get('taille')} -> {l.taille} octets)" +         (" ; PDF scanné : son texte demande un OCR, à relire sur le PDF" if l.scanne else "")


def difference(ancien, nouveau, lignes_max=40):
    if ancien is None:
        return "(ancien texte non gardé)"
    d = list(difflib.unified_diff(ancien.splitlines(), nouveau.splitlines(), "version validée", "version lue",
                                  lineterm="", n=1))
    return "\n".join(d[:lignes_max] + (["… (différence tronquée)"] if len(d) > lignes_max else []))


def executer(sources, etat, quand=None, tout=False, limite=None, sauver_tous=None):
    """sauver_tous : enregistre l'état toutes les N sources lues ; si l'ordinateur s'arrête en route, le travail fait
    est gardé et la relance reprend où elle s'était arrêtée (les sources déjà lues ne sont plus « dues »)."""
    quand = quand or maintenant()
    instant = dt.datetime.fromisoformat(quand)
    resultats, arretes = [], {}
    for src in sources:
        s = lecteur.site(src["url"])
        if s in arretes:
            resultats.append((src, "non_lue", f"site arrêté : {arretes[s]}"))
            continue
        if not tout and not due(etat.de(src["url"]), src.get("delai_jours"), instant):
            resultats.append((src, "pas_due", ""))
            continue
        if limite is not None and sum(v not in ("pas_due", "non_lue") for _, v, _ in resultats) >= limite:
            break
        try:
            verdict, detail = traiter(src, etat, quand)
        except lecteur.Captcha as ex:
            arretes[s] = str(ex)
            verdict, detail = "captcha", str(ex)
            e = etat.sources[src["url"]]  # compté comme un échec : la dernière version reste utilisée
            e["echecs_consecutifs"] = e.get("echecs_consecutifs", 0) + 1
            e["derniere_erreur"], e["derniere_erreur_le"] = str(ex), quand
        resultats.append((src, verdict, detail))
        if sauver_tous and sum(v not in ("pas_due", "non_lue") for _, v, _ in resultats) % sauver_tous == 0:
            etat.enregistrer()
    return resultats


def alertes(resultats, etat):
    a = []
    for src, verdict, detail in resultats:
        e = etat.de(src["url"])
        if verdict == "disparue":
            a.append(f"Page disparue ({detail}) : {src['url']}")
        elif verdict == "captcha":
            a.append(f"CAPTCHA : lecture du site arrêtée, ne pas contourner : {src['url']}")
        elif verdict == "interdit_robots":
            a.append(f"robots.txt interdit la lecture : {src['url']} (mettre actif = 0 ou demander un accès)")
        elif e.get("echecs_consecutifs", 0) >= ECHECS_ALERTE:
            a.append(f"{e['echecs_consecutifs']} échecs de suite ({e.get('derniere_erreur')}) : {src['url']}")
    a += [f"À relire depuis le {e.get('change_depuis', '?')} : {u}" for u, e in sorted(etat.sources.items())
          if e.get("a_relire")]
    return a


NOMS = {"nouvelle": "Première lecture (référence)", "inchangee": "Inchangées", "changee": "Changées : à relire",
        "a_relire": "Toujours à relire", "echec": "Échecs (dernière version gardée)", "disparue": "Disparues",
        "captcha": "CAPTCHA", "interdit_robots": "Interdites par robots.txt", "non_lue": "Non lues (site arrêté)",
        "pas_due": "Pas encore dues (lues il y a moins que leur délai)"}


def rapport(resultats, etat, quand, enregistre):
    n = collections.Counter(v for _, v, _ in resultats)
    r = [f"# Rafraîchissement des sources : {quand}", "",
         f"État {'enregistré' if enregistre else 'NON enregistré (lancer avec --enregistrer)'}.", "",
         "| Résultat | Sources |", "|---|---|"]
    r += [f"| {NOMS[k]} | {n[k]} |" for k in NOMS if n[k]]
    for verdict in ("changee", "echec", "disparue", "captcha", "interdit_robots"):
        liste = [(s, d) for s, v, d in resultats if v == verdict]
        if liste:
            r += ["", f"## {NOMS[verdict]}", ""]
            for s, d in liste:
                r.append(f"- [{s['organisme']}] {s['url']}")
                if verdict == "changee" and s.get("utilise_par"):
                    r.append(f"  utilisée par : {s['utilise_par'].replace(';', ', ')}"
                             + (" (fichier relu à la main : à corriger si une valeur a changé)"
                                if "db/reference" in s["utilise_par"] else ""))
                if verdict == "changee" and "\n" in d:
                    r += ["", "```diff", d, "```", ""]
                elif d:
                    r.append(f"  {d}")
    a = alertes(resultats, etat)
    r += ["", "## Alertes pour l'administration", ""] + ([f"- {x}" for x in a] or ["Aucune."])
    return "\n".join(r) + "\n"


def valider(etat, url):
    e = etat.sources.get(url)
    if not e or not e.get("empreinte_lue"):
        raise SystemExit(f"source jamais lue : {url}")
    e.update(empreinte_validee=e["empreinte_lue"], a_relire=False, valide_le=maintenant())
    e.pop("change_depuis", None)
    texte = etat.texte(url, "lu")
    if texte is not None:
        etat.ecrire_texte(url, "valide", texte)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enregistrer", action="store_true", help="enregistrer le nouvel état")
    ap.add_argument("--tout", action="store_true", help="relire même les sources lues il y a moins que leur délai")
    ap.add_argument("--organisme", help="seulement cet organisme (AFI, FIPA…)")
    ap.add_argument("--limite", type=int, help="nombre maximal de sources lues")
    ap.add_argument("--valider", action="append", metavar="URL", help="marquer le changement de cette source comme relu")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console Windows
    etat = Etat()
    if a.valider:
        for u in a.valider:
            valider(etat, u)
            print("validée :", u)
        etat.enregistrer()
        return
    sources = [s for s in sources_actives() if not a.organisme or s["organisme"].lower() == a.organisme.lower()]
    if not sources:
        raise SystemExit(f"aucune source active dans {CONFIG} (lancer python -m dalila.sources.inventaire --ecrire)")
    quand = maintenant()
    resultats = executer(sources, etat, quand, tout=a.tout, limite=a.limite,
                         sauver_tous=20 if a.enregistrer else None)
    texte = rapport(resultats, etat, quand, a.enregistrer)
    if a.enregistrer:
        etat.enregistrer()
    (DOSSIER / "rapports").mkdir(parents=True, exist_ok=True)
    f = DOSSIER / "rapports" / f"rafraichir_{quand[:16].replace(':', '').replace(' ', '_')}.md"
    f.write_text(texte, encoding="utf-8")
    print(texte)
    print("rapport :", f)


if __name__ == "__main__":
    main()
