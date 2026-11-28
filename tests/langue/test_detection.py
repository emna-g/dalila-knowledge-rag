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
           "أبحث عن مقسم صناعي في ولاية سوسة": "ar", "نحب مقسم صناعي في صفاقس": "tn",
           "rani n9aleb 3la terrain f Sétif": "dz", "نبي قطعة أرض صناعية في طرابلس": "ly"}
    faux = {t: (a, detecter(t)["langue"]) for t, a in cas.items() if detecter(t)["langue"] != a}
    assert len(faux) <= 1, faux                              # une erreur tolérée sur huit (mesure : eval/reports)


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
