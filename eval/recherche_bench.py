"""Recherche de passages (outil chercher_passages), avec ou sans les anciennes règles de langue écrites à la main.

    .venv\Scripts\python -m eval.recherche_bench

Jeux : vraies questions (eval/testset), lexique tunisien, 8 langues ; seules les questions dont les passages attendus
sont donnés (« ids:… » ou « regex:… ») comptent. Mesure : passage attendu dans les 5 premiers (rappel@5) et MRR.
Rapport : eval/reports/recherche_regles.json.
"""
import csv, json, re, statistics, sys, time
from dalila.config import LEXIQUE, RACINE
from dalila.semantique.recherche import Recherche

JEUX = {"vraies questions": RACINE / "eval/testset/questions_reelles.csv",
        "lexique tunisien": LEXIQUE / "tests/questions_test.csv",
        "8 langues": RACINE / "eval/testset/questions_claude_a_relire.csv"}


def touche(p, attendu):
    if attendu.startswith("ids:"):
        return p["id"] in attendu[4:].split(",")
    if attendu.startswith("regex:"):
        return bool(re.search(attendu[6:], f"{p['titre'] or ''} {p['texte']}", re.I))
    return False


def mesurer(r):
    out = {}
    for nom, f in JEUX.items():
        Q = [x for x in csv.DictReader(open(f, encoding="utf-8-sig")) if x.get("passages_attendus", "").startswith(("ids:", "regex:"))]
        rangs, temps = [], []
        for x in Q:
            t = time.time()
            res = r.chercher(x["question"], k=5)["resultats"]
            temps.append(time.time() - t)
            rangs.append(next((i + 1 for i, p in enumerate(res) if touche(p, x["passages_attendus"])), None))
        out[nom] = {"questions": len(Q), "rappel@5": f"{sum(1 for k in rangs if k)}/{len(Q)}",
                    "MRR": round(statistics.mean(1 / k if k else 0 for k in rangs), 2),
                    "temps_median_s": round(statistics.median(temps), 2)}
    return out


def main():
    rapport = {}
    for nom, regles in (("sans règles de langue (service)", False), ("avec les anciennes règles", True)):
        rapport[nom] = mesurer(Recherche(lexique=regles, regles_langue=regles))
    (RACINE / "eval/reports/recherche_regles.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(rapport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
