"""Démonstration : une question passe par les 4 briques (lexique, graphe, chiffres SQLite, passages ChromaDB).

python demo_dalila.py "n7eb terrain f Sfax"

Ce script ne rédige pas la réponse (c'est le rôle du LLM) : il montre ce que le LLM recevrait.
"""
import json, os, pathlib, re, sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI / "libs"))
sys.path.insert(0, str(ICI))
from rdflib import Graph  # noqa: E402
from rdflib.namespace import SKOS, RDF  # noqa: E402
from rechercher import Recherche  # noqa: E402
from chiffres import Chiffres  # noqa: E402
from normaliser import tokens  # noqa: E402

question = " ".join(sys.argv[1:]) or "n7eb terrain f Sfax"
g = Graph().parse(ICI / "graphe" / "dalila.ttl")
DAL = "https://dalila.afi.nat.tn/ontologie#"
etiquettes = {}  # mot -> concepts du graphe
for s, p, o in g.triples((None, None, None)):
    if p in (SKOS.altLabel, SKOS.prefLabel) and isinstance(o.value, str):
        etiquettes.setdefault(o.value.lower(), set()).add(s)

r = Recherche()
res = r.chercher(question, k=5)
mots = tokens(res["requete"].lower())
fenetres = set(mots) | {" ".join(mots[i:i + 2]) for i in range(len(mots))} | {" ".join(mots[i:i + 3]) for i in range(len(mots))}
concepts = set()
for m in fenetres:
    concepts |= etiquettes.get(m, set())
gouvs = [c for c in concepts if (c, RDF.type, g.namespace_manager.expand_curie("dal:Gouvernorat")) in g]
types = {str(c).split("/")[-1].split("#")[-1] for c in concepts}

print("1. LEXIQUE  tunisien :", res["tunisien"], "| requête :", res["requete"][:120])
print("2. GRAPHE   concepts reconnus :", sorted(types)[:15])
print("3. CHIFFRES (SQLite) :")
c = Chiffres()
nom_gouv = [str(g.value(x, SKOS.prefLabel)) for x in gouvs]
if nom_gouv:  # chiffres seulement quand un lieu est donné
    lots = c.chercher_lots(gouvernorat=nom_gouv[0] if nom_gouv else None, limite=5)
    for l in lots:
        conf = " (à confirmer)" if l["a_confirmer"] else ""
        print(f"   lot {l['lot_num']} - {l['zone_fr']} ({l['gouvernorat_fr']}) : {l['surface_m2']:.0f} m², "
              f"{l['prix_m2_dt']} DT/m², {l['statut']}{conf}")
if not nom_gouv and not {"port", "aeroport", "gare", "autoroute"} & types:
    print("   (aucun lieu dans la question : Dalila demande dans quel gouvernorat chercher)")
for t in ("port", "aeroport", "gare", "autoroute"):
    if t in types:
        for z in c.zones_proches(t, 20)[:5]:
            print(f"   {z['nom_fr']} : {t} {z['nom']} à {z['km']} km")
print("4. PASSAGES (ChromaDB + mots-clés) :")
for x in res["resultats"]:
    print(f"   [{x['type']}] {(x['titre'] or '')[:60]} <{(x['source_url'] or '')[:70]}>")
