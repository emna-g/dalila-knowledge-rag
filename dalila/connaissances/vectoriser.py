"""Calcule les vecteurs (embeddings) des passages et les range dans MariaDB (colonne VECTOR).

python -m dalila.connaissances.vectoriser --modele e5      (multilingual-e5-small, 384 dimensions : modèle léger)
python -m dalila.connaissances.vectoriser --modele bge     (BAAI/bge-m3, 1024 dimensions)
python -m dalila.connaissances.vectoriser --modele qwen3   (Qwen/Qwen3-Embedding-0.6B, 1024 dimensions)
La carte graphique est utilisée si elle est là (quelques minutes ; plusieurs heures sur processeur pour bge et qwen3).
Seuls les passages encore sans vecteur sont calculés : on peut arrêter et relancer.
"""
import argparse, time
from dalila.config import MODELE, MODELES_RECHERCHE, db


def vers_sql(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", choices=list(MODELES_RECHERCHE), default=MODELE)
    ap.add_argument("--lot", type=int, default=32)
    ap.add_argument("--longueur-max", type=int, default=512, help="nombre maximal de jetons par passage")
    ap.add_argument("--echantillon", action="store_true", help="seulement les passages de dalila_echantillon_eval")
    a = ap.parse_args()
    cfg = MODELES_RECHERCHE[a.modele]
    con = db("root")
    cur = con.cursor()
    filtre = " AND id IN (SELECT id FROM dalila_echantillon_eval)" if a.echantillon else ""
    cur.execute(f"SELECT id, texte FROM dalila_passages WHERE {cfg['colonne']} IS NULL{filtre} ORDER BY id")
    todo = sorted(cur.fetchall(), key=lambda r: len(r["texte"]))  # longueurs proches par lot : plus rapide
    print(len(todo), "passages sans vecteur", a.modele)
    if not todo:
        return
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(cfg["nom"], device=None)
    m.max_seq_length = a.longueur_max
    t0 = time.time()
    for i in range(0, len(todo), a.lot):
        lot = todo[i:i + a.lot]
        vec = m.encode([cfg["prefixe_passage"] + r["texte"] for r in lot], normalize_embeddings=True, batch_size=a.lot)
        cur.executemany(f"UPDATE dalila_passages SET {cfg['colonne']} = VEC_FromText(%s) WHERE id=%s",
                        [(vers_sql(v), r["id"]) for v, r in zip(vec, lot)])
        if (i // a.lot) % 20 == 0:
            print(f"{i + len(lot)}/{len(todo)}  {time.time() - t0:.0f} s", flush=True)
    print("terminé", f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
