"""Intégration des outils avec des données et un graphe AFI initialisés.

Requires a dedicated MariaDB test database loaded with the AFI schema, targeted
migrations, references and corpus, plus the generated ontology/store for graph
tests. Never point this module at a database containing data to preserve.
It is intentionally excluded from the offline/unit test command.

Questions: eval/testset/questions_reelles.csv. Each expected count is queried
from the live public views, not hard-coded.

Chaque vérité vient d'une requête directe sur les vues, pas d'une valeur écrite à la main : le test reste juste quand
la base est rafraîchie.
"""
import os

import pytest

_test_db = os.environ.get("DALILA_TEST_DB_NAME")
if not _test_db:
    pytest.skip("Set DALILA_TEST_DB_NAME to run AFI integration tests", allow_module_level=True)
if not _test_db.startswith("dalila_test_"):
    raise RuntimeError("DALILA_TEST_DB_NAME must name an isolated schema prefixed with 'dalila_test_'")
os.environ["DB_NAME"] = _test_db

from dalila.traitement.base import q
from dalila.traitement.registre import appeler, definitions
from dalila.traitement.references import gouvernorats_par_code

COMPTE = "SELECT COUNT(*) n FROM v_pub_lots_disponibles l JOIN v_pub_zones z USING (zone_id) WHERE "


def verite(cond, *p):
    return q(COMPTE + cond, *p)[0]["n"]


def lieu(texte):
    return appeler("resoudre_lieu", {"texte": texte})


def code_gouv(nom):
    return next(code for code, gouv in gouvernorats_par_code().items() if gouv["nom_fr"] == nom)


def test_lieux():
    assert [(l["type"], l["id"]) for l in lieu("Agba")["lieux"]] == [("zone", "930403")]  # R23 : non reconnu avant
    r = lieu("Jendouba")  # R38 : le pipeline fixe prenait la zone (0 lot) au lieu du gouvernorat (19)
    assert not r["ambigu"] and r["lieux"][0]["type"] == "gouvernorat" and r["lieux"][1]["type"] == "zone"
    assert lieu("ولاية جندوبة")["lieux"][0]["type"] == "gouvernorat"  # R39 : le nom est dans un texte plus long
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
         verite("z.gouvernorat_code IN (" + ",".join(["%s"] * len(gt)) + ")", *gt)),
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


def test_manques_combles():
    g = appeler("fiche_zone", {"zone_id": "88888"})       # prix absent de la base : dernier prix publié par l'AFI, sourcé
    assert g["prix_m2_dt"] is None and g["prix_m2_dernier_publie_dt"] == 50 and "ancienne carte" in g["prix_dernier_publie_source"]
    assert appeler("fiche_zone", {"zone_id": "930601"})["prix_m2_dernier_publie_dt"] is None  # Sousse I : aucune source
    k = appeler("fiche_zone", {"zone_id": "931804"})       # El Kef Extension : deux publications de l'AFI en désaccord
    assert k["prix_m2_dt"] == 32 and k["prix_site_afi"] == 118 and k["prix_en_conflit"]
    h = appeler("fiche_zone", {"zone_id": "931005"})       # prix subventionné du site de l'AFI (groupe 1 : 35 % du prix)
    assert h["prix_m2_subventionne_dt"] == 13.3 and h["groupe_developpement_regional"] == 1
    b = appeler("fiche_zone", {"zone_id": "9302051"})      # surface aménagée calculée à partir des contours AFI
    assert b["surface_amenagee_m2"] is None and 400000 < b["surface_amenagee_calculee_m2"] < 560000
    r = appeler("chercher_lots", {"gouvernorats": [7], "budget_max_dt": 200000})  # Gabès : lots trouvés grâce au dernier prix
    assert r["nombre_total"] > 0 and all("dernier prix" in l["prix_selon"] for l in r["lots"])
    s = appeler("demarche", {"service": "mainlevee"})
    assert "PDG" in s["lieu_depot"] and "Chott Mariem" in s["lieu_depot"] and s["non_publie_par_afi"] is None


def test_graphe():
    r = appeler("relier_concepts", {"texte": "La banque me demande un papier pour mon prêt"})  # exemple BF22
    assert r["services_afi"] == ["insertion_hypotheque"]
    assert "Eau" not in [c["libelle"] for c in r["concepts"]]  # « me » n'est pas un concept
    p = appeler("conseiller", {"secteur": "pêche et élevage de poissons"})  # exemple BF20
    assert p["secteurs"] == ["Pêche et aquaculture"] and "APIA" in [o["id"] for o in p["organismes"]]
    assert p["infrastructures_utiles"] == ["port"]
    h = appeler("conseiller", {"secteur": "hôtel touristique"})
    assert "ONTT" in [o["id"] for o in h["organismes"]]
    t = appeler("conseiller", {"secteur": "transformation de poisson"})
    assert "poisson" in t["activites"][0]["libelle"].lower()
    assert all(o["role"] for o in t["organismes"])  # chaque organisme a son rôle sourcé (seuil, secteur)


def test_registre_robuste():
    assert "erreur" in appeler("supprimer_base", {})                    # outil hors liste
    assert "erreur" in appeler("chercher_lots", {"limite": 1000})        # borne dépassée
    assert appeler("fiche_zone", {"zone_id": "1; DROP TABLE lots"}) == {"resultat": None}
    assert q("SELECT COUNT(*) n FROM v_pub_zones")[0]["n"] == 50
    noms = {d["function"]["name"] for d in definitions()}
    assert noms == {"relier_concepts", "conseiller", "resoudre_lieu", "chercher_lots", "fiche_zone", "lister_zones",
                    "zones_proches", "demarche", "chercher_passages"}


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
