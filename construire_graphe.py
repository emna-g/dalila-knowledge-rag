"""Construit le graphe de connaissances de Dalila (OWL 2 / RDF, export Turtle).

python construire_graphe.py --donnees donnees/dalila_fusion --lexique lexique_tunisien --sortie graphe

Règles (cahier des charges §IV.5, BF16, BNF19) :
- les 9 familles de concepts : Lieu, Lot, Secteur, Commodité/proximité, Démarche, Incitation, Organisme, Projet, Service AFI ;
- le graphe garde seulement le LIEN vers le lot : aucun prix, aucun statut, aucune disponibilité
  (ils restent dans MariaDB et sont lus au moment de répondre) ;
- synonymes = libellés avec balise de langue (skos:prefLabel / skos:altLabel), tunisien = « aeb »
  (aeb-Arab en lettres arabes, aeb-Latn en arabizi), seulement les formes attestées du lexique ;
- chaque fait garde sa source (dcterms:source).
Sorties : graphe/dalila.ttl (ontologie + faits), graphe/rapport_graphe.json (cohérence + requêtes de test).
"""
import argparse, json, csv, pathlib, re, sys, unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "libs"))
from rdflib import Graph, Namespace, Literal, URIRef  # noqa: E402
from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS, DCTERMS  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--donnees", required=True)
ap.add_argument("--lexique", required=True)
ap.add_argument("--sortie", default="graphe")
a = ap.parse_args()
D, LX, OUT = pathlib.Path(a.donnees), pathlib.Path(a.lexique), pathlib.Path(a.sortie)
OUT.mkdir(parents=True, exist_ok=True)

DAL = Namespace("https://dalila.afi.nat.tn/ontologie#")
RES = Namespace("https://dalila.afi.nat.tn/donnees/")
g = Graph()
for p, ns in {"dal": DAL, "res": RES, "skos": SKOS, "dcterms": DCTERMS, "owl": OWL}.items():
    g.bind(p, ns)
SRC_SQL = Literal("base AFI afi.sql (export du 2026-11-13)")
SRC_CDC = Literal("Cahier des charges Hackathon AGENTIC Dalila (2026-11-17)")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def labels(node, fr=None, en=None, ar=None, de=None, tr=None):
    for txt, lang in ((fr, "fr"), (en, "en"), (ar, "ar"), (de, "de"), (tr, "tr")):
        if txt:
            g.add((node, SKOS.prefLabel, Literal(txt, lang=lang)))
    if fr:
        g.add((node, RDFS.label, Literal(fr, lang="fr")))


def cls(name, parent=None, **lab):
    c = DAL[name]
    g.add((c, RDF.type, OWL.Class))
    if parent:
        g.add((c, RDFS.subClassOf, DAL[parent]))
    labels(c, **lab)
    return c


def prop(name, kind, domain=None, rng=None, fr=None):
    p = DAL[name]
    g.add((p, RDF.type, kind))
    if domain:
        g.add((p, RDFS.domain, DAL[domain]))
    if rng is not None:
        g.add((p, RDFS.range, rng if isinstance(rng, URIRef) else DAL[rng]))
    if fr:
        g.add((p, RDFS.label, Literal(fr, lang="fr")))
    return p


# ------------------------------------------------------------------ TBox : les 9 familles
ont = URIRef("https://dalila.afi.nat.tn/ontologie")
g.add((ont, RDF.type, OWL.Ontology))
g.add((ont, RDFS.comment, Literal("Ontologie de Dalila (AFI). Sans prix ni statut : ils restent dans MariaDB.", lang="fr")))
FAM = {  # famille -> libellés fr, en, ar, de, tr (de/tr : traduction des noms de familles, à relire)
    "Lieu": ("Lieu", "Place", "مكان", "Ort", "Yer"),
    "Lot": ("Lot", "Plot", "مقسم", "Grundstück", "Parsel"),
    "SecteurActivite": ("Secteur d'activité", "Business sector", "قطاع النشاط", "Branche", "Faaliyet sektörü"),
    "Commodite": ("Commodité et proximité", "Amenity and proximity", "المرافق والقرب", "Infrastruktur und Nähe", "Altyapı ve yakınlık"),
    "Demarche": ("Démarche", "Procedure", "إجراء", "Verfahren", "Prosedür"),
    "Incitation": ("Incitation", "Incentive", "حافز", "Förderung", "Teşvik"),
    "Organisme": ("Organisme", "Organisation", "هيكل", "Behörde", "Kurum"),
    "Projet": ("Projet", "Project", "مشروع", "Projekt", "Proje"),
    "ServiceAFI": ("Service de l'AFI", "AFI service", "خدمة الوكالة العقارية الصناعية", "AFI-Dienstleistung", "AFI hizmeti"),
}
for k, (fr, en, ar, de, tr) in FAM.items():
    cls(k, fr=fr, en=en, ar=ar, de=de, tr=tr)
    g.add((DAL[k], DAL.familleDeConcepts, Literal(True)))
fams = list(FAM)
for i, x in enumerate(fams):  # familles disjointes : permet au raisonneur de trouver une incohérence
    for y in fams[i + 1:]:
        if {x, y} != {"Lieu", "Commodite"}:
            g.add((DAL[x], OWL.disjointWith, DAL[y]))
cls("Gouvernorat", "Lieu", fr="Gouvernorat", en="Governorate", ar="ولاية")
cls("ZoneIndustrielle", "Lieu", fr="Zone industrielle", en="Industrial zone", ar="منطقة صناعية")
cls("TypeCommodite", "Commodite", fr="Type de commodité", en="Amenity type", ar="نوع المرفق")
cls("Proximite", "Commodite", fr="Proximité d'une zone", en="Zone proximity", ar="القرب من المنطقة")
cls("CahierDesCharges", "Demarche", fr="Cahier des charges de zone", en="Zone specifications", ar="كراس الشروط")
cls("RegionDeveloppementRegional", "Incitation", fr="Zone de développement régional", en="Regional development zone",
    ar="منطقة تنمية جهوية")

for n, d, r, fr in [("dansGouvernorat", "ZoneIndustrielle", "Gouvernorat", "dans le gouvernorat"),
                    ("contientLot", "ZoneIndustrielle", "Lot", "contient le lot"),
                    ("dansZone", "Lot", "ZoneIndustrielle", "dans la zone"),
                    ("aProximite", "ZoneIndustrielle", "Proximite", "a une proximité"),
                    ("typeDeCommodite", "Proximite", "TypeCommodite", "type de commodité"),
                    ("aCahierDesCharges", "ZoneIndustrielle", "CahierDesCharges", "a pour cahier des charges"),
                    ("eligibleA", "ZoneIndustrielle", "Incitation", "éligible à"),
                    ("organismeCompetent", "SecteurActivite", "Organisme", "organisme compétent"),
                    ("commoditeUtile", "SecteurActivite", "TypeCommodite", "commodité utile"),
                    ("fourniPar", "ServiceAFI", "Organisme", "fourni par"),
                    ("concerneDemarche", "ServiceAFI", "Demarche", "concerne la démarche"),
                    ("relevePourProjet", "Projet", "SecteurActivite", "relève du secteur")]:
    prop(n, OWL.ObjectProperty, d, r, fr)
g.add((DAL.dansZone, OWL.inverseOf, DAL.contientLot))
for n, d, r, fr in [("idAFI", None, XSD.string, "identifiant dans la base AFI"),
                    ("numeroLot", "Lot", XSD.string, "numéro du lot"),
                    ("distanceKm", "Proximite", XSD.decimal, "distance en km"),
                    ("nomLieu", "Proximite", XSD.string, "nom du lieu proche"),
                    ("lienPDF", "CahierDesCharges", XSD.anyURI, "lien du PDF officiel"),
                    ("annee", "CahierDesCharges", XSD.string, "année"),
                    ("ficheBaseConnaissances", None, XSD.integer, "fiche de la base de connaissances AFI"),
                    ("formeAValider", None, XSD.string, "forme tunisienne à valider par un locuteur")]:
    prop(n, OWL.DatatypeProperty, d, r, fr)

# ------------------------------------------------------------------ ABox : lieux, zones, lots
zones = load(D / "1_zones_et_lots/zones.json")
gouvs = load(D / "1_zones_et_lots/gouvernorats.json")
for gv in gouvs:
    n = RES[f"gouvernorat/{gv['code']}"]
    g.add((n, RDF.type, DAL.Gouvernorat))
    labels(n, fr=gv["nom_fr"], ar=gv["nom_ar"])
    g.add((n, DAL.idAFI, Literal(str(gv["code"]))))
TYPES = {"aeroport": ("Aéroport", "Airport", "مطار"), "port": ("Port", "Port", "ميناء"), "gare": ("Gare", "Railway station", "محطة قطار"),
         "autoroute": ("Autoroute", "Motorway", "طريق سيارة"), "gazoduc": ("Gazoduc", "Gas pipeline", "أنبوب الغاز"),
         "electricite_puissance": ("Électricité", "Electricity", "كهرباء"), "eau_debit": ("Eau", "Water", "ماء"),
         "gaz_pression": ("Gaz", "Gas", "غاز"), "telephone": ("Téléphone", "Telephone", "هاتف"),
         "station_epuration": ("Assainissement", "Sanitation", "تطهير")}
for k, (fr, en, ar) in TYPES.items():
    t = RES[f"commodite/{k}"]
    g.add((t, RDF.type, DAL.TypeCommodite))
    labels(t, fr=fr, en=en, ar=ar)
regdev = RES["incitation/zone_developpement_regional"]
g.add((regdev, RDF.type, DAL.RegionDeveloppementRegional))
labels(regdev, fr="Zone de développement régional", en="Regional development zone", ar="منطقة تنمية جهوية")
g.add((regdev, DCTERMS.source, SRC_SQL))
for z in zones:
    n = RES[f"zone/{z['zone_id']}"]
    g.add((n, RDF.type, DAL.ZoneIndustrielle))
    labels(n, fr=z["nom_fr"], ar=z["nom_ar"])
    g.add((n, DAL.idAFI, Literal(z["zone_id"])))
    g.add((n, DCTERMS.source, SRC_SQL))
    if z["gouvernorat"]["code"] is not None:
        g.add((n, DAL.dansGouvernorat, RES[f"gouvernorat/{z['gouvernorat']['code']}"]))
    if z.get("zone_developpement_regional"):
        g.add((n, DAL.eligibleA, regdev))
    for k, v in (z.get("distances") or {}).items():
        if v and v.get("km") is not None:
            px = RES[f"proximite/{z['zone_id']}_{k}"]
            g.add((px, RDF.type, DAL.Proximite))
            g.add((n, DAL.aProximite, px))
            g.add((px, DAL.typeDeCommodite, RES[f"commodite/{k}"]))
            g.add((px, DAL.distanceKm, Literal(v["km"], datatype=XSD.decimal)))
            if v.get("nom"):
                g.add((px, DAL.nomLieu, Literal(v["nom"])))
            g.add((px, DCTERMS.source, Literal(v["source"])))
    for k in (z.get("equipements") or {}):
        if k in TYPES:
            px = RES[f"proximite/{z['zone_id']}_{k}"]
            g.add((px, RDF.type, DAL.Proximite))
            g.add((n, DAL.aProximite, px))
            g.add((px, DAL.typeDeCommodite, RES[f"commodite/{k}"]))
for l in load(D / "1_zones_et_lots/lots.json"):  # lien vers le lot seulement (§IV.5)
    if l["statut"] == "non_affiche":
        continue
    n = RES[f"lot/{l['lot_id']}"]
    g.add((n, RDF.type, DAL.Lot))
    g.add((n, DAL.idAFI, Literal(str(l["lot_id"]))))
    g.add((n, DAL.numeroLot, Literal(str(l["lot_num"]))))
    g.add((n, DAL.dansZone, RES[f"zone/{l['zone_id']}"]))
    g.add((RES[f"zone/{l['zone_id']}"], DAL.contientLot, n))
for r in csv.DictReader(open(D / "2_cahiers_des_charges/index.csv", encoding="utf-8-sig")):
    n = RES[f"cahier/{slug(r['fichier_texte'])}"]
    g.add((n, RDF.type, DAL.CahierDesCharges))
    labels(n, fr=f"Cahier des charges {r['zone']} {r['annee']}".strip())
    if r["annee"]:
        g.add((n, DAL.annee, Literal(r["annee"])))
    if r["lien_pdf"].startswith("http"):
        g.add((n, DAL.lienPDF, Literal(r["lien_pdf"], datatype=XSD.anyURI)))
    if r["zone_id"]:
        g.add((RES[f"zone/{r['zone_id']}"], DAL.aCahierDesCharges, n))

# ------------------------------------------------------------------ organismes, secteurs, démarches, services
ORG = {"AFI": ("Agence Foncière Industrielle", "الوكالة العقارية الصناعية"),
       "APII": ("Agence de Promotion de l'Industrie et de l'Innovation", "وكالة النهوض بالصناعة والتجديد"),
       "TIA": ("Tunisia Investment Authority", "الهيئة التونسية للاستثمار"),
       "FIPA": ("Agence de Promotion de l'Investissement Extérieur", "وكالة النهوض بالاستثمار الخارجي"),
       "APIA": ("Agence de Promotion des Investissements Agricoles", "وكالة النهوض بالاستثمارات الفلاحية"),
       "SICAD": ("Système d'information des procédures administratives", None),
       "ANPE": ("Agence Nationale de Protection de l'Environnement", "الوكالة الوطنية لحماية المحيط"),
       "INS": ("Institut National de la Statistique", "المعهد الوطني للإحصاء")}
for k, (fr, ar) in ORG.items():
    n = RES[f"organisme/{k}"]
    g.add((n, RDF.type, DAL.Organisme))
    labels(n, fr=fr, ar=ar)
    g.add((n, SKOS.altLabel, Literal(k)))
SECT = {  # secteurs vus dans les données : monographies APII, pages FIPA, besoins des visiteurs, exemple du CDC
    "agroalimentaire": ("Agroalimentaire", "Agri-food", "الصناعات الغذائية", "APII", []),
    "materiaux_construction": ("Matériaux de construction, céramique et verre", "Building materials", "مواد البناء", "APII", []),
    "mecanique_metallurgie": ("Industries mécaniques et métallurgiques", "Mechanical and metal industries", "الصناعات الميكانيكية والمعدنية", "APII", []),
    "electrique_electronique": ("Industries électriques, électroniques et électroménager", "Electrical and electronic industries", "الصناعات الكهربائية والإلكترونية", "APII", []),
    "chimie_plastique": ("Chimie et plastique", "Chemicals and plastics", "الصناعات الكيميائية", "APII", []),
    "cuir_chaussure": ("Cuir et chaussure", "Leather and footwear", "الجلد والأحذية", "APII", []),
    "textile": ("Textile et habillement", "Textile and clothing", "النسيج والملابس", "APII", []),
    "bois_papier_emballage": ("Bois, papier et emballage", "Wood, paper and packaging", "الخشب والورق والتغليف", "APII", []),
    "peche": ("Pêche et aquaculture", "Fishing and aquaculture", "الصيد البحري", "APIA", ["port"]),  # exemple BF20 du CDC
}
for k, (fr, en, ar, org, util) in SECT.items():
    n = RES[f"secteur/{k}"]
    g.add((n, RDF.type, DAL.SecteurActivite))
    labels(n, fr=fr, en=en, ar=ar)
    g.add((n, DAL.organismeCompetent, RES[f"organisme/{org}"]))
    for u in util:
        g.add((n, DAL.commoditeUtile, RES[f"commodite/{u}"]))
g.add((RES["secteur/peche"], DCTERMS.source, SRC_CDC))
DEM = {"acquisition": ("Acquisition d'un lot", "Plot acquisition", "اقتناء مقسم", [12, 13, 14, 15, 16, 17]),
       "enchere": ("Vente aux enchères", "Public auction", "بتة عمومية", [24, 25]),
       "declaration_projet": ("Déclaration d'un projet industriel (APII)", "Industrial project declaration", "التصريح بمشروع صناعي", [42])}
for k, (fr, en, ar, kb) in DEM.items():
    n = RES[f"demarche/{k}"]
    g.add((n, RDF.type, DAL.Demarche))
    labels(n, fr=fr, en=en, ar=ar)
    for i in kb:
        g.add((n, DAL.ficheBaseConnaissances, Literal(i)))
SERV = {  # les 8 services du CDC §IV.6, reliés aux fiches de la base de connaissances
    "acquisition_lot": ("Acquisition d'un lot", "acquisition", [12, 13, 14, 15, 16, 17]),
    "vente_encheres": ("Vente aux enchères", "enchere", [24, 25]),
    "attestation_situation_fonciere": ("Attestation de situation foncière", None, [18]),
    "attestation_insertion_hypotheque": ("Attestation d'insertion d'hypothèque", None, [19]),
    "attestation_mainlevee": ("Attestation de mainlevée", None, [23]),
    "acte_precision_contrat_final": ("Acte de précision ou contrat final", None, [20]),
    "autorisation_vente_leasing": ("Autorisation de vente (société de leasing)", None, [21]),
    "copie_conforme": ("Copie conforme", None, [22]),
}
for k, (fr, dem, kb) in SERV.items():
    n = RES[f"service/{k}"]
    g.add((n, RDF.type, DAL.ServiceAFI))
    labels(n, fr=fr)
    g.add((n, DAL.fourniPar, RES["organisme/AFI"]))
    g.add((n, DCTERMS.source, SRC_CDC))
    if dem:
        g.add((n, DAL.concerneDemarche, RES[f"demarche/{dem}"]))
    for i in kb:
        g.add((n, DAL.ficheBaseConnaissances, Literal(i)))
proj = RES["projet/exemple_type"]  # la famille Projet : décrite par ses propriétés, les projets réels viennent des visiteurs
g.add((proj, RDF.type, DAL.Projet))
labels(proj, fr="Projet d'un investisseur (gabarit)")

# ------------------------------------------------------------------ synonymes du lexique tunisien
LEX2NODE = {"terrain": DAL.Lot, "zone_industrielle": DAL.ZoneIndustrielle, "gouvernorat": DAL.Gouvernorat,
            "projet": DAL.Projet, "usine": DAL.Projet, "port": RES["commodite/port"], "aeroport": RES["commodite/aeroport"],
            "autoroute": RES["commodite/autoroute"], "gare": RES["commodite/gare"],
            "electricite": RES["commodite/electricite_puissance"], "eau": RES["commodite/eau_debit"],
            "gaz": RES["commodite/gaz_pression"], "subvention": regdev, "avantages": DAL.Incitation,
            "procedure": DAL.Demarche, "papiers": DAL.Demarche, "acheter": RES["demarche/acquisition"],
            "encheres": RES["demarche/enchere"], "cahier_des_charges": DAL.CahierDesCharges,
            "plastique": RES["secteur/chimie_plastique"], "textile": RES["secteur/textile"],
            "agroalimentaire": RES["secteur/agroalimentaire"], "poisson": RES["secteur/peche"],
            "bois": RES["secteur/bois_papier_emballage"], "emballage": RES["secteur/bois_papier_emballage"]}
lex = load(LX / "lexique_tunisien.json")["concepts"]
n_syn = n_val = 0
OK = {"vu_conversations_afi", "vu_cahier_des_charges_afi", "vu_corpus_public", "vu_textes_afi_seulement"}
for c in lex:
    node = LEX2NODE.get(c["id"])
    if node is None:
        continue
    for f in c.get("francais") or []:
        g.add((node, SKOS.altLabel, Literal(f, lang="fr"))); n_syn += 1
    if c.get("anglais"):
        g.add((node, SKOS.altLabel, Literal(c["anglais"], lang="en"))); n_syn += 1
    for key, lang in (("arabe_standard", "ar"), ("tunisien_arabe", "aeb-Arab"), ("arabizi", "aeb-Latn"),
                      ("francais_melange", "aeb-Latn")):
        for f in c.get(key) or []:
            forme = f["forme"] if isinstance(f, dict) else f
            forme = re.sub(r"\s*\(.*?\)", "", forme).strip()
            statut = f.get("statut") if isinstance(f, dict) else None
            if not forme:
                continue
            if statut is None or statut in OK:
                g.add((node, SKOS.altLabel, Literal(forme, lang=lang))); n_syn += 1
            else:
                g.add((node, DAL.formeAValider, Literal(forme))); n_val += 1

# ------------------------------------------------------------------ contrôles BNF19
ttl = OUT / "dalila.ttl"
g.serialize(ttl, format="turtle")
check = Graph().parse(ttl, format="turtle")  # l'export Turtle se recharge-t-il sans erreur ?
rapport = {"triplets": len(check), "synonymes": n_syn, "formes_a_valider": n_val}
import owlrl  # noqa: E402
inf = Graph()
for t in check:
    inf.add(t)
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(inf)
incoherent = list(inf.subjects(RDF.type, OWL.Nothing))
errs = [str(o) for o in inf.objects(None, URIRef("http://www.daml.org/2002/03/agents/agent-ont#error"))]
rapport["raisonneur_owlrl"] = {"triplets_apres_inference": len(inf), "individus_incoherents": [str(x) for x in incoherent][:10],
                               "erreurs": errs[:10], "coherent": not incoherent and not errs}
PFX = "PREFIX dal: <https://dalila.afi.nat.tn/ontologie#> PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
TESTS = {
    "Lieu : zones du gouvernorat de Sousse": PFX + "SELECT ?z WHERE { ?z a dal:ZoneIndustrielle ; dal:dansGouvernorat ?g . ?g skos:prefLabel 'Sousse'@fr }",
    "Lot : lots de la zone 930900 (Sejnane)": PFX + "SELECT (COUNT(?l) AS ?n) WHERE { ?l dal:dansZone <https://dalila.afi.nat.tn/donnees/zone/930900> }",
    "Secteur : organisme compétent pour la pêche": PFX + "SELECT ?o WHERE { <https://dalila.afi.nat.tn/donnees/secteur/peche> dal:organismeCompetent ?o }",
    "Commodité : zones à moins de 10 km d'un port": PFX + "SELECT ?z ?km WHERE { ?z dal:aProximite ?p . ?p dal:typeDeCommodite <https://dalila.afi.nat.tn/donnees/commodite/port> ; dal:distanceKm ?km FILTER(?km <= 10) }",
    "Démarche : fiches de l'acquisition": PFX + "SELECT ?f WHERE { <https://dalila.afi.nat.tn/donnees/demarche/acquisition> dal:ficheBaseConnaissances ?f }",
    "Incitation : zones de développement régional": PFX + "SELECT (COUNT(?z) AS ?n) WHERE { ?z dal:eligibleA <https://dalila.afi.nat.tn/donnees/incitation/zone_developpement_regional> }",
    "Organisme : organismes connus": PFX + "SELECT ?o WHERE { ?o a dal:Organisme }",
    "Projet : la famille existe": PFX + "SELECT ?p WHERE { ?p a dal:Projet }",
    "Service AFI : service pour un prêt bancaire (hypothèque)": PFX + "SELECT ?s ?f WHERE { ?s a dal:ServiceAFI ; dal:ficheBaseConnaissances ?f ; skos:prefLabel ?l FILTER(CONTAINS(LCASE(STR(?l)), 'hypoth')) }",
    "BF17 : « 9at3a », « أرض », « plot » et « terrain » mènent au même concept": PFX + "SELECT DISTINCT ?c WHERE { VALUES ?m { '9at3a'@aeb-Latn 'أرض'@ar 'plot'@en 'terrain'@fr } ?c skos:altLabel ?m }",
}
res = {}
for name, q in TESTS.items():
    rows = [[str(v) for v in r] for r in check.query(q)]
    res[name] = {"nb_resultats": len(rows), "exemple": rows[:3]}
rapport["requetes_sparql"] = res
rapport["toutes_les_familles_repondent"] = all(v["nb_resultats"] > 0 for v in res.values())
(OUT / "rapport_graphe.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rapport, ensure_ascii=False, indent=1))
