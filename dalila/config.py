"""Configuration de Dalila : tout ce qui change d'une machine à l'autre est ici ou dans le fichier .env.

Variables (fichier .env à la racine du dépôt, jamais dans git ; voir .env.example) :
  DB_HOST, DB_PORT, DB_NAME, DB_ROOT_PASSWORD, DB_RO_USER, DB_RO_PASSWORD, DB_RW_USER, DB_RW_PASSWORD
  DALILA_DONNEES   dossier des données hors git (défaut : donnees/ ; le corpus est dans donnees/corpus/)
  DALILA_MODELES   dossier des modèles d'embeddings (défaut : modeles/)
  DALILA_MODELE    modèle de recherche : "e5" (multilingual-e5-small), "bge" (BGE-M3) ou "qwen3" (Qwen3-Embedding-0.6B) ;
                   ses vecteurs doivent être calculés (dalila.connaissances.vectoriser). Choix : DECISIONS.md.
  DALILA_RERANKER  0 (défaut) ; 1 : reclassement par bge-reranker-v2-m3
"""
import os, pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent


def _charger_env():
    f = pathlib.Path(os.environ.get("DALILA_ENV", RACINE / ".env"))
    if f.exists():
        for ligne in f.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.lstrip().startswith("#"):
                k, v = ligne.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_charger_env()
DONNEES = pathlib.Path(os.environ.get("DALILA_DONNEES", RACINE / "donnees"))
MODELES = pathlib.Path(os.environ.get("DALILA_MODELES", RACINE / "modeles"))
os.environ.setdefault("HF_HOME", str(MODELES))
LEXIQUE = RACINE / "dalila" / "langue" / "lexique"
ONTOLOGIE = RACINE / "ontology"
MODELES_RECHERCHE = {
    "e5": {"nom": "intfloat/multilingual-e5-small", "colonne": "embedding_e5", "dim": 384,
           "prefixe_question": "query: ", "prefixe_passage": "passage: "},
    "bge": {"nom": "BAAI/bge-m3", "colonne": "embedding_bge", "dim": 1024,
            "prefixe_question": "", "prefixe_passage": ""},
    "qwen3": {"nom": "Qwen/Qwen3-Embedding-0.6B", "colonne": "embedding_qwen", "dim": 1024,
              "prefixe_question": "Instruct: Given a question, retrieve passages that answer the question\nQuery: ",
              "prefixe_passage": ""},
}
MODELE = os.environ.get("DALILA_MODELE", "bge")  # choix mesuré : docs/decisions.md
RERANKER = os.environ.get("DALILA_RERANKER", "0") == "1"
NOM_RERANKER = "BAAI/bge-reranker-v2-m3"


def db(role="ro"):
    """Connexion MariaDB. role : 'ro' (lecture des vues), 'rw' (tables agent_*), 'root' (construction)."""
    import pymysql
    user = {"ro": os.environ.get("DB_RO_USER", "dalila_ro"), "rw": os.environ.get("DB_RW_USER", "dalila_rw"),
            "root": "root"}[role]
    pwd = {"ro": os.environ.get("DB_RO_PASSWORD"), "rw": os.environ.get("DB_RW_PASSWORD"),
           "root": os.environ.get("DB_ROOT_PASSWORD")}[role]
    return pymysql.connect(host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", 3306)),
                           user=user, password=pwd, database=os.environ.get("DB_NAME", "afi"), charset="utf8mb4",
                           autocommit=True, cursorclass=pymysql.cursors.DictCursor)
