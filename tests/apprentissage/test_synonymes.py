"""BF18, BF19, BF21 : un mot d'abord mal compris l'est bien une fois l'apprentissage publié ; annulé, il ne sert plus.

python -m tests.apprentissage.test_synonymes      (conversations simulées, puis effacées)
"""
import json
from dalila.apprentissage import synonymes_appris as S
from dalila.config import db

PREFIXE = "test-synonymes-"
POISSON = "transformation et conservation de poisson"


def _root(sql, *p):
    con = db("root")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            return cur.fetchall()
    finally:
        con.close()


def _tour(session, texte, secteur):
    outils = [{"outil": "conseiller", "arguments": {"secteur": secteur}}]
    S._ecrire("INSERT INTO agent_turns (session_id, texte_anonymise, langue, outils, garde_faits, source) VALUES "
              "(%s, %s, 'tn', %s, 'ancre', 'dalila')", PREFIXE + session, texte, json.dumps(outils, ensure_ascii=False))


def _nettoyer():
    ids = [r["id"] for r in _root("SELECT id FROM agent_learning_candidates WHERE kind = 'synonyme' AND "
                                  "JSON_UNQUOTE(JSON_EXTRACT(payload, '$.terme')) IN ('7out', 'sardine', 'n7eb', 'na3mel', "
                                  "'ma3mel', 'mte3i', 'projet', 'usine', 'plastique', '3andi')")]
    for i in ids:
        _root("DELETE FROM agent_learning_journal WHERE candidate_id = %s", i)
        _root("DELETE FROM agent_appris_synonymes WHERE candidat_id = %s", i)
        _root("DELETE FROM agent_learning_candidates WHERE id = %s", i)
    _root("DELETE FROM agent_turns WHERE session_id LIKE %s", PREFIXE + "%")


def test_apprendre_puis_annuler():
    _nettoyer()
    try:
        poisson = S._activite(POISSON)[0]
        assert S._activite("7out")[0] != poisson                    # d'abord mal compris
        _tour("a", "n7eb na3mel ma3mel 7out", POISSON)
        _tour("b", "3andi projet 7out w sardine", POISSON)
        _tour("c", "sardine, n7eb usine", POISSON)
        _tour("d", "n7eb na3mel ma3mel plastique", "fabrication d'emballages en plastique")
        _tour("e", "3andi projet plastique", "fabrication d'emballages en plastique")
        res = {p["terme"]: (d, c) for p, d, c in S.cycle(tests=False)}
        assert res["7out"][0] == "publie" and res["sardine"][0] == "publie", res
        for commun in ("n7eb", "na3mel", "ma3mel", "3andi", "projet"):  # vus avec plusieurs activités : jamais appris
            assert commun not in res or res[commun][0] != "publie", (commun, res.get(commun))
        assert S._activite("7out")[0] == poisson and S._activite("sardine")[0] == poisson   # bien compris après
        assert not S.cycle(tests=False)                              # rien n'est reproposé
        sid = _root("SELECT id FROM agent_appris_synonymes WHERE terme = '7out'")[0]["id"]
        assert S.annuler(sid, par="test")
        assert S._activite("7out")[0] != poisson                    # annulé : plus utilisé (BF21)
        j = _root("SELECT revoked_by FROM agent_learning_journal WHERE graphe_nomme = %s", f"appris/{sid}")
        assert j and j[0]["revoked_by"] == "test"
    finally:
        _nettoyer()


if __name__ == "__main__":
    test_apprendre_puis_annuler()
    print("ok test_apprendre_puis_annuler")
