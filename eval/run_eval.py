"""Évaluation de la recherche de Dalila (graphe + filtres + passages MariaDB).

python -m eval.run_eval --modele e5                       index complet (8 860 passages)
python -m eval.run_eval --modele e5  --echantillon        échantillon commun de 1 500 passages
python -m eval.run_eval --modele bge --echantillon
python -m eval.run_eval --modele bge --echantillon --reranker
Questions : eval/testset/questions_*.csv (même format) ; par défaut le jeu de 30 questions du lexique.
Mesures : rappel@5 (la bonne réponse est-elle dans les 5 premiers ?), MRR (rang moyen inverse de la 1re bonne
réponse), par langue ; temps de réponse (médiane et 95e centile).
"""
import argparse, csv, json, re, statistics, time, pathlib
from backend.config import LEXIQUE, RACINE
from backend.app.dalila import Dalila


def attendu_ok(attendu, r):
    if attendu.startswith("ids:"):
        return r["id"] in set(attendu[4:].split(","))
    rx = re.compile(attendu[6:], re.I)
    return bool(rx.search(r["texte"]) or rx.search(r["titre"] or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", default="e5")
    ap.add_argument("--reranker", action="store_true")
    ap.add_argument("--echantillon", action="store_true")
    ap.add_argument("--questions", default=str(LEXIQUE / "tests/questions_test.csv"))
    a = ap.parse_args()
    Q = [q for q in csv.DictReader(open(a.questions, encoding="utf-8-sig"))
         if q.get("passages_attendus") or q.get("verite_sql")]
    d = Dalila(modele=a.modele, reranker=a.reranker, echantillon=a.echantillon)
    d.analyser("question de chauffe")  # premier appel plus lent (chargement)
    lignes, temps, chiffres = [], [], {}
    par_langue = {}
    for q in Q:
        t = time.time()
        res = d.analyser(q["question"], k=5)
        temps.append(time.time() - t)
        lang = q.get("langue_attendue") or q.get("langue")
        if q.get("verite_sql"):  # question de chiffres : le nombre de lots renvoyé doit égaler la vérité SQL
            with d.outils.con.cursor() as cur:
                cur.execute(q["verite_sql"])
                vrai = list(cur.fetchone().values())[0]
            obtenu = len(res["chiffres"].get("lots", []))
            s = chiffres.setdefault(lang, {"n": 0, "ok": 0})
            s["n"] += 1
            s["ok"] += int(obtenu == vrai)
            lignes.append({"id": q["id"], "question": q["question"], "langue": lang, "rang": "",
                           "zones": f"chiffre attendu {vrai}, obtenu {obtenu}", "intention": res["sens"]["intention"],
                           "top1": ""})
            continue
        rang = next((i + 1 for i, r in enumerate(res["resultats"]) if attendu_ok(q["passages_attendus"], r)), None)
        s = par_langue.setdefault(lang, {"n": 0, "trouve": 0, "rr": 0.0})
        s["n"] += 1
        s["trouve"] += rang is not None
        s["rr"] += 1 / rang if rang else 0
        lignes.append({"id": q["id"], "question": q["question"], "langue": lang, "rang": rang or "",
                       "zones": ";".join(z for _, z in res["sens"]["zones"]), "intention": res["sens"]["intention"],
                       "top1": f"{res['resultats'][0]['id']} {(res['resultats'][0]['titre'] or '')[:60]}" if res["resultats"] else ""})
    n = sum(v["n"] for v in par_langue.values())
    tot_t = sum(s["trouve"] for s in par_langue.values())
    nom = (f"{a.modele}{'_reranker' if a.reranker else ''}_{'echantillon' if a.echantillon else 'complet'}"
           f"_{pathlib.Path(a.questions).stem}")
    resume = {"reglage": nom, "questions": len(Q),
              "rappel@5": f"{tot_t}/{n}", "MRR": round(sum(s["rr"] for s in par_langue.values()) / n, 3),
              "par_langue": {k: {"rappel@5": f"{v['trouve']}/{v['n']}", "MRR": round(v["rr"] / v["n"], 3)}
                             for k, v in par_langue.items()},
              "chiffres_exacts": {k: f"{v['ok']}/{v['n']}" for k, v in chiffres.items()},
              "temps_median_s": round(statistics.median(temps), 2),
              "temps_p95_s": round(sorted(temps)[max(0, int(0.95 * len(temps)) - 1)], 2)}
    out = RACINE / "eval" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"resultats_{nom}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)
    (out / f"resume_{nom}.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resume, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
