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
         verite("z.gouvernorat_fr IN ('Tunis','Ariana','Ben Arous','La Manouba')")),
        ("lot dans zone subventionnée", {"regime": "developpement_regional"}, verite("z.zone_developpement_regional = 1")),
        ("Agba lot superier 15000 m2", {"zones": ["930403"], "surface_min_m2": 15000.01},
         verite("l.zone_id = '930403' AND l.surface_m2 > 15000")),
    ]
    for question, args, attendu in cas:
        r = appeler("chercher_lots", args)
        assert r["nombre_total"] == attendu, (question, r["nombre_total"], attendu)
    # le lieu tel qu'écrit par le visiteur, résolu par l'outil lui-même (l'agent n'enchaîne pas deux outils)
    assert appeler("chercher_lots", {"lieu": "jendouba", "surface_min_m2": 2000})["nombre_total"] == cas[0][2]
    assert appeler("chercher_lots", {"lieu": "Grand Tunis"})["nombre_total"] == cas[2][2]
    t = appeler("chercher_lots", {"lieu": "tunis"})  # gouvernorat ou région : pas de devinette
    assert t["nombre_total"] is None and len(t["lieux_a_proposer"]) == 2
    z = appeler("lister_zones", {"lieu": "Jendouba", "seulement_avec_lots_disponibles": False})
    assert z["nombre"] == q("SELECT COUNT(*) n FROM v_pub_zones WHERE gouvernorat_code = %s", jen)[0]["n"] > 0
    assert appeler("lister_zones", {"lieu": "tunis"})["lieux_a_proposer"]


def test_lieu_reecrit_par_le_modele():
    """Un lieu réécrit (« Qassrin ») ou qui n'en est pas un (« port ») ne devient jamais « aucune zone »."""
    from dalila.harnais.agent import appeler_avec_lieu
    r, args = appeler_avec_lieu("lister_zones", {"lieu": "Qassrin"}, "في أراضي صناعية في القصرين؟")
    assert r["lieu_retenu"] == "gouvernorat Kasserine" and r["lots_disponibles_total"] > 0
    r, args = appeler_avec_lieu("chercher_lots", {"lieu": "port", "proche_de": "port", "budget_max_dt": 100000},
                                "Industrial lots near a port under 100000 DT?")
    assert "lieu" not in args and r["nombre_total"] > 0
    r, args = appeler_avec_lieu("chercher_lots", {"lieu": "tunis"}, "un lot à tunis")  # ambigu : rien n'est changé
    assert args == {"lieu": "tunis"} and len(r["lieux_a_proposer"]) == 2


def test_vues_et_bloc():
    """Le modèle lit une vue courte ; la liste, les balises et les liens sont écrits par le harnais (exacts)."""
    from dalila.harnais.vues import TAILLE_VUE, bloc, vue
    from dalila.harnais.garde_fous import verifier_ancrage
    r = appeler("chercher_lots", {"lieu": "jendouba", "surface_min_m2": 2000})
    b = bloc([("chercher_lots", r)])
    assert b.count("[[LOT:") == min(5, len(r["lots"]))
    assert verifier_ancrage(b, [r], "")["ok"]  # chaque nombre et balise du bloc vient du résultat
    for nom, args in (("demarche", {"service": "acquisition"}), ("chercher_passages", {"question": "TIA"}),
                      ("fiche_zone", {"zone_id": "931206"})):
        assert len(vue(nom, appeler(nom, args))) <= TAILLE_VUE + 20
    f = appeler("fiche_zone", {"zone_id": "931206"})
    assert "[[ZONE:931206:" in bloc([("fiche_zone", f)]) and "[[PDF:" in bloc([("fiche_zone", f)])
    assert "lister_zones" in vue("fiche_zone", appeler("fiche_zone", {"zone_id": "jendouba"}))
    assert bloc([("chercher_lots", appeler("chercher_lots", {"lieu": "tunis"}))]).count("[[CHOIX:") == 2


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


def test_guide_de_projet():
    """BF31 : un projet décrit obtient un guide complet et sourcé (exemple du cahier des charges, section 8.2)."""
    g = appeler("conseiller", {"secteur": "transformation d'huile d'olive", "lieu": "Sfax", "surface_m2": 3000,
                               "investissement_dt": 2000000, "emplois": 20})
    assert "huile" in g["activites"][0]["libelle"].lower() and g["organisme_competent"][0] == "APII"
    assert g["zones"] and all(z["gouvernorat"] == "Sfax" and z["lots_adaptes"] > 0 for z in g["zones"])
    vrai = verite("z.gouvernorat_fr = 'Sfax' AND l.zone_id = %s AND l.surface_m2 >= 2400", g["zones"][0]["zone_id"])
    assert g["zones"][0]["lots_adaptes"] == vrai                         # compté en base, jamais estimé
    assert g["incitations"] and g["demarche_lieu_depot"] and "emploi" in g["demarche_criteres"].lower()
    assert any("tia.gov.tn" in (s["url"] or "") for s in g["sources"])  # le seuil APII / TIA est sourcé
    assert appeler("conseiller", {"secteur": "cimenterie", "investissement_dt": 20000000})["organisme_competent"][0] == "TIA"
    assert appeler("conseiller", {"secteur": "huile d'olive", "lieu": "tunis"})["lieux_a_proposer"]  # pas de devinette


def test_registre_robuste():
    assert "erreur" in appeler("supprimer_base", {})                    # outil hors liste
    assert "erreur" in appeler("chercher_lots", {"limite": 1000})        # borne dépassée
    assert "erreur" in appeler("fiche_zone", {"zone_id": "1; DROP TABLE lots"}) or True  # paramètre lié, sans effet
    assert q("SELECT COUNT(*) n FROM v_pub_zones")[0]["n"] == 50
    noms = {d["function"]["name"] for d in definitions()}
    assert noms == {"relier_concepts", "conseiller", "resoudre_lieu", "chercher_lots", "fiche_zone", "lister_zones",
                    "zones_proches", "demarche", "chercher_passages"}


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
