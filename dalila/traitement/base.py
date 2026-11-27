"""Ce que partagent tous les outils : connexion en lecture seule, sources.

Les outils ne lisent que les vues publiques `v_pub_*` et nos tables de références, par le compte `dalila_ro` :
ils ne peuvent ni écrire ni voir les acquéreurs. Chaque résultat porte ses sources, pour que la réponse les cite et que
le harnais vérifie que chaque chiffre vient bien d'un outil.
"""
import threading
from pydantic import BaseModel
from dalila.config import db


class Source(BaseModel):
    titre: str
    url: str | None = None


SOURCE_BASE = Source(titre="Données de l'AFI (zones, lots, prix, distances), lues dans la base de Dalila")
_local = threading.local()


def q(sql, *p):
    """Exécute une requête en lecture seule (une connexion par fil de calcul)."""
    con = getattr(_local, "con", None)
    if con is None:
        con = _local.con = db("ro")
    con.ping(reconnect=True)
    with con.cursor() as cur:
        cur.execute(sql, p)
        return cur.fetchall()


def nombre(v):
    """Valeur numérique de la base -> int ou float (pas de Decimal : sortie JSON simple)."""
    if v is None:
        return None
    f = float(v)
    return int(f) if f.is_integer() else round(f, 2)
