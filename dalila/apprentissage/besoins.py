"""Liste pour l'AFI des questions que Dalila traite mal (BF12, BF24), à partir des tours journalisés (anonymisés).

    .venv\\Scripts\\python -m dalila.apprentissage.besoins                 les 30 premières, les plus fréquentes d'abord
    .venv\\Scripts\\python -m dalila.apprentissage.besoins --csv besoins.csv --depuis 2026-11-01 --tout

Pour chaque question (regroupée à l'écriture près) : la langue, combien de fois elle a été posée, combien de fois
Dalila a répondu par le repli (pas de réponse fiable), combien de fois elle a été notée « pas utile » ou « utile ».
Par défaut, seulement les questions qui ont posé problème (repli ou « pas utile »). Rien n'est envoyé hors du serveur.
"""
import argparse, csv, re, sys, unicodedata
from dalila.config import db


def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def besoins(depuis=None, tout=False):
    con = db("rw")
    try:
        with con.cursor() as cur:
            cur.execute("SELECT texte_anonymise, langue, source, avis, avis_commentaire, created_at FROM agent_turns "
                        "WHERE texte_anonymise IS NOT NULL AND texte_anonymise <> ''"
                        + (" AND created_at >= %s" if depuis else "") + " ORDER BY created_at",
                        (depuis,) if depuis else ())
            tours = cur.fetchall()
    finally:
        con.close()
    groupes = {}
    for t in tours:
        g = groupes.setdefault(_norm(t["texte_anonymise"]), {
            "question": t["texte_anonymise"], "langues": set(), "posee": 0, "repli": 0, "pas_utile": 0, "utile": 0,
            "derniere_fois": None, "commentaires": []})
        if t.get("avis_commentaire"):
            g["commentaires"].append(t["avis_commentaire"])
        g["langues"].add(t["langue"] or "?")
        g["posee"] += 1
        g["repli"] += t["source"] == "repli"
        g["pas_utile"] += t["avis"] == 0
        g["utile"] += t["avis"] == 1
        g["derniere_fois"] = t["created_at"]
    lignes = [dict(g, langues=",".join(sorted(g["langues"])), commentaires=" | ".join(g["commentaires"][-3:]))
              for g in groupes.values()
              if tout or g["repli"] or g["pas_utile"]]
    return sorted(lignes, key=lambda g: (-(g["repli"] + g["pas_utile"]), -g["posee"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--depuis", help="date AAAA-MM-JJ")
    ap.add_argument("--tout", action="store_true", help="aussi les questions sans problème")
    ap.add_argument("--nombre", type=int, default=30)
    a = ap.parse_args()
    L = besoins(a.depuis, a.tout)
    champs = ["question", "langues", "posee", "repli", "pas_utile", "utile", "commentaires", "derniere_fois"]
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, champs)
            w.writeheader()
            w.writerows({k: l[k] for k in champs} for l in L)
        print(f"{len(L)} questions écrites dans {a.csv}")
        return
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{'posée':>5} {'repli':>5} {'pas utile':>9} {'utile':>5}  langue  question")
    for l in L[:a.nombre]:
        print(f"{l['posee']:>5} {l['repli']:>5} {l['pas_utile']:>9} {l['utile']:>5}  {l['langues']:<6}  {l['question'][:90]}")
    print(f"({len(L)} questions ; --csv pour toutes les exporter)")


if __name__ == "__main__":
    main()
