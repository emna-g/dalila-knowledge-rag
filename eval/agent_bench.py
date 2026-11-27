"""Banc d'essai de l'agent : compare des modèles locaux dans les conditions du serveur de l'AFI (processeur seul).

python -m eval.agent_bench --modeles qwen3:4b,qwen3:1.7b                 (processeur, 8 fils, comme la production)
python -m eval.agent_bench --modeles qwen3:4b --ids R05,R23 --gpu         (essai rapide)

Questions : eval/testset/questions_reelles.csv : toutes celles qui ont une vérité vérifiable (verite_sql ou
passages_attendus) + un choix de questions hors sujet, hors données, vagues et de projet (CHOISIES).
Mesures par question : outils appelés, erreurs du registre, nombre de lots exact (comparé à la requête de vérité),
réponse contenant ce nombre, passage attendu retrouvé, ancrage, repli, écriture de la réponse, durée.
Résultats : eval/reports/agent_<modele>.csv (une ligne par question, réponse comprise) et agent_resume.json.
"""
import argparse, csv, json, os, statistics, time
from dalila.config import RACINE
from dalila.traitement.base import q

CHOISIES = ["R16", "R26", "R28", "R31", "R32", "R34", "R41", "R53", "R54"]
DONNEES = {"chercher_lots", "fiche_zone", "lister_zones", "zones_proches", "demarche", "chercher_passages"}
RAPPORTS = RACINE / "eval" / "reports"


def ecriture(texte):
    """Part de lettres arabes parmi les lettres (évaluation seulement : vérifie la langue de la réponse)."""
    lettres = [c for c in texte if c.isalpha()]
    return sum("؀" <= c <= "ۿ" for c in lettres) / max(len(lettres), 1)


def questions(ids=None):
    Q = list(csv.DictReader(open(RACINE / "eval/testset/questions_reelles.csv", encoding="utf-8-sig")))
    if ids:
        return [x for x in Q if x["id"] in ids]
    return [x for x in Q if x["verite_sql"] or x["passages_attendus"] or x["id"] in CHOISIES]


def juger(x, r):
    from dalila.harnais.garde_fous import nombres
    outils = [o["outil"] for o in r["outils"]]
    j = {"outils": " > ".join(outils), "erreurs_registre": sum(1 for o in r["outils"] if o["erreur"]),
         "repli": r["source"] == "repli", "ancrage_ok": bool(r["ancrage"] and r["ancrage"]["ok"])}
    texte = r["reponse"]
    if x["verite_sql"]:
        vrai = list(q(x["verite_sql"])[0].values())[0]
        j["verite"] = vrai
        j["nombre_outil_ok"] = any(o["outil"] == "chercher_lots" for o in r["outils"]) and \
            vrai in r.get("_nombres_outils", [])
        j["nombre_reponse_ok"] = any(vrai in plein for plein, _ in nombres(texte)) or (vrai == 0 and j["nombre_outil_ok"])
        j["reussi"] = j["nombre_outil_ok"] and j["nombre_reponse_ok"] and not j["repli"]
    elif x["passages_attendus"].startswith("ids:"):
        ids = x["passages_attendus"][4:].split(",")
        j["passage_ok"] = any(f'"{i}"' in r.get("_texte_outils", "") for i in ids)
        j["reussi"] = j["passage_ok"] and not j["repli"]
    elif x["categorie"] in ("hors_sujet", "plateforme"):
        j["reussi"] = not (set(outils) & DONNEES) and not j["repli"]   # refus sans aller chercher de données
    else:
        j["reussi"] = None  # à relire (projet, vague, hors données) : voir la réponse dans le CSV
    attendu_ar = x["langue"] == "ar"
    j["langue_ok"] = (ecriture(texte) > 0.3) == attendu_ar if x["langue"] in ("ar", "fr") and not j["repli"] else None
    return j


def lancer(modele, Q, delai):
    from dalila.harnais import agent as A
    resultats_bruts = []
    appeler_orig = A.appeler

    def espion(nom, args):  # garde les résultats d'outils pour juger (nombre exact, passages)
        res = appeler_orig(nom, args)
        resultats_bruts.append((nom, res))
        return res

    A.appeler = espion
    ag = A.Agent(modele=modele, delai_s=delai)
    ag.prechauffer()  # chargement des modèles en mémoire, non compté (comme au démarrage du service)
    lignes = []
    for x in Q:
        resultats_bruts.clear()
        r = ag.repondre(x["question"])
        r["_nombres_outils"] = [res.get("nombre_total") for n, res in resultats_bruts if n == "chercher_lots"]
        r["_texte_outils"] = json.dumps([res for _, res in resultats_bruts], ensure_ascii=False)
        j = juger(x, r)
        lignes.append({"id": x["id"], "langue": x["langue"], "categorie": x["categorie"], "question": x["question"],
                       **j, "etapes": r["etapes"], "duree_s": r["duree_s"], "erreur": r["erreur"] or "",
                       "non_ancre": "" if not r["ancrage"] or r["ancrage"]["ok"] else
                       json.dumps({k: v for k, v in r["ancrage"].items() if k != "ok"}, ensure_ascii=False),
                       "arguments": json.dumps([o["arguments"] for o in r["outils"]], ensure_ascii=False),
                       "reponse": r["reponse"]})
        print(f"  {x['id']} {r['duree_s']:6.1f}s reussi={j['reussi']} outils={j['outils']}", flush=True)
        ecrire(modele, lignes)
    A.appeler = appeler_orig
    return lignes


def ecrire(modele, lignes):
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    champs = list(dict.fromkeys(k for l in lignes for k in l))
    with open(RAPPORTS / f"agent_{modele.replace(':', '_')}.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=champs)
        w.writeheader()
        w.writerows(lignes)


def resumer(lignes, delai_cible=35):
    d = [l["duree_s"] for l in lignes]
    juges = [l for l in lignes if l["reussi"] is not None]
    par = lambda cle: [l for l in lignes if cle in l and l[cle] is not None]  # noqa: E731
    return {"questions": len(lignes),
            "reussies": f"{sum(l['reussi'] for l in juges)}/{len(juges)}",
            "nombre_lots_exact": f"{sum(l['nombre_outil_ok'] for l in par('nombre_outil_ok'))}/{len(par('nombre_outil_ok'))}",
            "nombre_dans_reponse": f"{sum(l['nombre_reponse_ok'] for l in par('nombre_reponse_ok'))}/{len(par('nombre_reponse_ok'))}",
            "passage_trouve": f"{sum(l['passage_ok'] for l in par('passage_ok'))}/{len(par('passage_ok'))}",
            "langue_ok": f"{sum(l['langue_ok'] for l in par('langue_ok'))}/{len(par('langue_ok'))}",
            "replis": sum(l["repli"] for l in lignes),
            "erreurs_registre": sum(l["erreurs_registre"] for l in lignes),
            "duree_mediane_s": round(statistics.median(d), 1),
            "duree_p95_s": round(sorted(d)[int(0.95 * (len(d) - 1))], 1),
            f"au_dela_{delai_cible}s": sum(x > delai_cible for x in d)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modeles", default="qwen3:4b,qwen3:1.7b")
    ap.add_argument("--ids", default="")
    ap.add_argument("--delai", type=float, default=90, help="délai par question (mesure ; la cible reste 35 s)")
    ap.add_argument("--gpu", action="store_true", help="carte graphique (essai rapide, pas une mesure de production)")
    a = ap.parse_args()
    os.environ["DALILA_LLM_CPU"] = "0" if a.gpu else "1"
    Q = questions(set(a.ids.split(",")) if a.ids else None)
    resume_path = RAPPORTS / "agent_resume.json"
    resume = json.loads(resume_path.read_text(encoding="utf-8")) if resume_path.exists() else {}
    for m in a.modeles.split(","):
        print(f"{m} : {len(Q)} questions ({'GPU' if a.gpu else 'CPU'})", flush=True)
        t = time.time()
        lignes = lancer(m, Q, a.delai)
        resume[m] = {**resumer(lignes), "materiel": "GPU" if a.gpu else "CPU 8 fils", "duree_totale_min": round((time.time() - t) / 60, 1)}
        print(json.dumps(resume[m], ensure_ascii=False, indent=1), flush=True)
        if not a.ids:
            resume_path.write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
