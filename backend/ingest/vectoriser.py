"""Calcule les vecteurs (embeddings) des passages et les range dans MariaDB (colonne VECTOR).

python -m backend.ingest.vectoriser --modele e5          (multilingual-e5-small, 384 dimensions, ~25 min CPU)
python -m backend.ingest.vectoriser --modele bge         (BAAI/bge-m3, 1024 dimensions, plusieurs heures CPU)
python -m backend.ingest.vectoriser --modele e5 --depuis-chroma <dossier index_chroma>
       reprend les vecteurs e5 déjà calculés dans l'ancien index ChromaDB (même modèle, mêmes textes).
Seuls les passages encore sans vecteur sont calculés : on peut arrêter et relancer.
"""
import argparse, json, time
from backend.config import MODELES_RECHERCHE, db


def vers_sql(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", choices=list(MODELES_RECHERCHE), default="e5")
    ap.add_argument("--depuis-chroma")
    ap.add_argument("--lot", type=int, default=32)
    ap.add_argument("--longueur-max", type=int, default=512, help="nombre maximal de jetons par passage")
    ap.add_argument("--echantillon", action="store_true", help="seulement les passages de dalila_echantillon_eval")
    a = ap.parse_args()
    cfg = MODELES_RECHERCHE[a.modele]
    con = db("root")
    cur = con.cursor()
    filtre = " AND id IN (SELECT id FROM dalila_echantillon_eval)" if a.echantillon else ""
    cur.execute(f"SELECT id, texte FROM dalila_passages WHERE {cfg['colonne']} IS NULL{filtre} ORDER BY id")
    todo = cur.fetchall()
    print(len(todo), "passages sans vecteur", a.modele)
    if a.depuis_chroma:
        import chromadb
        col = chromadb.PersistentClient(path=a.depuis_chroma).get_collection("passages_dalila")
        ids = [r["id"] for r in todo]
        n = 0
        for i in range(0, len(ids), 500):
            got = col.get(ids=ids[i:i + 500], include=["embeddings"])
            for pid, emb in zip(got["ids"], got["embeddings"]):
                cur.execute(f"UPDATE dalila_passages SET {cfg['colonne']} = VEC_FromText(%s) WHERE id=%s",
                            (vers_sql(emb), pid))
                n += 1
        print(n, "vecteurs repris de ChromaDB")
        cur.execute(f"SELECT id, texte FROM dalila_passages WHERE {cfg['colonne']} IS NULL ORDER BY id")
        todo = cur.fetchall()
        print(len(todo), "restent à calculer")
    if not todo:
        return
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(cfg["nom"], device="cpu")
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
