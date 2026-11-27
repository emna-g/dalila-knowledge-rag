"""Garde-fous du harnais, à l'entrée et à la sortie du modèle.

Entrée  : longueur (500 caractères, BF1), historique (20 messages), données personnelles masquées avant le modèle et
          les journaux (BNF10 : téléphone, CIN, courriel).
Sortie  : ancrage : chaque nombre et chaque identifiant de balise de la réponse doit venir d'un résultat d'outil (ou de
          la question). Sinon, le harnais redemande une fois au modèle, puis répond par le repli (BNF4).
Ces règles portent sur des chiffres et des formats (téléphone, balises), jamais sur la langue du visiteur.
"""
import json, re
from decimal import Decimal

LONGUEUR_MAX, HISTORIQUE_MAX = 500, 20

_COURRIEL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TEL_216 = re.compile(r"(?:\+|00)216[\s.-]?\d{2}[\s.-]?\d{3}[\s.-]?\d{3}")
_HUIT_CHIFFRES = re.compile(r"(?<![\d.,])\d{8}(?![\d.,])")  # téléphone tunisien ou CIN écrit d'un bloc


def masquer(texte):
    texte = _COURRIEL.sub("[courriel masqué]", texte)
    texte = _TEL_216.sub("[téléphone masqué]", texte)
    return _HUIT_CHIFFRES.sub("[numéro masqué]", texte)


def nettoyer_entree(message, historique=()):
    """-> (message, historique) bornés et masqués. Seuls les rôles user/assistant sont gardés de l'historique."""
    message = masquer((message or "").strip()[:LONGUEUR_MAX])
    propre = [{"role": h["role"], "content": masquer(str(h.get("content", ""))[:2000])}
              for h in list(historique or [])[-HISTORIQUE_MAX:]
              if isinstance(h, dict) and h.get("role") in ("user", "assistant")]
    return message, propre


# ---------------------------------------------------------------- ancrage des nombres et des balises
_ARABES = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NOMBRE = re.compile(r"\d+(?:[\u0020\u00a0\u202f]\d{3})*(?:[.,]\d+)?")
_PUCE = re.compile(r"(?m)^\s*\d{1,2}[.)]\s")
_MARQUEUR_ENUMERATION = re.compile(r"[.)]\s+\S")
_INTRO_ENUMERATION = re.compile(
    r"\b(?:options?|choix|étapes?|steps?|items?|points?|listes?|lists?|alternatives?)\s*[:：]",
    re.I,
)
_PHRASE = re.compile(r"[.!?;؛؟\n]")
_CLAUSE = re.compile(r"[.!?;؛؟,\n]")
_BALISE = re.compile(r"\[\[(ZONE|LOT):([^:\]]+):[^\]]*\]\]")
_PDF = re.compile(r"\[\[PDF:(.+?):([^:\]]*)\]\]")
_LIEN_MD = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", re.I)
_URL = re.compile(r"https?://[^\s)\]>]+", re.I)
_SECTION_SOURCES = re.compile(r"(?im)^\s*(?:sources?|références?)\s*:\s*(.*)$")
_CHAMPS_NON_NUMERIQUES = {
    "body", "code", "content", "contenu", "date", "date_source", "description", "details",
    "document_text", "erreur", "extrait", "fichier", "file", "filename", "file_name", "filtres",
    "id", "lien", "lot_num", "name", "nom", "nom_ar", "nom_de_fichier", "nom_fr",
    "nom_fichier", "num_lot", "numero", "ocr", "ocr_text", "passage", "path", "question",
    "source", "source_url", "sources", "text", "text_ocr", "texte", "texte_document",
    "texte_ocr", "title", "titre", "type", "url",
}
_CATEGORIES_CHAMPS = {
    "prix_m2": re.compile(
        r"(?:^|_)(?:prix_m2|price_m2|price_per_m2|prix_site_afi)(?:_|$)", re.I
    ),
    "prix_total": re.compile(
        r"(?:^|_)(?:prix_total|prix_terrain_estime|total_price|total_land_price)(?:_|$)", re.I
    ),
    "prix": re.compile(r"(?:^|_)(?:prix|price|cout|cost|tarif)(?:_|$)", re.I),
    "frais": re.compile(r"(?:^|_)(?:frais|fee|fees|charges?)(?:_|$)", re.I),
    "budget": re.compile(r"(?:^|_)(?:budget|max_budget)(?:_|$)", re.I),
    "surface": re.compile(r"(?:^|_)(?:surface|superficie|area|hectares?|ha|m2)(?:_|$)", re.I),
    "lots": re.compile(
        r"(?:^|_)(?:nombre_total|nombre_lots|nb_lots|number_of_lots|lot_count|"
        r"lots_disponibles(?:_a_confirmer)?|lots_mis_aux_encheres)(?:_|$)", re.I
    ),
    "delai": re.compile(r"(?:^|_)(?:delai|duree|duration|delay|days?|jours?|mois|months?|weeks?|semaines?)(?:_|$)", re.I),
    "emplois": re.compile(r"(?:^|_)(?:emplois?|employment|jobs?|postes?)(?:_|$)", re.I),
    "distance": re.compile(r"(?:^|_)(?:distance|km|kilometres?|kilometers?)(?:_|$)", re.I),
    "taux": re.compile(r"(?:^|_)(?:taux|rate|pourcentage|percentage|percent|pct)(?:_|$)", re.I),
}
_VALEUR_SCALAIRE = re.compile(
    r"^\s*(\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?)\s*"
    r"(?:(?:dt(?:\s*/\s*m(?:²|2))?|tnd|dinars?|m(?:²|2)|ha|hectares?|km|"
    r"kilom[eè]tres?|meters?|m[eè]tres?|lots?|jours?|days?|weeks?|semaines?|"
    r"mois|months?|heures?|hours?|emplois?|jobs?|%|pour\s*cent|percent(?:age)?))?\s*$",
    re.I,
)
_UNITES_REPONSE = (
    ("taux", re.compile(r"^\s*(?:[,;:]?\s*)(?:%|pour\s*cent\b|percent(?:age)?\b|بالمائة|بالمئة)", re.I)),
    ("surface", re.compile(r"^\s*(?:[,;:]?\s*)(?:m(?:²|2)\b|ha\b|hectares?\b|m[eè]tres?\s+carr[eé]s?)", re.I)),
    ("lots", re.compile(r"^\s*(?:[,;:]?\s*)(?:lots?\b|plots?\b|parcelles?\b|مقسم|مقاسم|قطع(?:ة)?)", re.I)),
    ("delai", re.compile(r"^\s*(?:[,;:]?\s*)(?:jours?\b|days?\b|weeks?\b|semaines?\b|mois\b|months?\b|heures?\b|hours?\b|أيام|يوم|أشهر|شهر)", re.I)),
    ("emplois", re.compile(r"^\s*(?:[,;:]?\s*)(?:emplois?\b|jobs?\b|employees?\b|workers?\b|postes?\b|فرص\s+عمل|مواطن\s+شغل)", re.I)),
    ("distance", re.compile(r"^\s*(?:[,;:]?\s*)(?:km\b|kilom[eè]tres?\b|meters?\b|m[eè]tres?\b|m(?![²2])\b|كم|كيلومتر|مسافة)", re.I)),
)
_CUES_REPONSE = {
    "prix_total": re.compile(
        r"\b(?:(?:prix|price)\s+total|total\s+(?:price|cost)|co[uû]t\s+total)\b", re.I
    ),
    "frais": re.compile(r"\b(?:frais|fees?|charges?)\b|رسوم|مصاريف", re.I),
    "budget": re.compile(r"\b(?:budget|max(?:imum)?\s+budget)\b|الميزانية", re.I),
    "prix": re.compile(r"\b(?:prix|price|co[uû]t|cost|tarif)\b|السعر|الثمن|تكلفة", re.I),
    "surface": re.compile(r"\b(?:surface|superficie|area|hectare|hectares)\b|m²|متر\s+مربع|مساحة|هكتار"),
    "lots": re.compile(r"\b(?:lots?|plots?|parcelles?|nombre\s+de\s+lots?)\b|مقسم|مقاسم|قطعة|قطع"),
    "delai": re.compile(r"\b(?:d[eé]lai|dur[eé]e|delay|duration|jours?|days?|weeks?|semaines?|mois|months?|heures?|hours?)\b|أيام|يوم|أشهر|شهر"),
    "emplois": re.compile(r"\b(?:emplois?|employment|jobs?|employees?|workers?|postes?)\b|فرص\s+عمل|مواطن\s+شغل"),
    "distance": re.compile(r"\b(?:distance|km|kilom[eè]tres?|kilometers?|meters?|m[eè]tres?)\b|كم|كيلومتر|مسافة"),
    "taux": re.compile(r"\b(?:taux|rate|pourcentage|percentage|percent)\b|%|نسبة|بالمائة|بالمئة"),
}
_PRIX_PAR_SURFACE = re.compile(r"\b(?:prix|price)\s+(?:au|par|per)\s+m(?:²|2)\b", re.I)
_PRIX_TOTAL = re.compile(r"\b(?:(?:prix|price)\s+total|total\s+(?:price|cost)|co[uû]t\s+total)\b", re.I)
_FRAIS_BUDGET = {
    "frais": _CUES_REPONSE["frais"],
    "budget": _CUES_REPONSE["budget"],
}
_DEVISE_M2 = re.compile(
    r"^\s*(?:[,;:]?\s*)(?:dt\b|tnd\b|dinars?\b|دينار|دنانير)\s*/\s*m(?:²|2)\b", re.I
)
_DEVISE = re.compile(r"^\s*(?:[,;:]?\s*)(?:dt\b|tnd\b|dinars?\b|دينار|دنانير)", re.I)


def _valeurs(jeton):
    """Un nombre écrit -> ses lectures possibles : groupé (« 1 000 » = 1000) et chaque bloc séparé."""
    plein = re.sub(r"[\u0020\u00a0\u202f]", "", jeton).replace(",", ".")
    blocs = re.split(r"[\u0020\u00a0\u202f]", jeton)
    return {_norm(plein)}, {_norm(b.replace(",", ".")) for b in blocs}


def _norm(s):
    try:
        x = float(s)
    except ValueError:
        return s
    return int(x) if x == int(x) else round(x, 2)


def nombres(texte):
    texte = _PUCE.sub(" ", str(texte).translate(_ARABES))
    return [_valeurs(j) for j in _NOMBRE.findall(texte)]


def _connus(resultats, question):
    """Valeurs numériques structurées par propriété; les textes libres ne servent pas de preuve."""
    connus = {categorie: set() for categorie in _CATEGORIES_CHAMPS}

    def ajouter(categorie, valeur):
        if isinstance(valeur, bool) or valeur is None:
            return
        if isinstance(valeur, (int, float, Decimal)):
            try:
                nombre = float(valeur)
                valeurs = {_norm(nombre), _norm(round(nombre, 1)), _norm(round(nombre))}
            except (OverflowError, ValueError):
                return
        elif isinstance(valeur, str):
            valeur = valeur.translate(_ARABES)
            scalaire = _VALEUR_SCALAIRE.fullmatch(valeur)
            if not scalaire:
                return
            plein, blocs = _valeurs(scalaire.group(1))
            valeurs = plein | blocs
        else:
            return
        connus[categorie].update(valeurs)
        if categorie in ("prix_m2", "prix_total"):
            connus["prix"].update(valeurs)

    def visiter(v, cle=None, categorie_parent=None):
        cle = str(cle or "").casefold()
        if cle in _CHAMPS_NON_NUMERIQUES or cle.endswith(
            ("_id", "_url", "_path", "_filename", "_num", "_code")
        ):
            return
        categorie = next(
            (nom for nom, motif in _CATEGORIES_CHAMPS.items() if motif.search(cle)),
            categorie_parent,
        )
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float, Decimal, str)):
            if categorie:
                ajouter(categorie, v)
        elif isinstance(v, dict):
            for k, x in v.items():
                visiter(x, k, categorie)
        elif isinstance(v, (list, tuple)):
            for x in v:
                if isinstance(x, (dict, list, tuple)):
                    visiter(x)
                else:
                    visiter(x, cle, categorie)

    visiter(resultats)
    nombres_question = set()
    for plein, blocs in nombres(question):
        nombres_question.update(plein | blocs)
    return connus, nombres_question


def _categorie_reponse(texte, debut, fin):
    suite = texte[fin:fin + 32]
    debut_clause = max((m.end() for m in _CLAUSE.finditer(texte, 0, debut)), default=0)
    clause_fin = _CLAUSE.search(texte, fin)
    fin_clause = clause_fin.start() if clause_fin else len(texte)
    debut_contexte = max(debut_clause, debut - 48)
    fin_contexte = min(fin_clause, fin + 48)
    contexte = texte[debut_contexte:fin_contexte]

    frais_budget = []
    for categorie, motif in _FRAIS_BUDGET.items():
        for match in motif.finditer(contexte):
            distance = max(0, debut_contexte + match.start() - fin, debut - (debut_contexte + match.end()))
            if distance <= 24:
                frais_budget.append((distance, categorie))
    if frais_budget:
        distance_min = min(distance for distance, _ in frais_budget)
        categories_proches = {
            categorie for distance, categorie in frais_budget if distance <= distance_min + 3
        }
        return next(iter(categories_proches)) if len(categories_proches) == 1 else None

    prix_m2_unite = _DEVISE_M2.search(suite)
    if prix_m2_unite or _PRIX_PAR_SURFACE.search(contexte):
        return "prix_m2"
    if _PRIX_TOTAL.search(contexte):
        return "prix_total"

    for categorie, motif in _UNITES_REPONSE:
        if motif.search(suite):
            return categorie

    candidats = []
    for categorie, motif in _CUES_REPONSE.items():
        if categorie in ("prix_total", "frais", "budget"):
            continue
        for match in motif.finditer(contexte):
            distance = max(0, debut_contexte + match.start() - fin, debut - (debut_contexte + match.end()))
            if distance <= 36:
                candidats.append((distance, categorie))
    if not candidats:
        return None

    distance_min = min(distance for distance, _ in candidats)
    categories_proches = {categorie for distance, categorie in candidats if distance <= distance_min + 3}
    if len(categories_proches) == 1:
        return next(iter(categories_proches))
    if _DEVISE.search(suite):
        return "prix"
    return None


def _est_marqueur_enumeration(texte, debut, fin, valeur):
    if not isinstance(valeur, int) or not 0 <= valeur <= 5:
        return False
    if not _MARQUEUR_ENUMERATION.match(texte[fin:]):
        return False
    debut_phrase = max((m.end() for m in _PHRASE.finditer(texte, 0, debut)), default=0)
    return bool(_INTRO_ENUMERATION.search(texte[debut_phrase:debut]))


def _sources(resultats):
    urls, titres_par_url, titres = set(), {}, set()
    identifiants, titres_par_identifiant = set(), {}

    def visiter(v):
        if isinstance(v, dict):
            titre = v.get("titre") or v.get("title")
            source = v.get("source")
            lien_est_source = any(
                isinstance(v.get(k), str) and v[k].startswith(("http://", "https://"))
                for k in ("url", "lien", "source_url")
            )
            if not titre and v.get("id") is not None and ("texte" in v or "text" in v):
                titre = v.get("question")
            if isinstance(titre, str) and titre.strip():
                titres.add(titre.strip())
            if isinstance(source, str) and source.strip() and not source.startswith(("http://", "https://")):
                titres.add(source.strip())
            identifiant = v.get("id")
            if identifiant is not None and ("texte" in v or "text" in v) and (titre or lien_est_source):
                identifiant = str(identifiant)
                identifiants.add(identifiant)
                titres_par_identifiant.setdefault(identifiant, set())
                if isinstance(titre, str) and titre.strip():
                    titres_par_identifiant[identifiant].add(titre.strip())
            liens = [v.get(k) for k in ("url", "lien", "source_url")]
            if isinstance(source, str) and source.startswith(("http://", "https://")):
                liens.append(source)
            for lien in liens:
                if isinstance(lien, str) and lien.startswith(("http://", "https://")):
                    urls.add(lien)
                    titres_par_url.setdefault(lien, set())
                    if isinstance(titre, str) and titre.strip():
                        titres_par_url[lien].add(titre.strip())
                    if isinstance(source, str) and source.strip() and not source.startswith(("http://", "https://")):
                        titres_par_url[lien].add(source.strip())
            for enfant in v.values():
                visiter(enfant)
        elif isinstance(v, (list, tuple)):
            for enfant in v:
                visiter(enfant)

    visiter(resultats)
    return urls, titres_par_url, titres, identifiants, titres_par_identifiant


def _titres_cites(reponse, titres_connus):
    section = _SECTION_SOURCES.search(reponse)
    if not section:
        return []
    contenu = (section.group(1) or "") + reponse[section.end():]
    contenu = _LIEN_MD.sub(" ", contenu)
    contenu = _PDF.sub(" ", contenu)
    contenu = _URL.sub(" ", contenu)

    cites = []
    for ligne in re.split(r"[;\n|•]+", contenu):
        ligne = re.sub(r"^\s*[-*]\s*", "", ligne).strip().strip("\"'“”‘’ ")
        if not ligne:
            continue
        morceaux = [ligne]
        if "," in ligne and ligne not in titres_connus:
            morceaux = ligne.split(",")
        cites.extend(
            morceau.strip().strip("\"'“”‘’ .") for morceau in morceaux if morceau.strip().strip("\"'“”‘’ .")
        )
    return cites


def contient_preuves(resultats):
    """True for usable tool data, including an explicit zero count or a resolution note."""
    ignores = {"erreur", "details", "sources", "filtres", "texte"}

    def utile(v, cle=None):
        if cle in ignores or v is None or isinstance(v, bool):
            return False
        if isinstance(v, dict):
            if "erreur" in v:
                return False
            return any(utile(x, k) for k, x in v.items())
        if isinstance(v, (list, tuple)):
            return any(utile(x) for x in v)
        if isinstance(v, (int, float)):
            return True
        if isinstance(v, str):
            return bool(v.strip())
        return False

    return utile(resultats)


def verifier_ancrage(reponse, resultats, question=""):
    """-> {"ok": bool, "nombres_inconnus": [...], "balises_inconnues": [...]}.
    resultats : liste des résultats d'outils (dicts) de ce tour. Les petits entiers (0 à 5) sont admis : énumérations."""
    valeurs_outils, nombres_question = _connus(resultats, question)
    sans_balises = _PDF.sub(" ", _BALISE.sub(" ", reponse))
    section = _SECTION_SOURCES.search(sans_balises)
    if section:
        sans_balises = sans_balises[:section.start()]
    sans_balises = _URL.sub(" ", _LIEN_MD.sub(" ", sans_balises))
    texte_nombres = _PUCE.sub(" ", sans_balises).translate(_ARABES)
    nombres_inconnus = []
    for match in _NOMBRE.finditer(texte_nombres):
        plein, blocs = _valeurs(match.group())
        n = next(iter(plein))
        if _est_marqueur_enumeration(texte_nombres, match.start(), match.end(), n):
            continue
        if plein & nombres_question or blocs <= nombres_question:
            continue
        categorie = _categorie_reponse(texte_nombres, match.start(), match.end())
        connus = valeurs_outils.get(categorie, set()) if categorie else set()
        if plein & connus or blocs <= connus:
            continue
        nombres_inconnus.append(n)
    texte_outils = json.dumps(resultats, ensure_ascii=False)
    balises = [f"{t}:{i}" for t, i in _BALISE.findall(reponse) if f'"{i.strip()}"' not in texte_outils
               and f": {i.strip()}," not in texte_outils and f": {i.strip()}}}" not in texte_outils]
    urls, titres_par_url, titres, identifiants, titres_par_identifiant = _sources(resultats)
    sources_inconnues = []
    citations_valides = False

    liens_cites = _URL.findall(_PDF.sub(" ", reponse))
    for lien in liens_cites:
        lien = lien.rstrip(".,;:!?،؛»")
        if lien not in urls:
            sources_inconnues.append(lien)
        else:
            citations_valides = True

    for cible, titre in _PDF.findall(reponse):
        cible = cible.strip().rstrip(".,;!?،؛»")
        titre = titre.strip()
        if cible.startswith(("http://", "https://")):
            valide = cible in urls
            titres_attendus = titres_par_url.get(cible, set())
        else:
            valide = cible in identifiants
            titres_attendus = titres_par_identifiant.get(cible, set())
        if not valide:
            sources_inconnues.append(cible)
            continue
        if not titre:
            sources_inconnues.append(f"titre manquant -> {cible}")
            continue
        if not titres_attendus or titre not in titres_attendus:
            sources_inconnues.append(f"{titre} -> {cible}")
            continue
        citations_valides = True

    for titre, url in _LIEN_MD.findall(reponse):
        titre = titre.strip()
        if url not in urls:
            sources_inconnues.append(url)
        elif titre not in titres or titre not in titres_par_url.get(url, set()):
            sources_inconnues.append(f"{titre} -> {url}")
        else:
            citations_valides = True

    titres_cites = _titres_cites(reponse, titres)
    for titre in titres_cites:
        if titre not in titres:
            sources_inconnues.append(titre)
        else:
            citations_valides = True

    sources_absentes = bool(urls or titres or identifiants) and not citations_valides
    return {"ok": not nombres_inconnus and not balises and not sources_inconnues and not sources_absentes,
            "nombres_inconnus": nombres_inconnus, "balises_inconnues": balises,
            "sources_inconnues": sources_inconnues, "sources_absentes": sources_absentes}
