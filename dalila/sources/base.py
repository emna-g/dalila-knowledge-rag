"""Recopie l'état des sources dans la table agent_source_status (compte dalila_rw), pour l'administration (BF15).

    synchroniser(etat) -> nombre de lignes écrites

Colonnes : url, last_ok_at (dernière lecture réussie), last_error et last_error_at (dernier échec, effacés après une
lecture réussie), content_hash (empreinte de la version lue).
"""
from dalila.config import db

SQL = ("INSERT INTO agent_source_status (url, last_ok_at, last_error, last_error_at, content_hash) "
       "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE last_ok_at=VALUES(last_ok_at), "
       "last_error=VALUES(last_error), last_error_at=VALUES(last_error_at), content_hash=VALUES(content_hash)")


def lignes(etat):
    for url, e in sorted(etat.sources.items()):
        en_echec = e.get("echecs_consecutifs", 0) > 0
        yield (url[:700], e.get("derniere_lecture_ok"), e.get("derniere_erreur") if en_echec else None,
               e.get("derniere_erreur_le") if en_echec else None, e.get("empreinte_lue"))


def synchroniser(etat, connexion=None):
    con = connexion or db("rw")
    try:
        L = list(lignes(etat))
        with con.cursor() as cur:
            cur.executemany(SQL, L)
        return len(L)
    finally:
        if connexion is None:
            con.close()
