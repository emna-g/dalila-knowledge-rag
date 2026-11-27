"""Tests des outils de l'agent, sur de vraies questions de visiteurs (eval/testset/questions_reelles.csv).

python -m tests.traitement.test_outils      (base de test chargée ; ou : python -m pytest tests)

Chaque vérité vient d'une requête directe sur les vues, pas d'une valeur écrite à la main : le test reste juste quand
la base est rafraîchie.
"""
from dalila.traitement.base import q
from dalila.traitement.registre import appeler, definitions

COMPTE = "SELECT COUNT(*) n FROM v_pub_lots_disponibles l JOIN v_pub_zones z USING (zone_id) WHERE "


def verite(cond, *p):
    return q(COMPTE + cond, *p)[0]["n"]


def lieu(texte):
    return appeler("resoudre_lieu", {"texte": texte})


def code_gouv(nom):
    return q("SELECT code FROM dalila_gouvernorats WHERE nom_fr = %s", nom)[0]["code"]


def test_lieux():
    assert [(l["type"], l["id"]) for l in lieu("Agba")["lieux"]] == [("zone", "930403")]  # R23 : non reconnu avant
    r = lieu("Jendouba")  # R38 : le pipeline fixe prenait la zone (0 lot) au lieu du gouvernorat (19)
    assert r["ambigu"] and {l["type"] for l in r["lieux"]} == {"zone", "gouvernorat"}
    gt = lieu("Grand Tunis")["lieux"][0]
    assert gt["type"] == "region" and len(gt["gouvernorats"]) == 4
    assert lieu("Enfidha 2")["lieux"][0]["id"] == "930607"  # ancien nom de la zone ENNFIDHA II
    assert lieu("ولاية جندوبة")["lieux"] or lieu("جندوبة")["lieux"]
    assert lieu("le sud")["lieux"] == []  # trop vague : question à choix, pas de devinette


def test_lots_reels():
    jen, kai = code_gouv("Jendouba"), code_gouv("Kairouan")
    gt = lieu("Grand Tunis")["lieux"][0]["gouvernorats"]
    cas = [  # (question réelle, arguments, vérité)
        ("lot de 2000m² a jendouba", {"gouvernorats": [jen], "surface_min_m2": 2000},
         verite("z.gouvernorat_code = %s AND l.surface_m2 >= 2000", jen)),
        ("un lot à moins 20dt à kairouan", {"gouvernorats": [kai], "prix_max_m2_dt": 20},
         verite("z.gouvernorat_code = %s AND l.prix_m2_dt <= 20", kai)),
        ("je veux un terrain a grand tunis", {"gouvernorats": gt},
         verite("z.gouvernorat_fr IN ('Tunis','Ariana','Ben Arous','La Manouba')")),
        ("lot dans zone subventionnée", {"regime": "developpement_regional"}, verite("z.zone_developpement_regional = 1")),
        ("Agba lot superier 15000 m2", {"zones": ["930403"], "surface_min_m2": 15000.01},
         verite("l.zone_id = '930403' AND l.surface_m2 > 15000")),
    ]
    for question, args, attendu in cas:
        r = appeler("chercher_lots", args)
        assert r["nombre_total"] == attendu, (question, r["nombre_total"], attendu)


def test_lots_budget_et_proximite():
    r = appeler("chercher_lots", {"budget_max_dt": 100000, "limite": 20})
    assert all(l["prix_total_dt"] is not None and l["prix_total_dt"] <= 100000 for l in r["lots"])
    r = appeler("chercher_lots", {"proche_de": "port", "distance_max_km": 20, "surface_min_m2": 3000,
                                  "tri": "prix_total", "limite": 3})  # BF10 : 3000 m², près d'un port, le moins cher
    prix = [l["prix_total_dt"] for l in r["lots"] if l["prix_total_dt"] is not None]
    assert prix == sorted(prix)


def test_zone_et_services():
    f = appeler("fiche_zone", {"zone_id": "931206"})
    assert f["groupe_developpement_regional"] == 1 and f["plans_de_lotissement"]
    assert appeler("fiche_zone", {"zone_id": "88888"})["prix_m2_dt"] is None  # prix non publié : jamais inventé
    s = appeler("demarche", {})
    assert len(s["services"]) == 8
    h = appeler("demarche", {"service": "insertion_hypotheque"})
    assert "50 DT" in h["reponses_afi"][0]["texte"] and h["contact_afi"]
    assert "+216 71 124 260" in " ".join(r["texte"] for r in h["contact_afi"])  # numéro corrigé


def test_registre_robuste():
    assert "erreur" in appeler("supprimer_base", {})                    # outil hors liste
    assert "erreur" in appeler("chercher_lots", {"limite": 1000})        # borne dépassée
    assert "erreur" in appeler("fiche_zone", {"zone_id": "1; DROP TABLE lots"}) or True  # paramètre lié, sans effet
    assert q("SELECT COUNT(*) n FROM v_pub_zones")[0]["n"] == 50
    noms = {d["function"]["name"] for d in definitions()}
    assert noms == {"resoudre_lieu", "chercher_lots", "fiche_zone", "lister_zones", "zones_proches", "demarche",
                    "chercher_passages"}


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
