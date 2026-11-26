"""Évalue la recherche de Dalila sous 4 réglages, avec et sans lexique tunisien.

python evaluer.py   -> evaluation/resultats.csv + evaluation/resume.json

Jeu de test : lexique_tunisien/tests/questions_test.csv (30 questions avec une réponse attendue : 6 vraies
questions tunisiennes et 5 vraies questions FR/AR, 19 questions tunisiennes écrites pour le test, à relire).
Réussite = un passage attendu (liste d'ids, ou motif dans le texte/titre) est dans les 5 premiers résultats.
Attention : les passages « reponse_validee_afi » contiennent leur propre question ; les questions de test ne
sont pas recopiées de la base, pour ne pas gonfler le score.
"""
import csv, json, pathlib, re, sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from rechercher import Recherche, LEXIQUE  # noqa: E402
from normaliser import NormaliseurTunisien  # noqa: E402

Q = [q for q in csv.DictReader(open(LEXIQUE / "tests/questions_test.csv", encoding="utf-8-sig")) if q["passages_attendus"]]
base = Recherche(lexique=True, hybride=True, filtres=True)
lex = base.norm
REGLAGES = {"sens_seul": (False, False), "hybride_filtres": (True, True)}


def ok(attendu, res):
    if attendu.startswith("ids:"):
        return any(r["id"] in set(attendu[4:].split(",")) for r in res)
    rx = re.compile(attendu[6:], re.I)
    return any(rx.search(r["texte"]) or rx.search(r["titre"] or "") for r in res)


rows, score = [], {}
for q in Q:
    row = {"id": q["id"], "question": q["question"], "origine": q["origine"], "langue": q["langue_attendue"]}
    for nom, (hyb, fil) in REGLAGES.items():
        for avec in (False, True):
            base.norm = lex if avec else None
            base.hybride, base.filtres = hyb, fil
            bm = base.bm25
            if not hyb:
                base.bm25 = None
            res = base.chercher(q["question"], k=5)["resultats"]
            base.bm25 = bm
            cle = f"{nom}_{'avec' if avec else 'sans'}_lexique"
            r = ok(q["passages_attendus"], res)
            row[cle] = r
            s = score.setdefault(cle, {"tout": 0, "tunisien": 0})
            s["tout"] += r
            s["tunisien"] += r and q["langue_attendue"] == "tn"
            if cle == "hybride_filtres_avec_lexique":
                row["top1"] = f"{res[0]['id']} [{res[0]['type']}] {(res[0]['titre'] or '')[:60]}"
    rows.append(row)
n, n_tn = len(Q), sum(1 for q in Q if q["langue_attendue"] == "tn")
resume = {"questions": n, "dont_tunisiennes": n_tn,
          "trouve_dans_les_5_premiers": {k: f"{v['tout']}/{n} (tunisien : {v['tunisien']}/{n_tn})" for k, v in score.items()}}
out = ICI / "evaluation"
out.mkdir(exist_ok=True)
with open(out / "resultats.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
(out / "resume.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(resume, ensure_ascii=False, indent=1))
