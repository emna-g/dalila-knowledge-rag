"""Tests des routes d'administration (BF12, BF15, BF21) : accès, état des sources, journal et « Annuler ».

python -m tests.communication.test_admin

Les tests avec la base posent des données de test (puis les effacent) ; sans base, ils sont sautés et le disent.
"""
import datetime as dt, json, os

os.environ.setdefault("DALILA_PRECHAUFFER", "0")
from fastapi.testclient import TestClient  # noqa: E402
from dalila.communication.api import app  # noqa: E402
from dalila.communication.admin import etat_source, ligne_journal  # noqa: E402
from dalila.config import db  # noqa: E402

LOCAL = TestClient(app)                                  # depuis le serveur lui-même
DISTANT = TestClient(app, client=("10.1.2.3", 50000))    # depuis une autre machine
SESSION = "test-admin"
ALIAS = "Qassrinn-admin-test"


def test_acces():
    os.environ.pop("DALILA_ADMIN_CLE", None)
    assert DISTANT.get("/admin/api/sources").status_code == 403          # sans clé : seulement en local
    assert LOCAL.get("/admin/api/sources").status_code == 200
    os.environ["DALILA_ADMIN_CLE"] = "cle-de-test"
    try:
        assert LOCAL.get("/admin/api/sources").status_code == 401        # avec une clé : même en local, il la faut
        assert DISTANT.get("/admin/api/sources", headers={"X-Cle-Admin": "fausse"}).status_code == 401
        assert DISTANT.get("/admin/api/sources", headers={"X-Cle-Admin": "cle-de-test"}).status_code == 200
    finally:
        os.environ.pop("DALILA_ADMIN_CLE", None)
    assert LOCAL.post("/admin/api/apprentissage/prix/1/annuler").status_code == 404   # rien d'autre ne s'annule


def test_etat_source():
    maintenant = dt.datetime(2026, 11, 28, 12)
    c = {"actif": "1", "delai_jours": "7"}
    ok = {"derniere_tentative": "2026-11-27 10:00:00", "derniere_lecture_ok": "2026-11-27 10:00:00", "echecs_consecutifs": 0}
    assert etat_source(c, ok, maintenant) == "ok"
    assert etat_source({"actif": "0"}, ok, maintenant) == "inactive"
    assert etat_source(c, {}, maintenant) == "jamais_lue"
    assert etat_source(c, dict(ok, echecs_consecutifs=2), maintenant) == "erreur"
    assert etat_source(c, dict(ok, a_relire=True), maintenant) == "a_relire"
    assert etat_source(c, dict(ok, derniere_lecture_ok="2026-11-01 10:00:00"), maintenant) == "en_retard"  # > 2 × 7 j


def test_route_sources():
    d = LOCAL.get("/admin/api/sources").json()
    assert d["total"] == len(d["sources"]) > 0 and sum(d["resume"].values()) == d["total"]
    assert all(s["etat"] in ("ok", "erreur", "a_relire", "en_retard", "jamais_lue", "inactive") for s in d["sources"])


def test_ligne_journal():
    r = {"candidat": 5, "kind": "alias_lieu", "status": "publie", "sessions_preuve": '["a", "b"]',
         "payload": json.dumps({"alias": "Qassrin", "type": "gouvernorat", "cible_nom": "Kasserine"}),
         "checks": '{"lieu_existe": true}', "propose_le": None, "decide_le": None, "revoked_at": None, "revoked_by": None,
         "lieu_id": 9, "lieu_actif": 1, "synonyme_id": None, "synonyme_actif": None}
    l = ligne_journal(r)
    assert (l["genre"], l["terme"], l["conversations"], l["appris_id"], l["annulable"]) == ("lieu", "Qassrin", 2, 9, True)
    assert not ligne_journal(dict(r, lieu_actif=0))["annulable"]          # déjà annulé : plus de bouton


# ---------------------------------------------------------------- avec la base
def _root(sql, *p):
    con = db("root")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            return cur.lastrowid, cur.fetchall()
    finally:
        con.close()


def _nettoyer():
    for (cid,) in [(r["id"],) for r in _root("SELECT id FROM agent_learning_candidates WHERE payload LIKE %s", f"%{ALIAS}%")[1]]:
        _root("DELETE FROM agent_learning_journal WHERE candidate_id = %s", cid)
        _root("DELETE FROM agent_appris_lieux WHERE candidat_id = %s", cid)
        _root("DELETE FROM agent_learning_candidates WHERE id = %s", cid)
    _root("DELETE FROM agent_turns WHERE session_id = %s", SESSION)


def test_avec_la_base():
    _nettoyer()
    try:
        # une question restée sans réponse fiable (deux fois) : en tête des questions mal traitées
        for _ in range(2):
            _root("INSERT INTO agent_turns (session_id, texte_anonymise, langue, source) VALUES (%s, %s, 'fr', 'repli')",
                  SESSION, "question admin de test sans réponse")
        b = LOCAL.get("/admin/api/besoins").json()
        ligne = next(l for l in b if l["question"] == "question admin de test sans réponse")
        assert ligne["posee"] == 2 and ligne["repli"] == 2

        # un nom de lieu publié : visible au journal, puis annulé par l'écran
        cid, _ = _root("INSERT INTO agent_learning_candidates (kind, payload, sessions_preuve, status) VALUES "
                       "('alias_lieu', %s, '[\"s1\", \"s2\"]', 'publie')",
                       json.dumps({"alias": ALIAS, "type": "gouvernorat", "cible_id": "42", "cible_nom": "Kasserine"}))
        lid, _ = _root("INSERT INTO agent_appris_lieux (alias, type, cible_id, candidat_id, actif) VALUES (%s, 'gouvernorat', '42', %s, 1)",
                       ALIAS, cid)
        _root("INSERT INTO agent_learning_journal (candidate_id, checks, decision, graphe_nomme) VALUES (%s, %s, 'publie', %s)",
              cid, '{"lieu_existe": true}', f"agent_appris_lieux/{lid}")
        a = next(x for x in LOCAL.get("/admin/api/apprentissage").json() if x["candidat"] == cid)
        assert a["annulable"] and a["appris_id"] == lid and a["conversations"] == 2
        assert LOCAL.post(f"/admin/api/apprentissage/lieu/{lid}/annuler", json={"par": "test admin"}).json() == {"ok": True}
        a = next(x for x in LOCAL.get("/admin/api/apprentissage").json() if x["candidat"] == cid)
        assert a["statut"] == "annule" and not a["actif"] and not a["annulable"] and a["annule_par"] == "test admin"
        assert LOCAL.post("/admin/api/apprentissage/lieu/999999999/annuler").status_code == 404
    finally:
        _nettoyer()


if __name__ == "__main__":
    for t in (test_acces, test_etat_source, test_route_sources, test_ligne_journal):
        t()
        print("ok", t.__name__)
    try:
        db("rw").close()
    except Exception:  # noqa: BLE001
        print("sauté test_avec_la_base : base injoignable (docker start dalila-db)")
    else:
        test_avec_la_base()
        print("ok test_avec_la_base")
