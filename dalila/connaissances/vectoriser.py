"""Calcule les vecteurs (embeddings) des passages et les range dans MariaDB (colonne VECTOR).

python -m dalila.connaissances.echantillon --taille 1500
python -m dalila.connaissances.vectoriser --modele e5 --echantillon
python -m dalila.connaissances.vectoriser --modele e5 --index-complet
python -m dalila.connaissances.vectoriser --modele bge --index-complet
La carte graphique est utilisée si elle est là (quelques minutes ; plusieurs heures sur processeur pour bge et qwen3).
L'index complet doit être demandé explicitement ; seuls les passages encore sans vecteur sont calculés.
"""
import argparse, time
from dalila.config import MODELE, MODELES_RECHERCHE, db


def analyser_arguments(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", choices=list(MODELES_RECHERCHE), default=MODELE)
    ap.add_argument("--lot", type=int, default=32)
    ap.add_argument("--longueur-max", type=int, default=512, help="nombre maximal de jetons par passage")
    portee = ap.add_mutually_exclusive_group(required=True)
    portee.add_argument("--echantillon", action="store_true", help="passages de dalila_echantillon_eval uniquement")
    portee.add_argument("--index-complet", action="store_true", help="autoriser l'indexation de tous les passages")
    return ap.parse_args(argv)


def vers_sql(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def main():
    a = analyser_arguments()
    cfg = MODELES_RECHERCHE[a.modele]
    con = db("ingest")
    try:
        with con.cursor() as cur:
            filtre = " AND id IN (SELECT id FROM dalila_echantillon_eval)" if a.echantillon else ""
            cur.execute(f"SELECT id, texte FROM dalila_passages WHERE {cfg['colonne']} IS NULL{filtre} ORDER BY id")
            todo = sorted(cur.fetchall(), key=lambda r: len(r["texte"]))
            print(len(todo), "passages sans vecteur", a.modele)
            if not todo:
                return
            from sentence_transformers import SentenceTransformer
            modele = SentenceTransformer(cfg["nom"], device=None)
            modele.max_seq_length = a.longueur_max
            debut = time.time()
            for i in range(0, len(todo), a.lot):
                lot = todo[i:i + a.lot]
                vecteurs = modele.encode(
                    [cfg["prefixe_passage"] + r["texte"] for r in lot],
                    normalize_embeddings=True,
                    batch_size=a.lot,
                )
                cur.executemany(
                    f"UPDATE dalila_passages SET {cfg['colonne']} = VEC_FromText(%s) WHERE id=%s",
                    [(vers_sql(vec), r["id"]) for vec, r in zip(vecteurs, lot)],
                )
                if (i // a.lot) % 20 == 0:
                    print(f"{i + len(lot)}/{len(todo)}  {time.time() - debut:.0f} s", flush=True)
            print("terminé", f"{time.time() - debut:.0f} s")
    finally:
        con.close()


if __name__ == "__main__":
    main()
