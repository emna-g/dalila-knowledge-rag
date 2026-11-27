"""Tests de la liste pour l'AFI et de l'export vers l'entraînement, sur des tours simulés (puis effacés).

python -m tests.apprentissage.test_besoins_export
"""
import json
from dalila.apprentissage import besoins, exporter
from dalila.config import db

SESSION = "test-besoins-export"


def _root(sql, *p):
    con = db("root")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            return cur.fetchall()
    finally:
        con.close()


def _tour(texte, source, outils=(), reponse=None, avis=None):
    _root("INSERT INTO agent_turns (session_id, texte_anonymise, langue, outils, garde_faits, source, reponse, avis) "
          "VALUES (%s, %s, 'fr', %s, %s, %s, %s, %s)", SESSION, texte, json.dumps(list(outils), ensure_ascii=False),
          "ancre" if source == "dalila" else "repli", source, reponse, avis)


def test_besoins_et_export():
    _root("DELETE FROM agent_turns WHERE session_id = %s", SESSION)
    try:
        jen = {"outil": "lister_zones", "arguments": {"lieu": "Jendouba"}}
        z = __import__("dalila.traitement.registre", fromlist=["appeler"]).appeler("lister_zones", {"lieu": "Jendouba"})
        n = z["lots_disponibles_total"]
        _tour("question test inconnue xyz", "repli")
        _tour("Question test inconnue XYZ ?", "repli")                                     # même question, autre écriture
        _tour("zones de jendouba (test)", "dalila", [jen], f"Il y a {n} lots à Jendouba.", avis=0)
        _tour("les zones à jendouba svp (test)", "dalila", [jen], f"Il y a {n} lots à Jendouba.")  # bon exemple
        _tour("zones jendouba faux (test)", "dalila", [jen], "Il y a 99999 lots à Jendouba.")      # nombre faux
        _tour("lot de 2000m² a jendouba", "dalila", [jen], f"Il y a {n} lots.")                    # question du test
        _tour("zones jendouba rattrapées (test)", "dalila",
              [{**jen, "arguments_modele": {"lieu": "Jandouuba"}}], f"Il y a {n} lots.")
        L = {l["question"]: l for l in besoins.besoins(tout=False)}
        assert L["question test inconnue xyz"]["posee"] == 2 and L["question test inconnue xyz"]["repli"] == 2
        assert L["zones de jendouba (test)"]["pas_utile"] == 1
        assert "les zones à jendouba svp (test)" not in L          # sans problème : pas dans la liste par défaut
        tours = [t for t in exporter._tours() if (t["texte_anonymise"] or "").endswith("(test)")
                 or t["texte_anonymise"] == "lot de 2000m² a jendouba"]
        test = exporter._questions_test()
        res = {t["texte_anonymise"]: exporter.exemple(t, test) for t in tours}
        ex, _ = res["les zones à jendouba svp (test)"]
        assert ex and ex["messages"][-1]["content"].startswith("Il y a") and ex["messages"][2]["tool_calls"]
        assert "zones de jendouba (test)" not in res                # noté « pas utile » : jamais exporté
        assert res["zones jendouba faux (test)"][1].startswith("nombres")
        assert res["lot de 2000m² a jendouba"][1] == "question du jeu de test"
        assert res["zones jendouba rattrapées (test)"][1] == "lieu rattrapé par le harnais"
    finally:
        _root("DELETE FROM agent_turns WHERE session_id = %s", SESSION)


if __name__ == "__main__":
    test_besoins_et_export()
    print("ok test_besoins_et_export")
