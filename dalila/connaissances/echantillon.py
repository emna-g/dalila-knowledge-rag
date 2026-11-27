"""Échantillon commun pour comparer les modèles d'embeddings sans tout réindexer.

python -m dalila.connaissances.echantillon --taille 1500
Contient : toutes les réponses validées de l'AFI, fiches de zone, formulaires et procédures ; tous les passages
attendus par le jeu de test ; puis des passages tirés au hasard (graine fixe) jusqu'à la taille demandée.
Tous les modèles sont comparés sur CE MÊME échantillon : la comparaison est juste, même si l'échantillon
est plus petit que l'index complet.
"""
import argparse, csv, random
from dalila.config import LEXIQUE, db


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--taille", type=int, default=1500)
    a = ap.parse_args(argv)
    if a.taille < 1:
        ap.error("--taille doit être supérieure à zéro.")
    con = db("ingest")
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM dalila_echantillon_eval")
            cur.execute("SELECT id, type, pertinence, longueur FROM dalila_passages")
            passages = cur.fetchall()
            ids = {
                passage["id"] for passage in passages
                if passage["type"] in ("reponse_validee_afi", "fiche_zone", "formulaire", "procedure")
            }
            ids_disponibles = {passage["id"] for passage in passages}
            with open(LEXIQUE / "tests" / "questions_test.csv", encoding="utf-8-sig", newline="") as fichier:
                for question in csv.DictReader(fichier):
                    if question["passages_attendus"].startswith("ids:"):
                        ids.update(set(question["passages_attendus"][4:].split(",")) & ids_disponibles)
            reste = sorted(ids_disponibles - ids)
            random.Random(42).shuffle(reste)
            ids.update(reste[: max(0, a.taille - len(ids))])
            cur.executemany("INSERT INTO dalila_echantillon_eval VALUES (%s)", [(i,) for i in sorted(ids)])
            print(len(ids), "passages dans l'échantillon")
    finally:
        con.close()


if __name__ == "__main__":
    main()
