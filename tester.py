"""Tester Dalila sans LLM : pose une question, regarde ce que le LLM recevrait.

Lancer :  double-clic sur tester.bat   (ou : python tester.py)
Taper une question (français, arabe, anglais ou tunisien), puis Entrée. Taper « q » pour quitter.

Pour chaque question, on voit :
 1. LEXIQUE  : la question est-elle en tunisien ? quels mots ont été ajoutés pour la recherche ?
 2. GRAPHE   : les concepts reconnus (Lot, Démarche, port, un gouvernorat…)
 3. CHIFFRES : les lots disponibles ou les zones proches, lus dans la base SQLite (jamais inventés)
 4. PASSAGES : les 5 textes à citer, avec leur type, leur source et un extrait
Commandes spéciales :
   sparql <requête>   interroge le graphe directement (voir exemples dans GUIDE_COMPLET.md)
"""
import os, pathlib, sys, warnings

ICI = pathlib.Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ICI / "modeles"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # le modèle est déjà téléchargé : pas besoin d'Internet
warnings.filterwarnings("ignore")
sys.path.insert(0, str(ICI / "libs"))
sys.path.insert(0, str(ICI))
from rdflib import Graph  # noqa: E402
from rdflib.namespace import SKOS, RDF  # noqa: E402
from rechercher import Recherche  # noqa: E402
from chiffres import Chiffres  # noqa: E402
from normaliser import tokens  # noqa: E402

print("Chargement (environ 20 secondes)…")
g = Graph().parse(ICI / "graphe" / "dalila.ttl")
GOUV = g.namespace_manager.expand_curie("dal:Gouvernorat")
etiquettes = {}
for s, p, o in g.triples((None, None, None)):
    if p in (SKOS.altLabel, SKOS.prefLabel) and isinstance(o.value, str):
        etiquettes.setdefault(o.value.lower(), set()).add(s)
r = Recherche()
c = Chiffres()
PREFIXES = ("PREFIX dal: <https://dalila.afi.nat.tn/ontologie#> PREFIX res: <https://dalila.afi.nat.tn/donnees/> "
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> ")


def analyser(question):
    res = r.chercher(question, k=5)
    mots = tokens(res["requete"].lower())
    fen = set(mots) | {" ".join(mots[i:i + n]) for n in (2, 3) for i in range(len(mots))}
    concepts = set().union(*[etiquettes.get(m, set()) for m in fen]) if fen else set()
    def fr(x):  # libellé français du concept
        labs = [o for o in g.objects(x, SKOS.prefLabel) if getattr(o, "language", None) == "fr"]
        return str(labs[0]) if labs else str(x).split("#")[-1].split("/")[-1]

    gouvs = [fr(x) for x in concepts if (x, RDF.type, GOUV) in g]
    noms = sorted({fr(x) for x in concepts})
    print(f"\n1. LEXIQUE   tunisien : {'oui' if res['tunisien'] else 'non'}")
    if res["requete"] != question:
        print(f"            mots ajoutés : {res['requete'][len(question):].strip(' |')[:150]}")
    print(f"2. GRAPHE    concepts : {', '.join(noms[:12]) or '(aucun)'}")
    print("3. CHIFFRES  (base SQLite)")
    if gouvs:
        lots = c.chercher_lots(gouvernorat=gouvs[0], limite=5)
        print(f"            lots disponibles à {gouvs[0]} (du moins cher) : {len(lots)} affichés")
        for l in lots:
            conf = " (à confirmer)" if l["a_confirmer"] else ""
            print(f"            - lot {l['lot_num']}, {l['zone_fr']} : {l['surface_m2']:.0f} m², "
                  f"{l['prix_m2_dt']} DT/m²{conf}")
    for t in ("port", "aeroport", "gare", "autoroute"):
        if any(str(x).endswith("/" + t) for x in concepts):
            print(f"            zones à moins de 20 km d'un(e) {t} :")
            for z in c.zones_proches(t, 20)[:5]:
                print(f"            - {z['nom_fr']} ({z['gouvernorat_fr']}) : {z['nom']} à {z['km']} km")
    if not gouvs and not any(str(x).split("/")[-1] in ("port", "aeroport", "gare", "autoroute") for x in concepts):
        print("            (pas de lieu dans la question : aucun chiffre à lire)")
    print("4. PASSAGES  (les 5 textes à citer)")
    for i, x in enumerate(res["resultats"], 1):
        ocr = "  [OCR : vérifier les chiffres]" if x["texte_ocr"] else ""
        print(f"   {i}. [{x['type']}] {(x['titre'] or '')[:70]}{ocr}")
        print(f"      source : {(x['source_url'] or '')[:100]}")
        print(f"      extrait : {' '.join(x['texte'].split())[:180]}…")


def sparql(q):
    try:
        for row in g.query(PREFIXES + q):
            print("  ", " | ".join(str(v) for v in row))
    except Exception as e:
        print("   erreur SPARQL :", e)


print("Prêt. Pose ta question (q pour quitter).")
while True:
    try:
        q = input("\nQuestion > ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if q.lower() in ("q", "quit", "exit"):
        break
    if q.lower().startswith("sparql "):
        sparql(q[7:])
    elif q:
        analyser(q)
