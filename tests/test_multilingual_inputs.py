import unittest

from dalila.langue.lexique.outils.normaliser import NormaliseurTunisien
from dalila.semantique.comprendre import norm


class MultilingualNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normaliseur = NormaliseurTunisien()

    def test_french_input_is_preserved(self):
        question = "Je cherche un lot à Sfax."
        result = self.normaliseur.analyser(question)
        self.assertFalse(result["tunisien"])
        self.assertEqual(result["requete_pour_rag"], question)

    def test_english_input_is_preserved_for_multilingual_retrieval(self):
        question = "Available industrial lots in Sfax?"
        result = self.normaliseur.analyser(question)
        self.assertFalse(result["tunisien"])
        self.assertEqual(result["requete_pour_rag"], question)

    def test_standard_arabic_input_is_not_mislabeled_as_derja(self):
        question = "ما هي إجراءات اقتناء مقسم صناعي؟"
        result = self.normaliseur.analyser(question)
        self.assertEqual(result["ecriture"], "arabe")
        self.assertFalse(result["tunisien"])
        self.assertEqual(result["requete_pour_rag"], question)

    def test_derja_in_arabic_script_uses_attested_lexicon(self):
        result = self.normaliseur.analyser("شنوة الأوراق اللازمة باش ناخو مقسم صناعي؟")
        self.assertEqual(result["ecriture"], "arabe")
        self.assertTrue(result["tunisien"])
        self.assertIn("papiers", result["concepts"])

    def test_derja_in_arabizi_uses_attested_lexicon(self):
        result = self.normaliseur.analyser("chnowa lwra9 lazmin bech na5ou ma9sem sina3i?")
        self.assertEqual(result["ecriture"], "arabizi")
        self.assertTrue(result["tunisien"])
        self.assertIn("papiers", result["concepts"])
        self.assertIn("papiers", result["requete_pour_rag"])

    def test_mixed_french_arabizi_and_arabic_script_are_preserved(self):
        question = "n7eb un lot صناعي في Sfax"
        result = self.normaliseur.analyser(question)
        self.assertEqual(result["ecriture"], "mixte")
        self.assertTrue(result["tunisien"])
        self.assertIn("صناعي", result["texte"])
        self.assertIn("Sfax", result["texte"])

    def test_graph_normalization_preserves_arabic_in_mixed_input(self):
        result = norm("Je cherche سوسة في تونس")
        self.assertIn("cherche", result)
        self.assertIn("سوسة", result)
        self.assertIn("تونس", result)


if __name__ == "__main__":
    unittest.main()
