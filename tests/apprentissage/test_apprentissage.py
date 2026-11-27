"""Test de la boucle d'apprentissage des noms de lieux, sur des conversations simulées (puis effacées).

python -m tests.apprentissage.test_apprentissage      (base de test chargée ; compte root pour le nettoyage)
"""
import json
from dalila.apprentissage import lieux_appris as A
from dalila.config import db

PREFIXE = "test-apprentissage-"


def _root(sql, *p):
    con = db("root")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            return cur.fetchall()
    finally:
        con.close()


def _tour(session, demande, final):
    outils = [{"outil": "lister_zones", "arguments": {"lieu": final}, "arguments_modele": {"lieu": demande}}]
    A._ecrire("INSERT INTO agent_turns (session_id, texte_anonymise, langue, outils, garde_faits, source) VALUES "
              "(%s, %s, 'ar', %s, 'ancre', 'dalila')", PREFIXE + session, final, json.dumps(outils, ensure_ascii=False))


def _nettoyer():
    ids = [r["id"] for r in _root("SELECT id FROM agent_learning_candidates WHERE JSON_UNQUOTE(JSON_EXTRACT(payload, '$.alias')) "
                                  "IN ('Qassrinn', 'Gabzx 450', 'Bizerrtta')")]
    for i in ids:
        _root("DELETE FROM agent_learning_journal WHERE candidate_id = %s", i)
        _root("DELETE FROM agent_appris_lieux WHERE candidat_id = %s", i)
        _root("DELETE FROM agent_learning_candidates WHERE id = %s", i)
    _root("DELETE FROM agent_turns WHERE session_id LIKE %s", PREFIXE + "%")


def test_boucle():
    _nettoyer()
    try:
        assert A._lieu("Qassrinn") is None                       # inconnu avant
        _tour("a", "Qassrinn", "في أراضي صناعية في القصرين؟")     # le message du visiteur a donné le lieu
        _tour("b", "Qassrinn", "zones industrielles Kasserine")
        _tour("c", "Bizerrtta", "Bizerte")                        # une seule conversation : pas assez (BNF18)
        _tour("d", "Gabzx 450", "Gabès")
        _tour("e", "Gabzx 450", "Gabès")                          # un chiffre : jamais appris
        resultats = {p["alias"]: (d, c) for p, d, c in A.cycle(tests=False)}
        assert resultats["Qassrinn"][0] == "publie", resultats
        assert "Bizerrtta" not in resultats
        assert resultats["Gabzx 450"][0] == "rejete" and not resultats["Gabzx 450"][1]["anonyme_sans_chiffre"]
        assert A._lieu("Qassrinn")[:1] == ("gouvernorat",) and A._lieu("Qassrinn")[2] == "Kasserine"  # appris
        assert not A.cycle(tests=False)                           # rien de nouveau : rien n'est reproposé
        lid = _root("SELECT a.id FROM agent_appris_lieux a JOIN agent_learning_candidates c ON c.id = a.candidat_id "
                    "WHERE a.alias = 'Qassrinn'")[0]["id"]
        assert A.annuler(lid, par="test")
        assert A._lieu("Qassrinn") is None                       # annulé : plus compris
        j = _root("SELECT revoked_by FROM agent_learning_journal WHERE graphe_nomme = %s", f"agent_appris_lieux/{lid}")
        assert j and j[0]["revoked_by"] == "test"                # le journal garde la trace
    finally:
        _nettoyer()


if __name__ == "__main__":
    test_boucle()
    print("ok test_boucle")
