"""Tester Dalila sans LLM : pose une question, une page s'ouvre dans le navigateur avec ce que Dalila a trouvé.

Lancer :  double-clic sur tester.bat   (ou : python tester.py)
Taper une question (français, arabe, anglais ou tunisien), puis Entrée. Taper « q » pour quitter.
La page « resultat.html » s'ouvre : elle montre, en clair, ce que le LLM recevrait pour rédiger sa réponse.
Commande spéciale :  sparql <requête>  interroge le graphe directement.
"""
import html, os, pathlib, sys, urllib.parse, warnings, webbrowser

ICI = pathlib.Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ICI / "modeles"))
os.environ["HF_HUB_OFFLINE"] = "1"  # le modèle est déjà sur le disque : pas besoin d'Internet
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore")
sys.path.insert(0, str(ICI / "libs"))
sys.path.insert(0, str(ICI))
import logging  # noqa: E402
logging.disable(logging.WARNING)
from rdflib import Graph  # noqa: E402
from rdflib.namespace import SKOS, RDF  # noqa: E402
from rechercher import Recherche  # noqa: E402
from chiffres import Chiffres  # noqa: E402
from normaliser import tokens  # noqa: E402

print("Chargement, patiente environ 20 secondes...")
g = Graph().parse(ICI / "graphe" / "dalila.ttl")
GOUV = g.namespace_manager.expand_curie("dal:Gouvernorat")
etiquettes = {}
for s, p, o in g.triples((None, None, None)):
    if p in (SKOS.altLabel, SKOS.prefLabel) and isinstance(o.value, str):
        etiquettes.setdefault(o.value.lower(), set()).add(s)
r = Recherche()
c = Chiffres()
PAGE = ICI / "resultat.html"
PREFIXES = ("PREFIX dal: <https://dalila.afi.nat.tn/ontologie#> PREFIX res: <https://dalila.afi.nat.tn/donnees/> "
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> ")
TYPES = {"reponse_validee_afi": "Réponse validée par l'AFI", "site_officiel": "Page d'un site officiel",
         "cahier_des_charges": "Cahier des charges d'une zone", "fiche_zone": "Fiche de zone", "loi": "Texte de loi",
         "guide": "Guide", "formulaire": "Formulaire", "procedure": "Procédure", "secteur": "Note sectorielle",
         "rapport": "Rapport"}


def fr(x):
    labs = [o for o in g.objects(x, SKOS.prefLabel) if getattr(o, "language", None) == "fr"]
    return str(labs[0]) if labs else str(x).split("#")[-1].split("/")[-1]


def e(t):
    return html.escape(str(t or ""))


def page(question, blocs):
    PAGE.write_text(f"""<!doctype html><html lang="fr"><meta charset="utf-8"><title>Dalila : {e(question)}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:30px auto;line-height:1.5;color:#222}}
h1{{font-size:22px}} h2{{font-size:17px;margin-top:28px;border-bottom:2px solid #0a6fa9;color:#0a6fa9}}
.note{{color:#666;font-size:14px}} .carte{{border:1px solid #ddd;border-radius:8px;padding:10px 14px;margin:10px 0}}
.tag{{display:inline-block;background:#eef5fb;color:#0a6fa9;border-radius:4px;padding:1px 7px;font-size:13px}}
.ocr{{background:#fff3cd;color:#8a6d00}} td,th{{padding:4px 10px;border-bottom:1px solid #eee;text-align:left}}
.ar{{direction:rtl;text-align:right}}</style>
<h1>Question : « {e(question)} »</h1>
<p class="note">Cette page montre ce que Dalila a trouvé. Le LLM (pas encore branché) rédigerait sa réponse
<b>uniquement</b> avec ces éléments, en citant les sources.</p>
{blocs}</html>""", encoding="utf-8")
    webbrowser.open(PAGE.as_uri())


def regime_de(gouv):
    """Régime des zones où il y a des lots disponibles dans ce gouvernorat (d'après la base)."""
    lots = c.chercher_lots(gouvernorat=gouv, limite=1000)
    reg = {c.zone(z)["zone_developpement_regional"] for z in {l["zone_id"] for l in lots}}
    return {frozenset({1}): "developpement_regional", frozenset({0}): "littoral"}.get(frozenset(reg))


def analyser(question):
    res = r.chercher(question, k=5)
    mots = tokens(res["requete"].lower())
    fen = set(mots) | {" ".join(mots[i:i + n]) for n in (2, 3) for i in range(len(mots))}
    concepts = set().union(*[etiquettes.get(m, set()) for m in fen]) if fen else set()
    gouvs = [fr(x) for x in concepts if (x, RDF.type, GOUV) in g]
    regime = regime_de(gouvs[0]) if gouvs else None
    if regime:  # on refait la recherche en écartant les fiches de l'autre régime (littoral / régional)
        res = r.chercher(question, k=5, regime=regime)
    b = []
    ajout = res["requete"][len(question):].strip(" |") if res["requete"] != question else ""
    b.append("<h2>1. Langue : comment Dalila a compris la question</h2>")
    if res["tunisien"]:
        b.append("<p>Dalila a reconnu du <b>tunisien</b>.</p>")
        if ajout:
            b.append(f"<p>Pour mieux chercher, elle a ajouté les mots équivalents : <b>{e(ajout)}</b></p>")
    else:
        b.append("<p>Question en français, arabe ou anglais : elle est utilisée telle quelle.</p>")
    b.append("<h2>2. Sens : les idées reconnues dans la question (graphe)</h2>")
    noms = sorted({fr(x) for x in concepts})
    b.append("<p>" + (" ".join(f'<span class="tag">{e(n)}</span>' for n in noms) or "Aucune idée reconnue.") + "</p>")
    b.append('<p class="note">Exemple : « terrain », « 9at3a » et « أرض » mènent tous à l\'idée « Lot ».</p>')
    b.append("<h2>3. Chiffres : lus dans la base (jamais inventés)</h2>")
    shown = False
    if gouvs:
        lots = c.chercher_lots(gouvernorat=gouvs[0], limite=10)
        b.append(f"<p><b>{len(lots)}</b> lot(s) disponible(s) affiché(s) dans le gouvernorat de <b>{e(gouvs[0])}</b>, "
                 "du moins cher au plus cher :</p><table><tr><th>Zone</th><th>Lot</th><th>Surface</th><th>Prix au m²</th>"
                 "<th>Prix du terrain*</th></tr>")
        for l in lots:
            conf = " (à confirmer)" if l["a_confirmer"] else ""
            total = f"{l['surface_m2'] * l['prix_m2_dt']:,.0f} DT".replace(",", " ") if l["prix_m2_dt"] else "non publié"
            b.append(f"<tr><td>{e(l['zone_fr'])}</td><td>{e(l['lot_num'])}{conf}</td>"
                     f"<td>{l['surface_m2']:.0f} m²</td><td>{l['prix_m2_dt']} DT/m²</td><td>{total}</td></tr>")
        b.append("</table><p class='note'>* Le prix au m² est fixé par zone : tous les lots d'une même zone ont le même "
                 "prix au m². Prix du terrain = surface × prix au m², estimation hors frais (contrat, piquetage).</p>")
        if regime:
            b.append(f"<p class='note'>Zone(s) de {'développement régional' if regime == 'developpement_regional' else 'la côte / Grand Tunis'} "
                     "(d'après la base) : les textes ci-dessous ne gardent que les règles de ce type de zone.</p>")
        shown = True
    for t, nom in (("port", "un port"), ("aeroport", "un aéroport"), ("gare", "une gare"), ("autoroute", "une autoroute")):
        if any(str(x).endswith("/" + t) for x in concepts):
            b.append(f"<p>Zones à moins de 20 km d'<b>{nom}</b> :</p><table><tr><th>Zone</th><th>Gouvernorat</th>"
                     f"<th>{nom.split()[-1].capitalize()}</th><th>Distance</th></tr>")
            for z in c.zones_proches(t, 20)[:8]:
                b.append(f"<tr><td>{e(z['nom_fr'])}</td><td>{e(z['gouvernorat_fr'])}</td><td>{e(z['nom'])}</td>"
                         f"<td>{z['km']} km</td></tr>")
            b.append("</table>")
            shown = True
    if not shown:
        b.append("<p>La question ne cite ni lieu ni port : pas de chiffre à lire. "
                 "Dalila demanderait : « Dans quel gouvernorat cherchez-vous ? »</p>")
    b.append("<h2>4. Textes à citer : les 5 passages les plus utiles</h2>")
    for i, x in enumerate(res["resultats"], 1):
        src = urllib.parse.unquote(x["source_url"] or "")
        lien = f'<a href="{e(src)}">{e(src)}</a>' if src.startswith("http") else e(src)
        ocr = ' <span class="tag ocr">lu sur un scan : vérifier les chiffres sur le PDF</span>' if x["texte_ocr"] else ""
        txt = " ".join(x["texte"].split())
        titre = " ".join((x["titre"] or "").split())
        if titre and txt.startswith(titre):  # les réponses de l'AFI répètent leur question au début : on l'enlève
            txt = txt[len(titre):].strip()
        txt = txt[:600]
        cls = ' class="ar"' if sum(ch >= "؀" and ch <= "ۿ" for ch in txt) > len(txt) / 3 else ""
        b.append(f'<div class="carte"><b>{i}. {e(x["titre"])}</b><br><span class="tag">{e(TYPES.get(x["type"], x["type"]))}'
                 f'</span>{ocr}<p{cls}>{e(txt)}…</p><span class="note">Source : {lien}</span></div>')
    page(question, "\n".join(b))
    print("  -> résultat ouvert dans le navigateur (resultat.html)")


def sparql(q):
    try:
        rows = list(g.query(PREFIXES + q))
        t = "".join("<tr>" + "".join(f"<td>{e(v)}</td>" for v in row) + "</tr>" for row in rows)
        page("SPARQL", f"<h2>Requête sur le graphe</h2><pre>{e(q)}</pre><p>{len(rows)} résultat(s)</p><table>{t}</table>")
        print(f"  -> {len(rows)} résultat(s), ouverts dans le navigateur")
    except Exception as ex:
        print("  erreur dans la requête :", ex)


print("\nPrêt ! Tape ta question puis Entrée (q pour quitter).")
print("Exemples :  n7eb terrain f Sfax   |   famma 9at3a 9rib mel port?   |   Procédure d'acquisition ?")
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
