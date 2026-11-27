"""Apply selected SQL migrations.

Fresh database initialization (includes historical migrations):
    python -m dalila.connaissances.migrer --all --allow-destructive-history

Existing database (targeted additive repair):
    python -m dalila.connaissances.migrer --migration 004_reference_contract.sql

The full historical sequence also refuses to run when DALILA objects or
accounts already exist in the selected database/server.
"""
import argparse
import os
import re
from dalila.config import RACINE, db

_MIGRATIONS_ADDITIVES_CIBLES = {"004_reference_contract.sql"}


def selectionner_migrations(
    repertoire,
    migration=None,
    toutes=False,
    autoriser_historique_destructif=False,
):
    if migration is not None and toutes:
        raise ValueError("Choisir --migration ou --all, pas les deux.")
    if migration is None and not toutes:
        raise ValueError("Sélectionner explicitement une migration ou utiliser --all.")
    if toutes and not autoriser_historique_destructif:
        raise ValueError(
            "La séquence historique peut supprimer des tables. "
            "Confirmer explicitement avec --allow-destructive-history."
        )
    if autoriser_historique_destructif and not toutes:
        raise ValueError("--allow-destructive-history est réservé à --all.")
    if migration is not None:
        if migration not in _MIGRATIONS_ADDITIVES_CIBLES:
            raise ValueError(f"Migration ciblée non autorisée: {migration}")
        chemin = repertoire / migration
        if not chemin.is_file():
            raise FileNotFoundError(f"Migration introuvable: {migration}")
        return [chemin]
    return sorted(repertoire.glob("*.sql"))


def verifier_base_neuve(cur):
    cur.execute(
        "SELECT TABLE_NAME AS nom FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND (LEFT(TABLE_NAME, 7) = 'dalila_' "
        "OR LEFT(TABLE_NAME, 6) = 'agent_' OR LEFT(TABLE_NAME, 6) = 'v_pub_' "
        "OR LEFT(TABLE_NAME, 9) = 'v_dalila_')"
    )
    objets = sorted(row["nom"] for row in cur.fetchall())
    cur.execute(
        "SELECT CONCAT(User, '@', Host) AS nom FROM mysql.user "
        "WHERE User IN ('dalila_ro', 'dalila_rw', 'dalila_ingest')"
    )
    objets.extend(sorted(row["nom"] for row in cur.fetchall()))
    if objets:
        raise RuntimeError(
            "Initialisation historique refusée : des objets ou comptes DALILA existent déjà "
            f"({', '.join(objets)}). Utiliser une base réellement neuve."
        )


def substituer_secrets(sql, environ=None):
    environ = os.environ if environ is None else environ
    for variable in ("DB_RO_PASSWORD", "DB_RW_PASSWORD", "DB_INGEST_PASSWORD"):
        marqueur = ":" + variable
        if marqueur not in sql:
            continue
        valeur = environ.get(variable)
        if not valeur:
            raise RuntimeError(f"La variable {variable} est requise par la migration sélectionnée.")
        valeur_sql = valeur.replace("\\", "\\\\").replace("'", "''")
        sql = sql.replace(marqueur, valeur_sql)
    return sql


def main(argv=None):
    parser = argparse.ArgumentParser(description="Applique les migrations DALILA.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--migration",
        choices=sorted(_MIGRATIONS_ADDITIVES_CIBLES),
        help="appliquer uniquement une migration additive explicitement autorisée",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="initialiser une base neuve avec toute la séquence historique",
    )
    parser.add_argument(
        "--allow-destructive-history",
        action="store_true",
        help="confirmation obligatoire : les migrations historiques peuvent supprimer des tables",
    )
    args = parser.parse_args(argv)
    try:
        migrations = selectionner_migrations(
            RACINE / "db" / "migrations",
            args.migration,
            args.all,
            args.allow_destructive_history,
        )
    except ValueError as exc:
        parser.error(str(exc))
    scripts = [
        (fichier, substituer_secrets(fichier.read_text(encoding="utf-8")))
        for fichier in migrations
    ]
    con = db("root")
    try:
        cur = con.cursor()
        if args.all:
            verifier_base_neuve(cur)
        for fichier, sql in scripts:
            sql = "\n".join(ligne for ligne in sql.splitlines() if not ligne.strip().startswith("--"))
            for statement in [part.strip() for part in re.split(r";\s*\n", sql) if part.strip()]:
                cur.execute(statement)
            print("ok", fichier.name)
    finally:
        con.close()


if __name__ == "__main__":
    main()
