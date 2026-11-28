"""Tests de la voix (BF7, BF8, BNF3, BNF7, BNF8). Modèles dans modeles/ (Whisper small, voix Piper).

python -m tests.voix.test_voix
"""
import time
from dalila.voix import reconnaissance, synthese


def test_texte_a_lire():
    t = synthese.texte_a_lire("7 lots. 2 904 m² à 32 DT/m².\n- [[LOT:5200:A30]] Zone · [[CHOIX:Tunis]] "
                              "[[PDF:https://x/y.pdf:Plan]] [AFI](https://www.afi.nat.tn/) [[DEMANDE]]", "fr")
    assert "[[" not in t and "DEMANDE" not in t and "http" not in t and "A30" in t and "Tunis" in t  # balises lues par leur libellé
    assert "2904 mètres carrés" in t and "32 dinars le mètre carré" in t      # unités dites en mots


def test_dialecte_lu_en_arabe_et_signale():
    """BF8 : un dialecte sans voix adaptée est lu en arabe, en le signalant ; l'arabizi est d'abord converti."""
    wav, note = synthese.lire_avec_note("Fama 2 lots disponibles fi Sfax.", "tn")
    assert wav and wav[:4] == b"RIFF" and "arabe" in note
    wav, note = synthese.lire_avec_note("Ma famech lots disponibles fi Sousse b hal chourout.", "fr")  # détecté
    assert wav and note
    assert synthese.lire_avec_note("7 lots disponibles à Jendouba.", "fr")[1] is None   # français : aucune note


def test_voix_pour():
    assert synthese.voix_pour("aeb", "Fama 2 lots fi Sfax") is None      # arabizi non converti : pas de voix
    assert synthese.voix_pour("aeb", "فما زوز مقاسم في صفاقس") == "ar"   # tunisien en lettres arabes : voix arabe
    assert synthese.voix_pour("de", "x") == "de" and synthese.voix_pour(None, "مرحبا") == "ar"


def test_aller_retour_et_delai():
    """Une réponse lue puis reconnue : même langue, dans le délai de 4 s (BNF3)."""
    for lang, texte in (("fr", "Je cherche un lot industriel à Jendouba."), ("ar", "أبحث عن مقسم صناعي في صفاقس")):
        wav = synthese.lire(texte, lang)
        assert wav and wav[:4] == b"RIFF"
        reconnaissance.transcrire(wav, lang)  # chargement du modèle, non compté
        t = time.time()
        r = reconnaissance.transcrire(wav, lang)
        assert time.time() - t < 4 and r["langue"] == lang and r["texte"], r


def test_audio_invalide():
    for mauvais in (b"", b"pas de l'audio", b"x" * (reconnaissance.TAILLE_MAX + 1)):
        try:
            reconnaissance.transcrire(mauvais)
            assert False, "audio invalide accepté"
        except reconnaissance.AudioInvalide:
            pass


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
