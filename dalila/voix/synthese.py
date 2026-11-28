"""Texte vers voix (BF8, BNF7) : Piper (licence MIT), local, rapide sur processeur.

    from dalila.voix.synthese import lire
    lire("7 lots disponibles à Jendouba...", lang="fr") -> octets WAV, ou None si aucune voix ne convient

Voix (modeles/piper/, téléchargées par `python -m piper.download_voices`) : français, anglais, allemand, turc, arabe.
BF8 : le tunisien, sans voix adaptée, est lu par la voix arabe, EN LE SIGNALANT (lire_avec_note
rend la note, l'API la met dans l'en-tête X-Dalila-Lecture) ; l'arabizi est d'abord converti en lettres arabes
(dictionnaire du lexique tunisien, cahier des charges : « l'arabizi doit être converti en lettres arabes avant la
synthèse vocale »). Les mots français mêlés restent tels quels. Avant lecture, les balises de la carte sont remplacées
par leur libellé, les liens retirés, les unités dites en mots.
"""
import io, re, threading, wave
from dalila.config import MODELES

VOIX = {"fr": "fr_FR-siwis-medium", "en": "en_US-ljspeech-medium", "de": "de_DE-thorsten-medium",
        "tr": "tr_TR-dfki-medium", "ar": "ar_JO-kareem-medium"}
DIALECTES_ARABES = {"aeb", "tn"}
UNITES = {  # ce que la voix doit dire à la place des symboles
    "fr": [("DT/m²", " dinars le mètre carré"), ("m²", " mètres carrés"), ("m2", " mètres carrés"), ("DT", " dinars"), ("km", " kilomètres")],
    "en": [("DT/m²", " dinars per square meter"), ("m²", " square meters"), ("m2", " square meters"), ("DT", " dinars"), ("km", " kilometers")],
    "de": [("DT/m²", " Dinar pro Quadratmeter"), ("m²", " Quadratmeter"), ("m2", " Quadratmeter"), ("DT", " Dinar"), ("km", " Kilometer")],
    "tr": [("DT/m²", " dinar metrekare başına"), ("m²", " metrekare"), ("m2", " metrekare"), ("DT", " dinar"), ("km", " kilometre")],
    "ar": [("DT/m²", " دينار للمتر المربع"), ("م²", " متر مربع"), ("m²", " متر مربع"), ("DT", " دينار"), ("km", " كيلومتر")],
}
_voix, _verrou = {}, threading.Lock()


def _arabe(texte):
    lettres = [c for c in texte if c.isalpha()]
    return bool(lettres) and sum("؀" <= c <= "ۿ" for c in lettres) / len(lettres) > 0.3


def voix_pour(lang, texte):
    """Code de voix pour la langue donnée par l'interface ; sans langue, l'écriture du texte décide (arabe ou français)."""
    code = (lang or "").strip().lower()
    if code in DIALECTES_ARABES:
        return "ar" if _arabe(texte) else None  # arabizi : pas de voix
    if code[:2] in VOIX:
        return code[:2]
    return "ar" if _arabe(texte) else "fr"


def texte_a_lire(texte, code):
    t = re.sub(r"\[\[(?:ZONE|LOT):[^:\]]*:([^\]]*)\]\]", r"\1", texte)   # [[LOT:5200:A30]] -> A30
    t = re.sub(r"\[\[CHOIX:([^\]]*)\]\]", r"\1.", t)
    t = re.sub(r"\[\[PDF:.*?\]\]", "", t)
    t = t.replace("[[DEMANDE]]", "")                                       # bouton de l'interface (BF11) : pas lu
    t = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", "", t)                    # sources : affichées, pas lues
    t = re.sub(r"https?://\S+", "", t)
    for symbole, mots in UNITES.get(code, []):
        t = re.sub(r"(?<=\d)\s*" + re.escape(symbole) + r"(?![\w²])", mots, t)
    t = re.sub(r"(?<=\d) (?=\d{3}\b)", "", t)                                # « 92 928 » : un seul nombre
    t = t.replace("·", ",").replace("- ", "").replace("*", "")
    return re.sub(r"\s+", " ", t).strip()


def _charger(code):
    with _verrou:
        if code not in _voix:
            from piper import PiperVoice
            _voix[code] = PiperVoice.load(str(MODELES / "piper" / f"{VOIX[code]}.onnx"))
        return _voix[code]


_normaliseur = {}
NOTE_DIALECTE = "dialecte lu avec la voix arabe standard (pas de voix {nom} disponible)"
NOMS = {"tn": "tunisienne", "aeb": "tunisienne"}


def _en_lettres_arabes(texte):
    with _verrou:
        if "n" not in _normaliseur:
            from dalila.langue.lexique.outils.normaliser import NormaliseurTunisien
            _normaliseur["n"] = NormaliseurTunisien()
    return _normaliseur["n"].en_arabe(texte)


def lire_avec_note(texte, lang=None):
    """-> (octets WAV ou None, note à montrer au visiteur ou None). Le dialecte vient de l'interface, sinon de la langue
    détectée dans le texte lui-même."""
    code = (lang or "").strip().lower()
    if code not in DIALECTES_ARABES:
        try:
            from dalila.langue.detection import detecter
            d = detecter(texte).get("langue")
            code = d if d in DIALECTES_ARABES else code
        except Exception:  # noqa: BLE001  (détection absente : la langue de l'interface décide)
            pass
    note = None
    if code in DIALECTES_ARABES:
        if not _arabe(texte):
            texte = _en_lettres_arabes(texte)
        note = NOTE_DIALECTE.format(nom=NOMS.get(code, "dialectale"))
        code = "ar"
    return lire(texte, code), note


def lire(texte, lang=None):
    code = voix_pour(lang, texte)
    if code is None:
        return None
    a_lire = texte_a_lire(texte, code)
    if not a_lire:
        return None
    sortie = io.BytesIO()
    with wave.open(sortie, "wb") as w:
        _charger(code).synthesize_wav(a_lire, w)
    return sortie.getvalue()
