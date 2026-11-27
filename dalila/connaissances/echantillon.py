"""Échantillon commun pour comparer les modèles d'embeddings sans tout réindexer.

python -m dalila.connaissances.echantillon --taille 1500
Contient : toutes les réponses validées de l'AFI, fiches de zone, formulaires et procédures ; tous les passages
attendus par le jeu de test ; puis des passages tirés au hasard (graine fixe) jusqu'à la taille demandée.
Tous les modèles sont comparés sur CE MÊME échantillon : la comparaison est juste, même si l'échantillon
est plus petit que l'index complet.
"""
import argparse, csv, random
from dalila.config import LEXIQUE, db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taille", type=int, default=1500)
    a = ap.parse_args()
    con = db("root")
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS dalila_echantillon_eval (id VARCHAR(12) PRIMARY KEY) "
                "DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci")
    cur.execute("DELETE FROM dalila_echantillon_eval")
    cur.execute("SELECT id, type, pertinence, longueur FROM dalila_passages")
    P = cur.fetchall()
    ids = {p["id"] for p in P if p["type"] in ("reponse_validee_afi", "fiche_zone", "formulaire", "procedure")}
    for q in csv.DictReader(open(LEXIQUE / "tests/questions_test.csv", encoding="utf-8-sig")):
        if q["passages_attendus"].startswith("ids:"):
            ids |= set(q["passages_attendus"][4:].split(",")) & {p["id"] for p in P}
    reste = sorted(p["id"] for p in P if p["id"] not in ids)
    random.Random(42).shuffle(reste)
    ids |= set(reste[: max(0, a.taille - len(ids))])
    cur.executemany("INSERT INTO dalila_echantillon_eval VALUES (%s)", [(i,) for i in sorted(ids)])
    print(len(ids), "passages dans l'échantillon")


if __name__ == "__main__":
    main()
