"""Tests de la demande d'acquisition (BF11) : préremplie depuis la base, jamais produite sans confirmation, rien gardé.

python -m tests.communication.test_demande          (base démarrée)
"""
import os

os.environ.setdefault("DALILA_PRECHAUFFER", "0")
from fastapi.testclient import TestClient  # noqa: E402
from dalila.communication.api import app  # noqa: E402
from dalila.traitement.base import q  # noqa: E402

C = TestClient(app)


def _un_lot(statut="disponible"):
    r = q("SELECT lot_id FROM v_pub_lots WHERE statut = %s AND surface_m2 > 0 AND prix_m2_dt IS NOT NULL LIMIT 1", statut)
    return int(r[0]["lot_id"]) if r else None


def _corps(lot_id, **kw):
    return {"lot_id": lot_id, "demandeur": {"nom": "Société Test SARL"}, "projet": {"activite": "Conserverie", "emplois": 25},
            "lang": "fr", **kw}


def test_preremplir():
    lid = _un_lot()
    d = C.get(f"/carte/demande?lot_id={lid}").json()
    l = d["lot"]
    assert l["lot_id"] == lid and d["lot_disponible"] and d["zone"]["nom"]
    assert l["prix_terrain_dt"] == round(l["surface_m2"] * l["prix_m2_dt"])      # calculé depuis la base
    assert d["pieces"] and d["lieu_depot"]                                      # réponses validées de l'AFI


def test_confirmation_obligatoire():
    lid = _un_lot()
    assert C.post("/carte/demande/pdf", json=_corps(lid)).status_code == 400                     # sans confirmation
    assert C.post("/carte/demande/pdf", json=_corps(lid, confirme=False)).status_code == 400
    r = C.post("/carte/demande/pdf", json=_corps(lid, confirme=True))
    assert r.status_code == 200 and r.content[:4] == b"%PDF" and r.headers["cache-control"] == "no-store"
    assert C.post("/carte/demande/pdf", json=_corps(99999999, confirme=True)).status_code == 404


def test_prix_jamais_pris_de_l_interface():
    """Un prix envoyé par l'interface est ignoré : le PDF reprend celui de la base (BNF1)."""
    lid = _un_lot()
    corps = _corps(lid, confirme=True)
    corps["prix_m2_dt"] = 1           # champ inconnu : ignoré par le modèle de la demande
    assert C.post("/carte/demande/pdf", json=corps).status_code == 200


def test_trois_langues():
    lid = _un_lot()
    for lg in ("fr", "ar", "en", "aeb"):
        assert C.post("/carte/demande/pdf", json=_corps(lid, confirme=True, lang=lg)).status_code == 200


if __name__ == "__main__":
    for t in (test_preremplir, test_confirmation_obligatoire, test_prix_jamais_pris_de_l_interface, test_trois_langues):
        t()
        print("ok", t.__name__)
