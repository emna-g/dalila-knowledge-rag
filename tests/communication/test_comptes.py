"""Connexion et sessions : on ne passe ni sans compte, ni avec un jeton inventé ou modifié, ni depuis un autre site.

python -m tests.communication.test_comptes      (comptes de test créés puis effacés ; base nécessaire)
"""
import os

os.environ.setdefault("DALILA_PRECHAUFFER", "0")
from fastapi.testclient import TestClient  # noqa: E402
from dalila.communication import comptes as C  # noqa: E402
from dalila.communication.api import app  # noqa: E402
from dalila.config import db  # noqa: E402

ADMIN, AUTRE = "test-admin-comptes", "test-promoteur-comptes"
MOT = "un mot de passe long 42"
ORIGINE = {"Origin": "http://testserver"}
_n = [0]


def client():
    """Un navigateur à part (adresse à part : la limite par adresse ne mélange pas les tests)."""
    _n[0] += 1
    return TestClient(app, client=(f"10.9.0.{_n[0]}", 50000))


def _root(sql, *p):
    con = db("root")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            return cur.fetchall()
    finally:
        con.close()


def _nettoyer():
    _root("DELETE FROM agent_comptes WHERE identifiant IN (%s, %s)", ADMIN, AUTRE)


def _connecte():
    c = client()
    r = c.post("/auth/connexion", json={"identifiant": ADMIN, "mot_de_passe": MOT}, headers=ORIGINE)
    assert r.status_code == 200, r.text
    return c, r


def test_empreinte():
    e = C.empreinte(MOT)
    assert e.startswith("scrypt$") and MOT not in e
    assert C.verifier(MOT, e) and not C.verifier(MOT + "x", e)
    assert C.empreinte(MOT) != e                                   # sel propre à chaque empreinte
    algo, n, r, p, sel, h = e.split("$")
    assert not C.verifier(MOT, "$".join([algo, n, r, p, sel, "A" + h[1:]]))   # empreinte modifiée : refus
    assert not C.verifier(MOT, "n'importe quoi")
    assert not C.mot_admis("court", "x") and not C.mot_admis(ADMIN.upper(), ADMIN)


def test_connexion_et_acces():
    c, r = _connecte()
    assert r.json()["suite"] == "/admin/" and r.json()["role"] == "admin"
    entete = r.headers["set-cookie"].lower()
    assert "httponly" in entete and "samesite=strict" in entete and "path=/" in entete
    jeton = c.cookies.get(C.COOKIE)
    assert jeton and len(jeton) >= 43
    assert _root("SELECT COUNT(*) n FROM agent_jetons WHERE empreinte = %s", jeton)[0]["n"] == 0   # jamais en clair
    assert c.get("/auth/moi").json()["identifiant"] == ADMIN
    assert c.get("/admin/api/sources").status_code == 200


def test_refus():
    anonyme = client()
    assert anonyme.get("/admin/api/sources").status_code == 401                         # sans compte
    mauvais = anonyme.post("/auth/connexion", json={"identifiant": ADMIN, "mot_de_passe": "faux faux faux"}, headers=ORIGINE)
    inconnu = anonyme.post("/auth/connexion", json={"identifiant": "personne-xyz", "mot_de_passe": MOT}, headers=ORIGINE)
    assert mauvais.status_code == inconnu.status_code == 401
    assert mauvais.json() == inconnu.json()                                             # rien ne trahit l'identifiant
    invente = client()
    invente.cookies.set(C.COOKIE, "a" * 43)
    assert invente.get("/admin/api/sources").status_code == 401                         # jeton inventé
    c, _ = _connecte()
    vrai = c.cookies.get(C.COOKIE)
    modifie = client()
    modifie.cookies.set(C.COOKIE, vrai[:-1] + ("A" if vrai[-1] != "A" else "B"))
    assert modifie.get("/admin/api/sources").status_code == 401                         # jeton modifié
    assert c.post("/auth/connexion", json={"identifiant": ADMIN, "mot_de_passe": MOT}).status_code == 403   # sans Origin
    assert c.post("/admin/api/apprentissage/lieu/1/annuler", headers={"Origin": "https://pirate.example"}).status_code == 403
    assert c.post("/admin/api/apprentissage/lieu/999999999/annuler", headers=ORIGINE).status_code == 404   # même site : passe


def test_role():
    _root("INSERT INTO agent_comptes (identifiant, role, mot_de_passe) VALUES (%s, 'promoteur', %s)", AUTRE, C.empreinte(MOT))
    c = client()
    assert c.post("/auth/connexion", json={"identifiant": AUTRE, "mot_de_passe": MOT}, headers=ORIGINE).status_code == 200
    assert c.get("/admin/api/sources").status_code == 403                               # connecté, mais pas admin


def test_fin_de_session():
    c, _ = _connecte()
    jeton = c.cookies.get(C.COOKIE)
    assert c.post("/auth/deconnexion", headers=ORIGINE).json() == {"ok": True}
    rejoue = client()
    rejoue.cookies.set(C.COOKIE, jeton)
    assert rejoue.get("/admin/api/sources").status_code == 401                          # jeton fermé : inutilisable
    for champ, sql in (("expire_le", "NOW() - INTERVAL 1 SECOND"), ("vu_le", f"NOW() - INTERVAL {C.INACTIVITE + 5} SECOND")):
        c, _ = _connecte()
        _root(f"UPDATE agent_jetons SET {champ} = {sql} WHERE empreinte = %s", C._hache(c.cookies.get(C.COOKIE)))
        assert c.get("/admin/api/sources").status_code == 401, champ                    # 8 h dépassées ; 30 min d'inactivité
    c, _ = _connecte()
    C.changer_mot_de_passe(ADMIN, MOT)                                                  # nouveau mot de passe
    assert c.get("/admin/api/sources").status_code == 401                               # : sessions fermées


def test_force_brute():
    c = client()
    for _ in range(C.ECHECS_MAX):
        assert c.post("/auth/connexion", json={"identifiant": ADMIN, "mot_de_passe": "faux faux faux"}, headers=ORIGINE).status_code == 401
    bon = client().post("/auth/connexion", json={"identifiant": ADMIN, "mot_de_passe": MOT}, headers=ORIGINE)
    assert bon.status_code == 429                                                       # bloqué, même avec le bon mot
    _root("UPDATE agent_comptes SET echecs = 0, bloque_jusqu_a = NULL WHERE identifiant = %s", ADMIN)
    meme_adresse = client()
    codes = [meme_adresse.post("/auth/connexion", json={"identifiant": "personne-xyz", "mot_de_passe": "x"}, headers=ORIGINE).status_code
             for _ in range(C.TENTATIVES_PAR_ADRESSE + 1)]
    assert codes[-1] == 429 and codes[0] == 401                                         # limite par adresse


def preparer():
    _nettoyer()
    C.creer(ADMIN, "admin", MOT, nom="Test")


if __name__ == "__main__":
    test_empreinte()
    print("ok test_empreinte")
    preparer()
    try:
        for t in (test_connexion_et_acces, test_refus, test_role, test_fin_de_session, test_force_brute):
            t()
            print("ok", t.__name__)
    finally:
        _nettoyer()
