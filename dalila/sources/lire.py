"""Lecture d'une source (page web ou PDF), poliment, sans jamais contourner une protection.

    from dalila.sources.lire import lire
    l = lire("https://www.afi.nat.tn/fr/nos-services/")
    l.ok, l.type, l.texte, l.empreinte, l.erreur

Règles :
  - au plus une requête par seconde et par site (PAUSE_S) ; robots.txt respecté (un site qui interdit les robots,
    comme SICAD, n'est pas lu) ;
  - CAPTCHA ou page de vérification anti-robot : exception Captcha, l'appelant arrête de lire ce site ; jamais contourné ;
  - redirection vers un autre site : refusée (seules les URL de la configuration sont lues, BNF14) ;
  - le texte lu est une DONNÉE : il est seulement extrait, normalisé et comparé, jamais interprété.
Page : texte du contenu principal (<main> ou <article> s'ils existent), sans menus, en-têtes, pieds de page ni scripts.
PDF : l'empreinte porte sur les octets du fichier ; le texte est extrait page par page (pypdfium2), au format
« === page N === » de la fusion. Un PDF scanné (pages sans texte) est signalé : son texte demande un OCR.
"""
import hashlib, os, re, tempfile, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from dataclasses import dataclass
from html.parser import HTMLParser
from dalila.sources.empreinte import empreinte_texte, normaliser

AGENT = "dalila-sources/1.0"
PAUSE_S = 1.0               # entre deux requêtes vers un même site
TAILLE_MAX_PAGE = 10 * 2**20     # une page web plus grosse n'est pas une page de texte
TAILLE_MAX_PDF = 500 * 2**20     # PDF : lu par morceaux (empreinte calculée au fil de l'eau, rien gardé en mémoire)
MORCEAU = 2**20
MIN_CARACTERES_PAGE = 40         # une page de PDF avec moins de texte est une image (scan)
MARQUES_CAPTCHA = ("captcha", "g-recaptcha", "hcaptcha", "cf-challenge", "challenge-platform",
                   "just a moment...", "attention required! | cloudflare")
PHRASES_MUR = ("verify you are human", "verifying you are human", "checking your browser", "are you a robot",
               "vérifiez que vous êtes humain", "vérification de sécurité", "security check", "access denied")

_derniere_requete = {}      # site -> instant de la dernière requête
_robots = {}                # site -> RobotFileParser, ou None si robots.txt illisible (lecture permise)


class Captcha(Exception):
    """Le site demande une vérification anti-robot : arrêter de le lire (ne jamais contourner)."""


@dataclass
class Lecture:
    url: str
    ok: bool = False
    statut_http: int | None = None
    type: str | None = None         # "page" ou "pdf"
    texte: str = ""                 # texte utile (page) ; vide pour un PDF
    empreinte: str | None = None
    taille: int = 0
    erreur: str | None = None
    interdit_robots: bool = False
    scanne: bool = False            # PDF surtout fait d'images : texte à obtenir par OCR
    non_modifie: bool = False       # le site répond 304 : rien n'a changé depuis la lecture précédente
    etag: str | None = None         # repères HTTP gardés pour la prochaine lecture (évite de retélécharger un PDF)
    modifie_le: str | None = None


def site(url):
    return urllib.parse.urlsplit(url).netloc.lower()


def vers_uri(url):
    """URL telle qu'écrite dans nos fichiers (lettres arabes, espaces) -> URL envoyable (encodage %)."""
    p = urllib.parse.urlsplit(url.strip())
    chemin = urllib.parse.quote(p.path, safe="/%:@!$&'()*+,;=-._~")
    requete = urllib.parse.quote(p.query, safe="=&%:/?+,;-._~")
    return urllib.parse.urlunsplit((p.scheme, p.netloc.encode("idna").decode("ascii"), chemin, requete, ""))


def _attendre(s):
    reste = PAUSE_S - (time.monotonic() - _derniere_requete.get(s, -1e9))
    if reste > 0:
        time.sleep(reste)
    _derniere_requete[s] = time.monotonic()


def permis_par_robots(url):
    s = site(url)
    if s not in _robots:
        p = urllib.parse.urlsplit(url)
        rp = urllib.robotparser.RobotFileParser()
        try:
            _attendre(s)
            req = urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                rp.parse(r.read().decode("utf-8", errors="replace").splitlines())
            _robots[s] = rp
        except urllib.error.HTTPError as e:
            # 401/403 : le site refuse les robots ; 404 et autres : pas de règle, lecture permise (usage courant)
            if e.code in (401, 403):
                rp.disallow_all = True
                _robots[s] = rp
            else:
                _robots[s] = None
        except Exception:  # noqa: BLE001  (site injoignable : l'erreur sera dite par la lecture elle-même)
            _robots[s] = None
    rp = _robots[s]
    return True if rp is None else rp.can_fetch(AGENT, vers_uri(url))


class _Texte(HTMLParser):
    """Texte visible d'une page, sans scripts, styles, menus, en-têtes, pieds de page ni formulaires."""
    IGNORER = {"script", "style", "noscript", "nav", "header", "footer", "form", "svg", "template", "iframe"}
    BLOCS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "td"}

    PRINCIPAL = {"main", "article"}
    # en-têtes et pieds de page des sites faits avec Elementor (AFI, FIPA…), comme le faisait la collecte de la fusion
    CLASSES_IGNOREES = ("elementor-location-header", "elementor-location-footer")

    def __init__(self, principal_seulement=False):
        super().__init__(convert_charrefs=True)
        self.profondeur, self.morceaux = 0, []
        self.principal_seulement, self.dans_principal = principal_seulement, 0
        self.bloc_ignore = None                   # [balise, profondeur] du bloc ignoré en cours

    def handle_starttag(self, tag, attrs):
        if tag in self.PRINCIPAL:
            self.dans_principal += 1
        if self.bloc_ignore:                      # dans un en-tête ou pied de page marqué par sa classe
            if tag == self.bloc_ignore[0]:
                self.bloc_ignore[1] += 1
            return
        classes = dict(attrs).get("class") or ""
        if any(c in classes for c in self.CLASSES_IGNOREES):
            self.bloc_ignore = [tag, 1]
        elif tag in self.IGNORER:
            self.profondeur += 1
        elif tag in self.BLOCS:
            self.morceaux.append("\n")

    def handle_endtag(self, tag):
        if self.bloc_ignore:
            if tag == self.bloc_ignore[0]:
                self.bloc_ignore[1] -= 1
                if not self.bloc_ignore[1]:
                    self.bloc_ignore = None
            return
        if tag in self.IGNORER and self.profondeur:
            self.profondeur -= 1
        if tag in self.PRINCIPAL and self.dans_principal:
            self.dans_principal -= 1

    def handle_data(self, data):
        if not self.profondeur and not self.bloc_ignore and (self.dans_principal or not self.principal_seulement):
            self.morceaux.append(data)


def texte_html(html):
    """Texte utile ; si la page marque son contenu principal (<main>, <article>) et qu'il a du texte, lui seul."""
    texte = _extraire(html, principal_seulement=True) if re.search(r"<(main|article)[\s>]", html, re.I) else ""
    return texte or _extraire(html, principal_seulement=False)


def _extraire(html, principal_seulement):
    t = _Texte(principal_seulement)
    t.feed(html)
    lignes = (normaliser(l) for l in "".join(t.morceaux).splitlines())
    return "\n".join(l for l in lignes if l)


def est_captcha(html, texte=None):
    """Page de vérification anti-robot (« mur »). Une vraie page qui contient un formulaire protégé (CAPTCHA d'un
    formulaire de contact, comme la page Contact de l'APII) n'en est pas une : un mur n'a presque pas de texte, ou
    dit explicitement qu'il vérifie le visiteur."""
    debut = html[:20000].lower()
    if not any(m in debut for m in MARQUES_CAPTCHA):
        return False
    texte = (texte_html(html) if texte is None else texte).lower()
    return len(texte) < 300 or (len(texte) < 1500 and any(p in texte for p in PHRASES_MUR))


def lire(url, delai_s=30, etag=None, modifie_le=None):
    """etag, modifie_le : repères de la lecture précédente ; si le site les comprend et que rien n'a changé, il répond
    304 sans renvoyer le fichier (non_modifie = True)."""
    l = Lecture(url=url)
    s = site(url)
    if not permis_par_robots(url):
        l.interdit_robots, l.erreur = True, "robots.txt interdit la lecture de cette page"
        return l
    _attendre(s)
    entetes = {"User-Agent": AGENT, "Accept": "text/html,application/pdf,*/*"}
    if etag:
        entetes["If-None-Match"] = etag
    if modifie_le:
        entetes["If-Modified-Since"] = modifie_le
    req = urllib.request.Request(vers_uri(url), headers=entetes)
    try:
        with urllib.request.urlopen(req, timeout=delai_s) as r:
            l.statut_http = r.status
            if site(r.geturl()) != s:
                l.erreur = f"redirection hors de la liste vers {site(r.geturl())} : non suivie"
                return l
            entete_type = r.headers.get("Content-Type", "")
            charset = r.headers.get_content_charset()
            l.etag, l.modifie_le = r.headers.get("ETag"), r.headers.get("Last-Modified")
            octets = r.read(MORCEAU)
            if octets[:5] == b"%PDF-" or "application/pdf" in entete_type:
                return _lire_pdf(r, octets, l)
            octets += r.read(TAILLE_MAX_PAGE + 1 - len(octets))
    except urllib.error.HTTPError as e:
        if e.code == 304:
            l.statut_http, l.ok, l.non_modifie = 304, True, True
            l.etag, l.modifie_le = e.headers.get("ETag") or etag, e.headers.get("Last-Modified") or modifie_le
            return l
        l.statut_http, l.erreur = e.code, f"HTTP {e.code}"
        if e.code in (403, 429, 503):
            corps = e.read(20000).decode("utf-8", errors="replace")
            if est_captcha(corps):
                raise Captcha(f"{s} : vérification anti-robot (HTTP {e.code})") from e
        return l
    except Exception as e:  # noqa: BLE001  (délai dépassé, site injoignable, certificat…)
        l.erreur = f"{type(e).__name__}: {e}"
        return l

    if len(octets) > TAILLE_MAX_PAGE:
        l.erreur = f"page de plus de {TAILLE_MAX_PAGE // 2**20} Mo : non lue"
        return l
    l.taille = len(octets)
    html = decoder(octets, charset)
    l.type, l.texte = "page", texte_html(html)
    if est_captcha(html, l.texte):
        raise Captcha(f"{s} : vérification anti-robot")
    if not l.texte:
        l.erreur = "page sans texte (vide ou construite en JavaScript)"
        return l
    l.empreinte, l.ok = empreinte_texte(l.texte), True
    return l


def _lire_pdf(reponse, debut, l):
    """Copie le PDF dans un fichier temporaire (empreinte calculée au fil de l'eau), en extrait le texte, l'efface."""
    h, l.taille = hashlib.sha256(debut), len(debut)
    fd, chemin = tempfile.mkstemp(suffix=".pdf", prefix="dalila_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(debut)
            while morceau := reponse.read(MORCEAU):
                h.update(morceau)
                f.write(morceau)
                l.taille += len(morceau)
                if l.taille > TAILLE_MAX_PDF:
                    l.erreur = f"PDF de plus de {TAILLE_MAX_PDF // 2**20} Mo : non lu"
                    return l
        l.type, l.empreinte, l.ok = "pdf", h.hexdigest(), True
        l.texte, l.scanne = texte_pdf(chemin)
        return l
    finally:
        os.remove(chemin)


def texte_pdf(chemin):
    """(texte « === page N === », scanné ?) ; scanné = plus de la moitié des pages sans texte (images)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return "", False
    try:
        doc = pdfium.PdfDocument(chemin)
        pages = [doc[i].get_textpage().get_text_range().replace('\r\n', '\n').strip() for i in range(len(doc))]
        doc.close()
    except Exception:  # noqa: BLE001  (PDF abîmé ou protégé : l'empreinte des octets suffit à suivre ses changements)
        return '', False
    vides = sum(len(t) < MIN_CARACTERES_PAGE for t in pages)
    texte = '\n\n'.join(f'=== page {i + 1} ===\n{t}' for i, t in enumerate(pages) if len(t) >= MIN_CARACTERES_PAGE)
    return texte, bool(pages) and vides > len(pages) / 2


def oublier_sites():
    """Remet à zéro les caches (robots.txt, politesse) : pour les tests."""
    _derniere_requete.clear()
    _robots.clear()


def decoder(octets, charset=None):
    """Encodage : celui de l'en-tête HTTP, sinon celui déclaré dans la page (<meta charset>), sinon UTF-8 s'il est
    valide, sinon windows-1252 (anciens sites, comme celui de l'APII)."""
    if not charset:
        m = re.search(rb"""<meta[^>]+charset=["']?([\w-]+)""", octets[:4096], re.I)
        charset = m.group(1).decode("ascii") if m else None
    if charset and charset.lower() in ("iso-8859-1", "latin-1", "latin1", "us-ascii", "ascii"):
        charset = "cp1252"  # comme les navigateurs (norme HTML) : les apostrophes ’ de ces pages sont en cp1252
    if charset:
        try:
            return octets.decode(charset, errors="replace")
        except LookupError:
            pass
    try:
        return octets.decode("utf-8")
    except UnicodeDecodeError:
        return octets.decode("cp1252", errors="replace")
