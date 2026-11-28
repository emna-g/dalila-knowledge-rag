"""Garde-fous du harnais, à l'entrée et à la sortie du modèle.

Entrée  : longueur (500 caractères, BF1), historique (20 messages), données personnelles masquées avant le modèle et
          les journaux (BNF10 : téléphone, CIN, courriel).
Sortie  : ancrage : chaque nombre et chaque identifiant de balise de la réponse doit venir d'un résultat d'outil (ou de
          la question). Sinon, le harnais redemande une fois au modèle, puis répond par le repli (BNF4).
Ces règles portent sur des chiffres et des formats (téléphone, balises), jamais sur la langue du visiteur.
"""
import json, re

LONGUEUR_MAX, HISTORIQUE_MAX = 500, 20

_COURRIEL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TEL_216 = re.compile(r"(?:\+|00)216[\s.-]?\d{2}[\s.-]?\d{3}[\s.-]?\d{3}")
_HUIT_CHIFFRES = re.compile(r"(?<![\d.,])\d{8}(?!\d|[.,]\d)")  # téléphone tunisien ou CIN d'un bloc (« CIN 09876543, »)


_TEL_LOCAL = re.compile(r"(?<![\d.,])[2-9]\d[\s.-]\d{3}[\s.-]\d{3}(?!\d|[.,]\d)")  # 98 123 456
# identifiant du Registre national des entreprises / matricule fiscal : 7 chiffres et une lettre (« 1234567A »), parfois
# suivis du code TVA, de la catégorie et de l'établissement (« 1234567/A/M/000 »)
_RNE = re.compile(r"(?<![\w.,])\d{7}\s*[/-]?\s*[A-Za-z](?:(?:\s*[/-]?\s*[A-Za-z]){1,2}\s*[/-]?\s*\d{3})?(?!\w)")


def masquer(texte):
    """Formats de données personnelles (courriel, téléphone, CIN, RNE) : avant le modèle et dans les journaux."""
    texte = _COURRIEL.sub("[courriel masqué]", texte)
    texte = _TEL_216.sub("[téléphone masqué]", texte)
    texte = _RNE.sub("[RNE masqué]", texte)
    texte = _TEL_LOCAL.sub("[téléphone masqué]", texte)
    return _HUIT_CHIFFRES.sub("[numéro masqué]", texte)


_ner = {}
MODELE_NOMS = "Davlan/xlm-roberta-base-ner-hrl"   # AFL-3.0 ; noms de personnes en arabe, français, anglais, allemand…


def anonymiser(texte):
    """BNF16 : texte gardé au journal et utilisé par l'apprentissage, sans donnée personnelle. En plus des formats
    (masquer), les noms de personnes sont retirés par un modèle de reconnaissance d'entités ; un nom qui désigne un lieu
    connu de la base (« Sidi Achour ») est gardé. Modèle indisponible : seulement les formats (jamais d'erreur)."""
    texte = masquer(texte or "")
    if not texte.strip():
        return texte
    try:
        if "m" not in _ner:
            from transformers import pipeline
            from dalila.config import MODELES
            _ner["m"] = pipeline("token-classification", model=MODELE_NOMS, aggregation_strategy="simple", device=-1,
                                 model_kwargs={"cache_dir": str(MODELES)})
        entites = [e for e in _ner["m"](texte[:512]) if e["entity_group"] == "PER" and e["score"] >= 0.6]
    except Exception:  # noqa: BLE001
        return texte
    from dalila.traitement.registre import appeler
    for e in sorted(entites, key=lambda e: -e["start"]):
        nom = texte[e["start"]:e["end"]]
        if len(nom.strip()) < 2 or appeler("resoudre_lieu", {"texte": nom[:100]}).get("lieux"):
            continue  # un lieu (zone, gouvernorat) n'est pas une personne
        texte = texte[:e["start"]] + "[nom masqué]" + texte[e["end"]:]
    return texte


def nettoyer_entree(message, historique=()):
    """-> (message, historique) bornés et masqués. Seuls les rôles user/assistant sont gardés de l'historique."""
    message = masquer((message or "").strip()[:LONGUEUR_MAX])
    propre = [{"role": h["role"], "content": masquer(str(h.get("content", ""))[:2000])}
              for h in list(historique or [])[-HISTORIQUE_MAX:]
              if isinstance(h, dict) and h.get("role") in ("user", "assistant")]
    return message, propre


# ---------------------------------------------------------------- ancrage des nombres et des balises
_ARABES = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NOMBRE = re.compile(r"\d+(?:[   ]\d{3})*(?:[.,]\d+)?")
_PUCE = re.compile(r"(?m)^\s*\d{1,2}[.)]\s")
# un chiffre seul collé à des lettres est une lettre en arabizi (« wa7ed », « 9addech », « 3andi ») : pas un nombre
_CHIFFRE_LETTRE = re.compile(r"(?<=[^\W\d_])\d(?![\d.,   ])|(?<![\d.,   ])\d(?=[^\W\d_])")
_BALISE = re.compile(r"\[\[(ZONE|LOT):([^:\]]+):[^\]]*\]\]")
_PDF = re.compile(r"\[\[PDF:(.+?):([^:\]]*)\]\]")


def _valeurs(jeton):
    """Un nombre écrit -> ses lectures possibles : groupé (« 1 000 » = 1000) et chaque bloc séparé."""
    plein = re.sub(r"[   ]", "", jeton).replace(",", ".")
    blocs = re.split(r"[   ]", jeton)
    return {_norm(plein)}, {_norm(b.replace(",", ".")) for b in blocs}


def _norm(s):
    try:
        x = float(s)
    except ValueError:
        return s
    return int(x) if x == int(x) else round(x, 2)


def nombres(texte):
    texte = _CHIFFRE_LETTRE.sub("x", _PUCE.sub(" ", str(texte).translate(_ARABES)))
    return [_valeurs(j) for j in _NOMBRE.findall(texte)]


def _connus(resultats, question):
    """Tous les nombres présents dans les résultats d'outils (valeurs et textes) et dans la question."""
    connus = set()

    def visiter(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            connus.add(_norm(v))
            connus.add(_norm(round(v, 1)))
            connus.add(_norm(round(v)))
        elif isinstance(v, str):
            for plein, blocs in nombres(v):
                connus.update(plein | blocs)
        elif isinstance(v, dict):
            for x in v.values():
                visiter(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                visiter(x)

    visiter(resultats)
    for plein, blocs in nombres(question):
        connus.update(plein | blocs)
    return connus


def verifier_ancrage(reponse, resultats, question=""):
    """-> {"ok": bool, "nombres_inconnus": [...], "balises_inconnues": [...]}.
    resultats : liste des résultats d'outils (dicts) de ce tour. Les petits entiers (0 à 5) sont admis : énumérations."""
    connus = _connus(resultats, question)
    sans_balises = _PDF.sub(" ", _BALISE.sub(" ", reponse))
    inconnus = []
    for plein, blocs in nombres(sans_balises):
        n = next(iter(plein))
        if isinstance(n, int) and 0 <= n <= 5:
            continue
        if plein & connus or blocs <= connus:
            continue
        inconnus.append(n)
    texte_outils = json.dumps(resultats, ensure_ascii=False)
    balises = [f"{t}:{i}" for t, i in _BALISE.findall(reponse) if f'"{i.strip()}"' not in texte_outils
               and f": {i.strip()}," not in texte_outils and f": {i.strip()}}}" not in texte_outils]
    balises += [f"PDF:{u}" for u, _ in _PDF.findall(reponse) if u.strip() not in texte_outils]
    return {"ok": not inconnus and not balises, "nombres_inconnus": inconnus, "balises_inconnues": balises}
