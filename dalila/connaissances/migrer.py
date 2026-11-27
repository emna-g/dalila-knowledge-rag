"""Crée les tables dalila_* / agent_*, les vues v_pub_* et les comptes dalila_ro / dalila_rw.

python -m dalila.connaissances.migrer      (afi.sql doit déjà être chargé tel quel dans la base)
"""
import os, re
from dalila.config import RACINE, db


def main():
    con = db("root")
    cur = con.cursor()
    for f in sorted((RACINE / "db" / "migrations").glob("*.sql")):
        sql = f.read_text(encoding="utf-8")
        sql = sql.replace(":RO_PASSWORD", os.environ["DB_RO_PASSWORD"]).replace(":RW_PASSWORD", os.environ["DB_RW_PASSWORD"])
        sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
        for stmt in [s.strip() for s in re.split(r";\s*\n", sql) if s.strip()]:
            cur.execute(stmt)
        print("ok", f.name)


if __name__ == "__main__":
    main()
