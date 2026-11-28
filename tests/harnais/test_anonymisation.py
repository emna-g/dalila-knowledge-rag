"""BNF16 : aucun nom, téléphone, CIN ou RNE dans ce qui est gardé et appris.

python -m tests.harnais.test_anonymisation      (modèle de noms téléchargé au premier appel)
"""
from dalila.harnais.garde_fous import anonymiser, masquer, nombres


def test_formats():
    t = masquer("CIN 09876543, tél. 98 123 456, +216 71 124 260, RNE 1234567A, matricule 1234567/A/M/000, a@b.tn")
    for donnee in ("09876543", "98 123 456", "71 124 260", "1234567", "a@b.tn"):
        assert donnee not in t, (donnee, t)
    s = "7 lots, 2 904 m² à 32 DT/m², soit 92 928 DT"           # les chiffres des lots restent (ancrage)
    assert masquer(s) == s and [sorted(p)[0] for p, _ in nombres(s)] == [7, 2904, 32, 92928]


def test_noms_de_personnes():
    cas = {"Bonjour, je suis Mohamed Ben Salah, je veux un lot à Sidi Achour Borj El Amri": ("Mohamed", "Sidi Achour"),
           "أنا فاطمة بن علي من صفاقس": ("فاطمة", "صفاقس"),
           "My name is John Smith, plots in Sousse?": ("John", "Sousse"),
           "Ich heiße Karl Müller und suche ein Grundstück in Bizerte": ("Karl", "Bizerte")}
    for texte, (nom, lieu) in cas.items():
        a = anonymiser(texte)
        assert nom not in a and lieu in a, a                   # le nom part, le lieu reste
    assert anonymiser("lot de 2000m² a jendouba") == "lot de 2000m² a jendouba"


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
