"""Construit l'index de recherche ChromaDB des passages de Dalila.

python construire_index.py --donnees donnees/dalila_fusion --sortie index_chroma

- Modèle d'embeddings : intfloat/multilingual-e5-small (multilingue FR/AR/EN, 384 dimensions, licence MIT).
  Un « embedding » est une liste de nombres qui résume le sens d'un texte : deux textes de même sens
  ont des listes proches, même s'ils n'utilisent pas les mêmes mots ou la même langue.
- On indexe seulement les passages avec a_indexer = true (les doublons et les passages bloqués sont exclus).
- Chaque passage garde ses métadonnées (type, langue, source, date, zone, page, article, OCR…) pour citer la source.
"""
import argparse, json, pathlib, sys, time, os

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI / "libs"))
os.environ.setdefault("HF_HOME", str(ICI / "modeles"))  # modèle téléchargé sur D:, pas sur C:
import chromadb  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

MODELE = "intfloat/multilingual-e5-small"
ap = argparse.ArgumentParser()
ap.add_argument("--donnees", required=True)
ap.add_argument("--sortie", default=str(ICI / "index_chroma"))
ap.add_argument("--lot", type=int, default=64)
a = ap.parse_args()

P = [json.loads(l) for l in open(pathlib.Path(a.donnees) / "6_pret_pour_le_llm/passages.jsonl", encoding="utf-8")]
P = [p for p in P if p.get("a_indexer")]
print(len(P), "passages à indexer")

modele = SentenceTransformer(MODELE, device="cpu")
client = chromadb.PersistentClient(path=a.sortie)
try:
    client.delete_collection("passages_dalila")
except Exception:
    pass
col = client.create_collection("passages_dalila", metadata={"hnsw:space": "cosine", "modele": MODELE})


def meta(p):
    m = {}
    for k in ("type", "titre", "source_url", "langue", "date_source", "zone_id", "page", "article", "texte_ocr",
              "kb_id", "pertinence", "contient_chiffre"):
        v = p.get(k)
        if v is None:
            continue
        m[k] = v if isinstance(v, (str, int, float, bool)) else str(v)
    return m


t0 = time.time()
for i in range(0, len(P), a.lot):
    lot = P[i:i + a.lot]
    vec = modele.encode(["passage: " + p["texte"] for p in lot], normalize_embeddings=True, batch_size=a.lot)
    col.add(ids=[p["id"] for p in lot], documents=[p["texte"] for p in lot],
            embeddings=vec.tolist(), metadatas=[meta(p) for p in lot])
    if i % (a.lot * 20) == 0:
        print(f"{i + len(lot)}/{len(P)}  {time.time() - t0:.0f} s", flush=True)
print("index terminé :", col.count(), "passages,", f"{time.time() - t0:.0f} s")
