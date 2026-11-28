"""Compare les modèles de recherche sur les mêmes questions (passages trouvés seulement : les chiffres ne dépendent
pas du modèle).

python -m eval.comparer_modeles                       e5, bge, qwen3, avec et sans reranker, sur les 3 jeux
python -m eval.comparer_modeles --modeles bge qwen3

Résultat : eval/reports/comparaison_modeles.md (rappel@5, MRR et temps médian par réglage et par jeu).
"""
import argparse, json, subprocess, sys
from dalila.config import LEXIQUE, RACINE

JEUX = {"reelles": RACINE / "eval/testset/questions_reelles.csv",
        "lexique (tunisien)": LEXIQUE / "tests/questions_test.csv",
        "6 langues (Claude)": RACINE / "eval/testset/questions_claude_a_relire.csv"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modeles", nargs="+", default=["e5", "bge", "qwen3"])
    a = ap.parse_args()
    lignes = ["| Réglage | " + " | ".join(f"{j} rappel@5 | MRR" for j in JEUX) + " | temps médian |",
              "|---|" + "---|---|" * len(JEUX) + "---|"]
    for m in a.modeles:
        for rr in (False, True):
            cell, temps = [], []
            for nom, f in JEUX.items():
                subprocess.run([sys.executable, "-m", "eval.run_eval", "--modele", m,
                                "--reranker" if rr else "--no-reranker", "--questions", str(f)],
                               check=True, capture_output=True)
                r = json.loads((RACINE / "eval/reports" /
                                f"resume_{m}{'_reranker' if rr else ''}_complet_{f.stem}.json").read_text(encoding="utf-8"))
                cell += [r["rappel@5"], str(r["MRR"])]
                temps.append(r["temps_median_s"])
            ligne = f"| {m}{' + reranker' if rr else ''} | " + " | ".join(cell) + f" | {max(temps)} s |"
            lignes.append(ligne)
            print(ligne, flush=True)
    (RACINE / "eval/reports/comparaison_modeles.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
