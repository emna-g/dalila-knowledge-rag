"""Tester Dalila sans LLM : pose une question, une page s'ouvre dans le navigateur avec ce que Dalila a trouvé.

Lancer :  double-clic sur tester.bat   (MariaDB doit tourner : voir README)
Pour chaque question : 1) comment elle est comprise (graphe), 2) les chiffres lus dans MariaDB,
3) les textes à citer (passages de MariaDB). Le LLM rédigerait sa réponse uniquement avec ces éléments.
"""
import html, logging, os, sys, urllib.parse, warnings, webbrowser, pathlib

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)
from backend.app.dalila import Dalila  # noqa: E402

PAGE = pathlib.Path(__file__).resolve().parent / "resultat.html"
TYPES = {"reponse_validee_afi": "Réponse validée par l'AFI", "site_officiel": "Page d'un site officiel",
         "cahier_des_charges": "Cahier des charges de la zone", "fiche_zone": "Fiche de zone", "loi": "Texte de loi",
         "guide": "Guide", "formulaire": "Formulaire", "procedure": "Procédure", "secteur": "Note sectorielle",
         "rapport": "Rapport"}
SERV = {"bank": "Banque", "poste": "Bureau de poste", "hospital": "Hôpital / dispensaire", "clinique": "Clinique / laboratoire",
        "ecole": "École", "college": "Collège", "lycee": "Lycée", "faculte": "Faculté / institut", "hotel": "Hôtel",
        "restaurant": "Restaurant", "parking": "Parking"}
E = lambda t: html.escape(str(t if t is not None else ""))  # noqa: E731


def prix_terrain(l):
    v = l.get("prix_terrain_estime_dt")
    return f"{v:,.0f} DT".replace(",", " ") if v else "non publié"


def fiche(z):
    b = [f"<h3>{E(z['nom_fr'])} ({E(z['gouvernorat_fr'])})</h3><table>"
         f"<tr><td>Prix au m²</td><td>{E(z['prix_m2_dt']) + ' DT' if z['prix_m2_dt'] else 'non publié'}</td></tr>"
         f"<tr><td>Lots disponibles</td><td>{E(z['lots_disponibles'])}"
         f"{' (dont ' + str(z['lots_disponibles_a_confirmer']) + ' à confirmer)' if z['lots_disponibles_a_confirmer'] else ''}</td></tr>"
         f"<tr><td>Type de zone</td><td>{'développement régional' if z['zone_developpement_regional'] else 'littoral / Grand Tunis'}</td></tr></table>"]
    if z["distances"]:
        b.append("<p><b>Infrastructures</b></p><table>" + "".join(
            f"<tr><td>{E(d['type'].capitalize())}</td><td>{E(d['nom'])}</td><td>{E(d['km'])} km</td></tr>" for d in z["distances"]) + "</table>")
    if z["equipements"]:
        b.append("<p><b>Équipements de la zone</b></p><table>" + "".join(
            f"<tr><td>{E(e['type'].replace('_', ' '))}</td><td>{E(e['valeur'])} {E(e['unite'])}</td></tr>" for e in z["equipements"]) + "</table>")
    if z["services_proches"]:
        b.append("<p><b>Services proches</b> (OpenStreetMap ; certains noms manquent dans la source)</p><table>" + "".join(
            f"<tr><td>{E(SERV.get(s['categorie'], s['categorie']))}</td><td>{E(s['nom'] or '(nom non renseigné)')}</td>"
            f"<td>{E(s['distance_km'])} km</td></tr>" for s in z["services_proches"]) + "</table>")
    for c in z["cahiers_des_charges"]:
        b.append(f"<p>Cahier des charges {E(c['annee'])} : <a href='{E(c['lien_pdf'])}'>{E(c['lien_pdf'])}</a></p>")
    return "".join(b)


def page(r):
    s = r["sens"]
    b = ["<h2>1. Ce que Dalila a compris (graphe)</h2>"]
    b.append(f"<p>Langue : {'tunisien' if r['tunisien'] else 'français, arabe ou anglais'}"
             + (f" — mots ajoutés pour la recherche : <b>{E(r['requete'][len(r['question']):].strip(' |'))}</b>" if r["requete"] != r["question"] else "") + "</p>")
    b.append("<p>Idées reconnues : " + (" ".join(f"<span class='tag'>{E(c)}</span>" for c in s["concepts"][:12]) or "aucune") + "</p>")
    if s["zones"]:
        b.append("<p>Zone(s) : <b>" + ", ".join(E(n) for _, n in s["zones"]) + "</b></p>")
    if s["services"]:
        b.append("<p>Service de l'AFI : <b>" + ", ".join(E(x) for x in s["services"]) + "</b></p>")
    b.append("<h2>2. Chiffres (lus dans la base MariaDB, jamais inventés)</h2>")
    ch = r["chiffres"]
    for z in ch.get("zones", []):
        if z:
            b.append(fiche(z))
    if ch.get("lots"):
        b.append("<p><b>Lots disponibles</b>, du moins cher au plus cher :</p><table><tr><th>Zone</th><th>Lot</th><th>Surface</th>"
                 "<th>Prix au m²</th><th>Prix du terrain*</th></tr>" + "".join(
                     f"<tr><td>{E(l['zone_fr'])}</td><td>{E(l['lot_num'])}{' (à confirmer)' if l['a_confirmer'] else ''}</td>"
                     f"<td>{l['surface_m2']:.0f} m²</td><td>{E(l['prix_m2_dt'])} DT</td>"
                     f"<td>{prix_terrain(l)}</td></tr>"
                     for l in ch["lots"]) + "</table><p class='note'>* Le prix au m² est fixé par zone. Prix du terrain = surface × prix au m², "
                 "estimation hors frais.</p>")
    if not ch:
        b.append("<p>La question ne cite ni zone ni gouvernorat : pas de chiffre à lire.</p>")
    b.append("<h2>3. Textes à citer (5 passages)</h2>")
    for i, x in enumerate(r["resultats"], 1):
        src = urllib.parse.unquote(x["source_url"] or "")
        txt = " ".join(x["texte"].split())
        t = " ".join((x["titre"] or "").split())
        if t and txt.startswith(t):
            txt = txt[len(t):].strip()
        ar = sum("؀" <= c <= "ۿ" for c in txt[:300]) > 100
        b.append(f"<div class='carte'><b>{i}. {E(t)}</b> <span class='tag'>{E(TYPES.get(x['type'], x['type']))}</span>"
                 + (" <span class='tag ocr'>lu sur un scan : vérifier les chiffres</span>" if x["texte_ocr"] else "")
                 + f"<p{' dir=rtl' if ar else ''}>{E(txt[:600])}…</p><span class='note'>Source : "
                 + (f"<a href='{E(src)}'>{E(src)}</a>" if src.startswith("http") else E(src)) + "</span></div>")
    PAGE.write_text(f"""<!doctype html><html lang="fr"><meta charset="utf-8"><title>Dalila</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:30px auto;line-height:1.5;color:#222}}
h2{{font-size:17px;margin-top:28px;border-bottom:2px solid #0a6fa9;color:#0a6fa9}} h3{{margin-bottom:4px}}
.note{{color:#666;font-size:14px}} .carte{{border:1px solid #ddd;border-radius:8px;padding:10px 14px;margin:10px 0}}
.tag{{display:inline-block;background:#eef5fb;color:#0a6fa9;border-radius:4px;padding:1px 7px;font-size:13px}}
.ocr{{background:#fff3cd;color:#8a6d00}} td,th{{padding:3px 10px;border-bottom:1px solid #eee;text-align:left}}</style>
<h1>« {E(r['question'])} »</h1><p class="note">Ce que Dalila a trouvé ; le LLM (pas encore branché) rédigerait sa réponse
avec ces seuls éléments, en citant les sources.</p>{''.join(b)}</html>""", encoding="utf-8")
    webbrowser.open(PAGE.as_uri())


if __name__ == "__main__":
    print("Chargement, patiente environ 30 secondes...")
    d = Dalila()
    print("\nPrêt ! Tape ta question puis Entrée (q pour quitter).")
    print("Exemples : quels sont les comodités prés de la zone sidi achour borj el amri | n7eb terrain f Sfax")
    while True:
        try:
            q = input("\nQuestion > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("q", "quit", "exit"):
            break
        if q:
            page(d.analyser(q))
            print("  -> résultat ouvert dans le navigateur")
