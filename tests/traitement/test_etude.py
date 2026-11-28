"""Test de l'étude de projet guidée (cahier des charges : BF4, cas d'utilisation 7) : 10 questions, puis le PDF.

python -m tests.traitement.test_etude      (base de test chargée)
"""
from dalila.config import db
from dalila.traitement import etude

SESSIONS = ("test-etude-fr", "test-etude-ar", "test-etude-arret")


def _nettoyer():
    con = db("root")
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM agent_sessions WHERE session_id IN (%s, %s, %s)", SESSIONS)
    finally:
        con.close()


def test_entretien_et_pdf():
    _nettoyer()
    try:
        for s, lang, reponses in (
                ("test-etude-fr", "fr", ["transformation d'huile d'olive", "huile en bouteille", "Sfax", "1 000 à 3 000 m²",
                                         "1 à 15 millions DT", "11 à 50", "En partie", "Port", "Rien de particulier",
                                         "Dans 6 à 12 mois"]),
                ("test-etude-ar", "tn", ["تحويل الأسماك", "معلبات", "صفاقس", "من 3000 إلى 10000 م²", "أقل من مليون دينار",
                                         "من 11 إلى 50", "نعم، كليا", "ميناء", "لا شيء خاص", "خلال أقل من 6 أشهر"])):
            r = etude.commencer(s, lang, reponses[0])
            assert "1/10" in r["message"] and etude.en_cours(s)
            for i, x in enumerate(reponses):
                r = etude.repondre(s, x)
                assert ("10/10" in r["message"]) == (i == 8) or r["fin"]
            assert r["fin"] and r["pdf"] and not etude.en_cours(s)
            p = etude.chemin_pdf(r["pdf"].split("/")[-1][:-4])
            assert p and p.read_bytes()[:5] == b"%PDF-"
        assert etude.langue_etude("tn", "تحويل الأسماك") == "ar" and etude.langue_etude("tn", "n7eb usine") == "fr"
        etude.commencer("test-etude-arret", "fr")
        assert etude.repondre("test-etude-arret", "Arrêter l'étude")["fin"] and not etude.en_cours("test-etude-arret")
        assert etude.chemin_pdf("../../.env") is None            # seul un jeton d'étude donne un fichier
    finally:
        _nettoyer()


if __name__ == "__main__":
    test_entretien_et_pdf()
    print("ok test_entretien_et_pdf")
