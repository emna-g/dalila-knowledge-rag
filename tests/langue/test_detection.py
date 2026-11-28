"""Test de la détection de langue (BF1), sur le test d'acceptation du cahier des charges et une phrase par langue.

python -m tests.langue.test_detection      (modeles/langue_latin.joblib : python -m dalila.langue.entrainer_detection)
"""
from dalila.langue.detection import detecter


def test_acceptation_bf1():
    d = detecter("n7eb terrain f Sfax")                     # test d'acceptation du cahier des charges
    assert d["langue"] == "tn" and d["ecriture"] == "latin", d


def test_une_phrase_par_langue():
    cas = {"Je cherche un lot industriel à Sousse": "fr", "I am looking for an industrial plot in Sousse": "en",
           "Ich suche ein Industriegrundstück in Sousse": "de", "Sousse'de sanayi arsası arıyorum": "tr",
           "أبحث عن مقسم صناعي في ولاية سوسة": "ar", "نحب مقسم صناعي في صفاقس": "tn"}
    faux = {t: (a, detecter(t)["langue"]) for t, a in cas.items() if detecter(t)["langue"] != a}
    assert len(faux) <= 1, faux                              # une erreur tolérée sur six (mesure : eval/reports)


def test_algerien_et_libyen_plus_proposes():
    """Algérien et libyen abandonnés (2026-11-28) : jamais rendus ; la réponse se fait en tunisien ou en arabe."""
    for t in ("rani n9aleb 3la terrain f Sétif", "wach kayen terrain disponible f Annaba?",
              "نبي قطعة أرض صناعية في طرابلس", "شن الأوراق اللي لازمة باش نشري قطعة أرض؟"):
        assert detecter(t)["langue"] in ("tn", "ar"), (t, detecter(t))


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
