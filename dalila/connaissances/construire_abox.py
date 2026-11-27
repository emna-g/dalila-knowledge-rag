"""Génère les DONNÉES du graphe (ABox) depuis la base MariaDB et les sources, puis charge tout dans Oxigraph.

python -m dalila.connaissances.construire_abox
Graphes nommés (TriG, rechargés à chaque construction) :
  .../graphe/core        l'ontologie écrite à la main (ontology/dalila.ttl)
  .../graphe/abox        les données générées ici (zones, lots, services, procédures, incitations, secteurs)
  .../graphe/lexique     les formes attestées du lexique tunisien (et synonymes français)
  .../graphe/a-valider   les libellés écrits par Claude à faire relire (ontology/libelles_a_valider.ttl)
  .../graphe/appris/<id> (vide pour l'instant) : ce que la boucle d'apprentissage ajoutera ; annuler = supprimer le graphe
Contrôles : SHACL (pyshacl), raisonneur OWL RL (owlrl), une requête SPARQL par famille (ontology/queries/*.rq).
Sorties : ontology/abox/dalila.trig, ontology/abox/rapport_graphe.json, base Oxigraph dans ontology/store/.
Mise en service seulement si SHACL, OWL RL et toutes les requêtes passent ; sinon l'ancien graphe reste en place,
le rapport donne la raison et le script sort avec le code 1. Le graphe précédent est gardé dans ontology/store.prev/.
"""
import gc, json, re, datetime, pathlib, shutil, sys
from rdflib import Dataset, Graph, Namespace, Literal, URIRef, RDF, RDFS
from rdflib.namespace import SKOS, DCTERMS, XSD, OWL
from dalila.config import DONNEES, ONTOLOGIE, LEXIQUE, db
from dalila.traitement.references import alias_zones, gouvernorats_par_code

DAL = Namespace("https://afi.nat.tn/ontology/dalila#")
D = Namespace("https://afi.nat.tn/ontology/dalila/donnees/")
G = Namespace("https://afi.nat.tn/ontology/dalila/graphe/")
SRC_BASE = Literal("base AFI (copie de afi.sql rafraîchie depuis la carte publique de l'AFI)")
SRC_CDC = Literal("Cahier des charges Hackathon AGENTIC Dalila (2026-11-17), BF20")
SRC_TIA = Literal("https://tia.gov.tn/fr/pourquoi-la-tunisie/package-dincitation-general/ (table chatbot_sources id 3)")
SRC_APII_NOMENCLATURE = Literal("https://www.tunisieindustrie.nat.tn/fr/doc.asp?mcat=12&mrub=213 (lue le 2026-11-25)")
SRC_TIA_PARCOURS = Literal("https://tia.gov.tn/fr/guide-de-linvestisseur/parcours-de-linvestisseur/ (lue le 2026-10-23)")
SRC_APII_FRANCHISE = Literal("https://www.tunisieindustrie.nat.tn/fr/doc.asp?mcat=12&mrub=214 (lue le 2026-11-25)")
SRC_APII_COMMISSIONS = Literal("https://www.tunisieindustrie.nat.tn/fr/doc.asp?mcat=12&mrub=212 (lue le 2026-11-25)")
# Organisme compétent : qui accorde les avantages de la loi 2016-71 ou instruit le projet, selon les textes officiels.
# Rôle de chaque organisme, mot pour mot ou presque, avec sa source.
ROLE_ORGANISME = {
    "TIA": ("projets dont le coût d'investissement est supérieur ou égal à 15 MDT, tous secteurs", SRC_TIA_PARCOURS),
    "APII": ("projets des secteurs non agricoles dont le coût d'investissement est inférieur à 15 MDT "
             "(directions régionales comprises)", SRC_TIA_PARCOURS),
    "APIA": ("projets du secteur agricole et de la pêche", SRC_TIA_PARCOURS),
    "ONTT": ("projets du secteur touristique (commission nationale pour les projets de moins de 1 MDT)",
             SRC_APII_COMMISSIONS),
    "ONA": ("projets du secteur de l'artisanat", SRC_APII_FRANCHISE),
}
# Raccordements nécessaires pour entrer en production, pour tout projet (STEG, SONEDE, ONAS, Tunisie Télécom).
EQUIPEMENTS_TOUT_PROJET = ["electricite_puissance", "eau_debit", "station_epuration", "telephone"]
PAS_UN_SECTEUR = {"incitations_et_avantages"}  # rubrique de la page de la nomenclature, pas un secteur


def slug(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:80]


def lab(g, n, texte, lang="fr"):
    g.add((n, SKOS.prefLabel, Literal(texte, lang=lang)))


def morceaux(texte, sep=";"):
    return [re.sub(r"\s+", " ", x).strip(" .;") for x in re.split(sep, texte) if len(x.strip(" .;")) > 2]


def main():
    ds = Dataset()
    core, abox, lex, aval = (ds.graph(G[n]) for n in ("core", "abox", "lexique", "a-valider"))
    core.parse(ONTOLOGIE / "dalila.ttl")
    aval.parse(ONTOLOGIE / "libelles_a_valider.ttl")
    con = db("ro")
    cur = con.cursor()

    def q(sql):
        cur.execute(sql)
        return cur.fetchall()

    # ---------------- Lieux, lots, commodités (liens seulement, aucun chiffre)
    gouvernorats = gouvernorats_par_code()
    for code, r in gouvernorats.items():
        n = D[f"gouvernorat/{code}"]
        abox.add((n, RDF.type, DAL.Gouvernorat))
        lab(abox, n, r["nom_fr"])
        lab(abox, n, r["nom_ar"], "ar")
        abox.add((n, DAL.idAFI, Literal(str(code))))
    regimes = {1: D["regime/developpement_regional"], 0: D["regime/littoral_grand_tunis"]}
    for (k, n), (fr, src) in zip(regimes.items(), [("Zone de développement régional", 13), ("Zone littorale ou Grand Tunis", 15)]):
        abox.add((n, RDF.type, DAL.RegimeZone))
        lab(abox, n, fr)
        abox.add((n, DCTERMS.source, Literal(f"base AFI afi.sql, chatbot_connaissances id {src}")))
    alias = {}
    for valeur in alias_zones():
        alias.setdefault(valeur["zone_id"], []).append(valeur)
    for z in q("SELECT zone_id, nom_fr, nom_ar, gouvernorat_code, zone_developpement_regional FROM v_pub_zones"):
        n = D[f"zone/{z['zone_id']}"]
        abox.add((n, RDF.type, DAL.ZoneIndustrielle))
        lab(abox, n, z["nom_fr"])
        if z["nom_ar"]:
            lab(abox, n, z["nom_ar"], "ar")
        abox.add((n, DAL.idAFI, Literal(z["zone_id"])))
        abox.add((n, DCTERMS.source, SRC_BASE))
        for ancien_nom in alias.get(str(z["zone_id"]), []):
            abox.add((n, SKOS.hiddenLabel, Literal(ancien_nom["alias"], lang=ancien_nom["langue"])))
        code = int(z["gouvernorat_code"]) if z["gouvernorat_code"] is not None else None
        if code in gouvernorats:
            abox.add((n, DAL.dansGouvernorat, D[f"gouvernorat/{code}"]))
        if z["zone_developpement_regional"] is not None:
            abox.add((n, DAL.aRegime, regimes[int(z["zone_developpement_regional"])]))
    for r in q("SELECT lot_id, zone_id FROM v_pub_lots"):
        n = D[f"lot/{r['lot_id']}"]
        abox.add((n, RDF.type, DAL.Lot))
        abox.add((n, DAL.idAFI, Literal(str(r["lot_id"]))))
        abox.add((n, DAL.dansZone, D[f"zone/{r['zone_id']}"]))
    TYPES = {"aeroport": ("Aéroport", DAL.TypeProximite), "port": ("Port", DAL.TypeProximite),
             "gare": ("Gare", DAL.TypeProximite), "autoroute": ("Autoroute", DAL.TypeProximite),
             "gazoduc": ("Gazoduc", DAL.TypeProximite),
             "electricite_puissance": ("Électricité", DAL.TypeEquipement), "eau_debit": ("Eau", DAL.TypeEquipement),
             "gaz_pression": ("Gaz", DAL.TypeEquipement), "telephone": ("Téléphone", DAL.TypeEquipement),
             "station_epuration": ("Assainissement", DAL.TypeEquipement)}
    SERV = {"bank": "Banque", "poste": "Bureau de poste", "hospital": "Hôpital / dispensaire", "clinique": "Clinique / laboratoire",
            "ecole": "École", "college": "Collège", "lycee": "Lycée", "faculte": "Faculté / institut", "hotel": "Hôtel",
            "restaurant": "Restaurant", "parking": "Parking"}
    for k, (fr, c) in TYPES.items():
        abox.add((D[f"commodite/{k}"], RDF.type, c))
        lab(abox, D[f"commodite/{k}"], fr)
    for k, fr in SERV.items():
        abox.add((D[f"service_proche/{k}"], RDF.type, DAL.TypeService))
        lab(abox, D[f"service_proche/{k}"], fr)
    for r in q("SELECT DISTINCT zone_id, type FROM v_pub_zone_distances"):
        abox.add((D[f"zone/{r['zone_id']}"], DAL.procheDe, D[f"commodite/{r['type']}"]))
    for r in q("SELECT DISTINCT zone_id, type FROM v_pub_zone_equipements"):
        if r["type"] in TYPES:
            abox.add((D[f"zone/{r['zone_id']}"], DAL.aEquipement, D[f"commodite/{r['type']}"]))
    for r in q("SELECT DISTINCT zone_id, categorie FROM v_pub_services_proches"):
        if r["categorie"] in SERV:
            abox.add((D[f"zone/{r['zone_id']}"], DAL.aServiceProche, D[f"service_proche/{r['categorie']}"]))
    for r in q("SELECT id, zone_id, zone, annee, lien_pdf FROM dalila_cahiers"):
        n = D[f"document/cahier_{r['id']}"]
        abox.add((n, RDF.type, DAL.CahierDesCharges))
        lab(abox, n, f"Cahier des charges {r['zone']} {r['annee']}".strip())
        if (r["lien_pdf"] or "").startswith("http"):
            abox.add((n, DAL.lienPDF, Literal(r["lien_pdf"], datatype=XSD.anyURI)))
        abox.add((n, DCTERMS.source, Literal(r["lien_pdf"] or "fourni par les organisateurs")))
        if r["zone_id"]:
            abox.add((D[f"zone/{r['zone_id']}"], DAL.aDocument, n))

    # ---------------- Organismes
    ORG = {"AFI": "Agence Foncière Industrielle", "APII": "Agence de Promotion de l'Industrie et de l'Innovation",
           "TIA": "Tunisia Investment Authority", "FIPA": "Agence de Promotion de l'Investissement Extérieur",
           "APIA": "Agence de Promotion des Investissements Agricoles", "SICAD": "Système d'information des procédures administratives",
           "ANPE": "Agence Nationale de Protection de l'Environnement", "GMG": "Groupement de Maintenance et de Gestion de la zone industrielle",
           "ONTT": "Office National du Tourisme Tunisien", "ONA": "Office National de l'Artisanat"}
    for k, fr in ORG.items():
        n = D[f"organisme/{k}"]
        abox.add((n, RDF.type, DAL.Organisme))
        lab(abox, n, fr)
        abox.add((n, SKOS.altLabel, Literal(k)))
        abox.add((n, DCTERMS.source, Literal("noms cités dans les sites officiels et la base de connaissances AFI")))
        if k in ROLE_ORGANISME:
            role, src = ROLE_ORGANISME[k]
            abox.add((n, DCTERMS.description, Literal(role, lang="fr")))
            abox.add((n, DCTERMS.source, src))

    # ---------------- Secteurs et activités : nomenclature de l'APII (page lue le 25/11)
    nomen = None
    for l in open(DONNEES / "corpus" / "pages_web.jsonl", encoding="utf-8"):
        p = json.loads(l)
        if "mcat=12&mrub=213" in p["url"] and "/fr/" in p["url"]:
            nomen = p["texte"]
            break
    n_act = 0
    if nomen:
        for bloc in re.split(r"\n## ", "\n" + nomen)[1:]:
            titre, *lignes = bloc.split("\n")
            if slug(titre) in PAS_UN_SECTEUR:
                continue
            sec = D[f"secteur/{slug(titre)}"]
            abox.add((sec, RDF.type, DAL.SecteurActivite))
            lab(abox, sec, titre.strip())
            abox.add((sec, DCTERMS.source, SRC_APII_NOMENCLATURE))
            for li in lignes:
                if li.startswith("- ") and len(li) > 4:
                    a = D[f"activite/{slug(li[2:])}"]
                    abox.add((a, RDF.type, DAL.Activite))
                    lab(abox, a, li[2:].strip())
                    abox.add((a, DAL.dansSecteur, sec))
                    abox.add((a, DCTERMS.source, SRC_APII_NOMENCLATURE))
                    n_act += 1
    peche = D["secteur/peche_aquaculture"]  # exemple BF20 du cahier des charges : la pêche relève de l'APIA, près d'un port
    abox.add((peche, RDF.type, DAL.SecteurActivite))
    lab(abox, peche, "Pêche et aquaculture")
    abox.add((peche, DAL.organismeCompetent, D["organisme/APIA"]))
    abox.add((peche, DAL.commoditeUtile, D["commodite/port"]))
    abox.add((peche, DCTERMS.source, SRC_CDC))
    # Organismes compétents et raccordements, pour chaque secteur, d'après les textes officiels (pas de supposition)
    for sec in set(abox.subjects(RDF.type, DAL.SecteurActivite)):
        ident = str(sec).rsplit("/", 1)[-1]
        orgs = ["TIA"] + (["APIA"] if ident == "peche_aquaculture" else ["APII"])
        if ident == "hebergement_et_restauration":
            orgs.append("ONTT")
        for o in orgs:
            abox.add((sec, DAL.organismeCompetent, D[f"organisme/{o}"]))
        for eq in EQUIPEMENTS_TOUT_PROJET:
            abox.add((sec, DAL.commoditeUtile, D[f"commodite/{eq}"]))
        abox.add((sec, DCTERMS.source, SRC_TIA_PARCOURS))

    # ---------------- Incitations : règles TIA citées mot pour mot (zone 1 / zone 2 du développement régional)
    cur.execute("SELECT contenu FROM chatbot_sources WHERE id = 3")
    tia = cur.fetchone()["contenu"]
    for zone_num in (1, 2):
        m = re.search(rf"Liste des incitations de la zone {zone_num}\s*(.*?)(?:Liste des incitations de la zone|\*Peuvent|$)",
                      tia, re.S)
        if not m:
            continue
        for i, ligne in enumerate([l.strip() for l in m.group(1).split("\n") if len(l.strip()) > 20], 1):
            n = D[f"incitation/tia_zone{zone_num}_{i}"]
            abox.add((n, RDF.type, DAL.RegleIncitation))
            lab(abox, n, f"Développement régional, zone {zone_num} : {ligne}")
            abox.add((n, DAL.texteSource, Literal(ligne, lang="fr")))
            abox.add((n, DCTERMS.source, SRC_TIA))
            abox.add((regimes[1], DAL.avantage, n))
    abox.add((regimes[1], RDFS.comment, Literal(
        "La TIA distingue une zone 1 et une zone 2 de développement régional ; la base AFI ne dit pas à quel "
        "groupe appartient chaque zone industrielle.", lang="fr")))

    # ---------------- Services de l'AFI : procédures, étapes, pièces, frais (tirés des fiches 12 à 25)
    kb = {r["id"]: r for r in q("SELECT id, question, reponse FROM chatbot_connaissances WHERE id BETWEEN 12 AND 25")}
    con.close()
    SERVICES = {  # service -> [(procédure, fiches, régime)]  ; fiches vérifiées sur leurs titres
        "acquisition_lot": ("Acquisition d'un lot", [("acquisition_regional", [13, 14], 1),
                                                     ("acquisition_littoral", [15, 16, 17], 0)]),
        "vente_encheres": ("Vente aux enchères", [("encheres", [24, 25], None)]),
        "attestation_situation_fonciere": ("Attestation de situation foncière", [("situation_fonciere", [18], None)]),
        "attestation_insertion_hypotheque": ("Attestation d'insertion d'hypothèque", [("hypotheque", [19], None)]),
        "acte_precision_contrat_final": ("Acte de précision ou contrat final", [("acte_precision", [20], None)]),
        "autorisation_vente_leasing": ("Autorisation de vente (société de leasing)", [("autorisation_leasing", [21], None)]),
        "copie_conforme": ("Copie conforme", [("copie_conforme", [22], None)]),
        "attestation_mainlevee": ("Attestation de mainlevée", [("mainlevee", [23], None)]),
    }
    n_etapes = n_pieces = n_frais = 0
    for sk, (sfr, procs) in SERVICES.items():
        s = D[f"service/{sk}"]
        abox.add((s, RDF.type, DAL.ServiceAFI))
        lab(abox, s, sfr)
        abox.add((s, DAL.fourniPar, D["organisme/AFI"]))
        abox.add((s, DCTERMS.source, Literal("https://www.afi.nat.tn/fr/nos-services/ (via chatbot_connaissances)")))
        for pk, fiches, reg in procs:
            p = D[f"procedure/{pk}"]
            abox.add((p, RDF.type, DAL.Procedure))
            lab(abox, p, f"{sfr}" + ("" if reg is None else f" ({'développement régional' if reg else 'littoral / Grand Tunis'})"))
            abox.add((s, DAL.aProcedure, p))
            if reg is not None:
                abox.add((p, DAL.pourRegime, regimes[reg]))
            for f in fiches:
                abox.add((p, DAL.ficheAFI, Literal(f)))
                src = Literal(f"base AFI afi.sql, chatbot_connaissances id {f}")
                t = kb[f]["reponse"]
                fr_ = re.search(r"frais\s*:\s*([^\n.]+DT[^\n.]*)", t, re.I)
                if fr_:
                    fn = D[f"frais/{pk}"]
                    abox.add((fn, RDF.type, DAL.Frais))
                    lab(abox, fn, f"{sfr} : {fr_.group(1).strip()}")
                    abox.add((fn, DAL.texteSource, Literal(fr_.group(0).strip(), lang="fr")))
                    abox.add((fn, DCTERMS.source, src))
                    abox.add((p, DAL.aFrais, fn))
                    n_frais += 1
                et = re.search(r"(?:Étapes|Déroulement|conditions)\s*:\s*(.*?)(?:\nDocuments requis|\n\(Source|$)", t, re.S | re.I)
                if et and re.search(r"\d\)", et.group(1)):
                    for i, e in enumerate(morceaux(et.group(1), r"\s*\d+\)\s*"), 1):
                        en = D[f"etape/{pk}_{f}_{i}"]
                        abox.add((en, RDF.type, DAL.Etape))
                        lab(abox, en, e[:300])
                        abox.add((en, DAL.ordre, Literal(i)))
                        abox.add((en, DCTERMS.source, src))
                        abox.add((p, DAL.aEtape, en))
                        n_etapes += 1
                docs = re.search(r"Documents requis[^:]*:\s*(.*?)(?:\n\(Source|$)", t, re.S)
                if docs:
                    phase = ""
                    for bloc in re.split(r"\b(I{1,3}\.\s*[^:]+:)", docs.group(1)):
                        if re.match(r"I{1,3}\.", bloc):
                            phase = bloc.strip(" :")
                            continue
                        for i, d in enumerate(morceaux(bloc), 1):
                            pn = D[f"piece/{pk}_{slug(d)[:60]}"]
                            abox.add((pn, RDF.type, DAL.Piece))
                            lab(abox, pn, d[:300])
                            if phase:
                                abox.add((pn, RDFS.comment, Literal(phase, lang="fr")))
                            abox.add((pn, DCTERMS.source, src))
                            abox.add((p, DAL.demandePiece, pn))
                            n_pieces += 1
    for fid, titre in (("demande_acquisition_fr", "Demande d'acquisition d'un lot (AFI, FR)"),
                       ("demande_acquisition_ar", "Demande d'acquisition d'un lot (AFI, AR)")):
        n = D[f"document/{fid}"]
        abox.add((n, RDF.type, DAL.Formulaire))
        lab(abox, n, titre)
        abox.add((n, DCTERMS.source, Literal("https://www.afi.nat.tn/fr/documents/")))
        for pk in ("acquisition_regional", "acquisition_littoral"):
            abox.add((D[f"procedure/{pk}"], DAL.formulaire, n))
    for k, fr in (("usine", "Usine"), ("depot", "Dépôt / entrepôt"), ("atelier", "Atelier")):
        n = D[f"nature/{k}"]
        abox.add((n, RDF.type, DAL.NatureProjet))
        lab(abox, n, fr)

    # ---------------- Lexique : formes attestées seulement (les autres vont dans « a-valider »)
    lexique = json.load(open(LEXIQUE / "lexique_tunisien.json", encoding="utf-8"))["concepts"]
    CIBLE = {  # concept du lexique -> concept du graphe (correction G5 : usine -> nature du projet, papiers -> pièce)
        "terrain": DAL.Lot, "zone_industrielle": DAL.ZoneIndustrielle, "gouvernorat": DAL.Gouvernorat,
        "projet": DAL.Projet, "usine": D["nature/usine"], "depot": D["nature/depot"],
        "port": D["commodite/port"], "aeroport": D["commodite/aeroport"], "autoroute": D["commodite/autoroute"],
        "gare": D["commodite/gare"], "electricite": D["commodite/electricite_puissance"],
        "eau": D["commodite/eau_debit"], "gaz": D["commodite/gaz_pression"], "subvention": DAL.RegleIncitation,
        "avantages": DAL.Incitation, "procedure": DAL.Procedure, "papiers": DAL.Piece, "demande": DAL.Formulaire,
        "acheter": D["service/acquisition_lot"], "encheres": D["service/vente_encheres"],
        "cahier_des_charges": DAL.CahierDesCharges, "poisson": D["secteur/peche_aquaculture"], "proche": DAL.Commodite,
        # crédit bancaire -> attestation d'insertion d'hypothèque : lien donné par la fiche AFI 19 (« pour un prêt
        # bancaire ») et par l'exemple BF22 du cahier des charges (« la banque me demande un papier pour mon prêt »)
        "credit": D["service/attestation_insertion_hypotheque"],
    }
    OK = {"vu_conversations_afi", "vu_cahier_des_charges_afi", "vu_corpus_public", "vu_textes_afi_seulement"}
    n_lex = n_aval = 0
    for c in lexique:
        cible = CIBLE.get(c["id"])
        if cible is None:
            continue
        for f in c.get("francais") or []:
            lex.add((cible, SKOS.altLabel, Literal(f, lang="fr"))); n_lex += 1
        if c.get("anglais"):
            lex.add((cible, SKOS.altLabel, Literal(c["anglais"], lang="en"))); n_lex += 1
        for key, lang in (("arabe_standard", "ar"), ("tunisien_arabe", "aeb-Arab"), ("arabizi", "aeb-Latn"),
                          ("francais_melange", "aeb-Latn")):
            for f in c.get(key) or []:
                forme = re.sub(r"\s*\(.*?\)", "", f["forme"] if isinstance(f, dict) else f).strip()
                if not forme:
                    continue
                if not isinstance(f, dict) or f.get("statut") in OK:
                    lex.add((cible, SKOS.altLabel, Literal(forme, lang=lang))); n_lex += 1
                else:
                    aval.add((cible, SKOS.altLabel, Literal(forme, lang=lang)))
                    aval.add((cible, DAL.aValider, Literal(forme))); n_aval += 1
    # activités de la nomenclature reliées aux mots du lexique par mot-clé (plastique, textile, bois…)
    MOTS = {"plastique": r"plasti", "textile": r"textil|vêtement|habill|tissage|filature",
            "agroalimentaire": r"aliment|boisson|lait|conserve", "bois": r"\bbois\b", "emballage": r"emballage"}
    for c in lexique:
        if c["id"] in MOTS:
            formes = [x["forme"] if isinstance(x, dict) else x for x in (c.get("arabizi") or []) + (c.get("tunisien_arabe") or [])
                      if not isinstance(x, dict) or x.get("statut") in OK]
            for a in list(abox.subjects(RDF.type, DAL.Activite)):
                if re.search(MOTS[c["id"]], str(abox.value(a, SKOS.prefLabel)), re.I):
                    for f in (c.get("francais") or []):
                        lex.add((a, SKOS.altLabel, Literal(f, lang="fr")))
                    for f in formes:
                        lex.add((a, SKOS.altLabel, Literal(re.sub(r"\s*\(.*?\)", "", f).strip(), lang="aeb")))
    # synonymes français des commodités (cas « commodités près de la zone… »)
    for f in ("commodités", "commodité", "équipements", "équipement", "infrastructures", "services", "à proximité",
              "proximité", "aux alentours", "autour de la zone"):
        lex.add((DAL.Commodite, SKOS.altLabel, Literal(f, lang="fr")))

    # ---------------- Écriture, Oxigraph, contrôles
    # Tout est d'abord construit à côté (dalila.new.trig, store.new) ; le graphe en service (dalila.trig, store)
    # n'est remplacé QUE si tous les contrôles passent. Sinon il reste en place et le script sort en erreur.
    out = ONTOLOGIE / "abox"
    out.mkdir(exist_ok=True)
    trig_new, trig = out / "dalila.new.trig", out / "dalila.trig"
    ds.serialize(trig_new, format="trig")
    union = Graph()
    for gr in (core, abox, lex, aval):
        for t in gr:
            union.add(t)
    import pyshacl, owlrl
    conforme, _, rapport_txt = pyshacl.validate(union, shacl_graph=Graph().parse(ONTOLOGIE / "shapes.ttl"),
                                                inference="none", abort_on_first=False)
    ferme = Graph()
    for t in core:
        ferme.add(t)
    for t in abox:
        ferme.add(t)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(ferme)
    erreurs = [str(o) for o in ferme.objects(None, URIRef("http://www.daml.org/2002/03/agents/agent-ont#error"))]
    import pyoxigraph as ox
    store_dir, store_new, store_prev = (ONTOLOGIE / n for n in ("store", "store.new", "store.prev"))
    if store_new.exists():
        shutil.rmtree(store_new)  # reste d'une construction précédente interrompue
    store = ox.Store(str(store_new))
    store.bulk_load(path=str(trig_new), format=ox.RdfFormat.TRIG)
    store.flush()
    reqs = {}
    for f in sorted((ONTOLOGIE / "queries").glob("*.rq")):
        rows = list(store.query(f.read_text(encoding="utf-8"), use_default_graph_as_union=True))
        reqs[f.stem] = {"nb_resultats": len(rows), "exemple": [[str(v) for v in r] for r in rows[:3]]}
    del store  # libère les fichiers de store.new avant de le renommer (Windows)
    gc.collect()
    echecs = ([] if conforme else ["SHACL non conforme"]) + ([f"OWL RL : {len(erreurs)} erreur(s)"] if erreurs else []) \
        + [f"requête sans résultat : {k}" for k, v in reqs.items() if v["nb_resultats"] == 0]
    if not echecs:  # mise en service : l'ancien graphe est gardé dans store.prev (retour arrière possible)
        if store_prev.exists():
            shutil.rmtree(store_prev)
        if store_dir.exists():
            store_dir.rename(store_prev)
        store_new.rename(store_dir)
        trig_new.replace(trig)
    langs = {}
    for gname, gr in (("lexique", lex), ("a-valider", aval), ("core+abox", core + abox)):
        for o in gr.objects(None, SKOS.prefLabel):
            langs.setdefault(o.language or "-", [0, 0, 0])[["lexique", "a-valider", "core+abox"].index(gname)] += 1
        for o in gr.objects(None, SKOS.altLabel):
            langs.setdefault(o.language or "-", [0, 0, 0])[["lexique", "a-valider", "core+abox"].index(gname)] += 1
    rapport = {"genere_le": datetime.datetime.now().isoformat(timespec="minutes"),
               "triplets": {"core": len(core), "abox": len(abox), "lexique": len(lex), "a-valider": len(aval)},
               "activites_nomenclature_APII": n_act, "etapes": n_etapes, "pieces": n_pieces, "frais": n_frais,
               "libelles_par_langue_[lexique,a-valider,core+abox]": langs,
               "shacl_conforme": conforme, "shacl_rapport": rapport_txt[:3000] if not conforme else "",
               "owlrl_erreurs": erreurs[:10], "requetes_sparql_oxigraph": reqs,
               "toutes_les_requetes_repondent": all(v["nb_resultats"] > 0 for v in reqs.values()),
               "mis_en_service": not echecs, "echecs": echecs}
    (out / "rapport_graphe.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rapport.items() if k != "requetes_sparql_oxigraph"}, ensure_ascii=False, indent=1))
    print({k: v["nb_resultats"] for k, v in reqs.items()})
    if echecs:
        print("GRAPHE REFUSÉ, l'ancien reste en service :", "; ".join(echecs), file=sys.stderr)
        sys.exit(1)
    print("graphe mis en service (ancien gardé dans ontology/store.prev)")


if __name__ == "__main__":
    main()
