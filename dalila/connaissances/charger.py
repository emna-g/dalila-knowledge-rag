"""Remplit les tables dalila_* : ce que l'AFI n'a pas dans sa base, et les corrections.

python -m dalila.connaissances.charger      (après dalila.connaissances.migrer ; afi.sql chargé tel quel)

- Zones, lots, distances, équipements et services ne sont PAS copiés : les vues v_pub_* les lisent dans les tables AFI.
- db/reference/ : gouvernorats et cahiers des charges ; db/corrections/ : corrections, lots à confirmer, noms
  alternatifs des zones (voir db/corrections/DESACCORDS.md).
- Passages (dalila_passages) :
    * donnees/corpus/passages.jsonl : textes à citer (préparés par dalila.connaissances.preparer_corpus) ;
    * réponses validées de l'AFI : lues dans sa table chatbot_connaissances (actives), corrections de texte appliquées ;
    * fiches de zone : écrites à partir des vues, SANS chiffre (prix, lots et distances sont lus dans les vues).
  Les vecteurs sont ensuite calculés par dalila.connaissances.vectoriser.
- Pas de comptes stockés : les nombres de lots par zone sont calculés par les vues.
"""
import collections, csv, json, re
from dalila.config import DONNEES, RACINE, db

REF, CORR = RACINE / "db" / "reference", RACINE / "db" / "corrections"
SOURCE_KB = "base de connaissances de l'AFI (table chatbot_connaissances), lue au chargement"


def lire_csv(chemin):
    with open(chemin, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def reponses_afi(cur):
    """Une réponse validée de l'AFI = un passage ; corrections de texte appliquées si l'extrait est encore là."""
    cur.execute("SELECT cle, valeur_afi, valeur_corrigee FROM dalila_corrections "
                "WHERE table_afi = 'chatbot_connaissances' AND appliquee = 1")
    corr = collections.defaultdict(list)
    for r in cur.fetchall():
        corr[int(r["cle"].split(":")[0])].append((r["valeur_afi"], r["valeur_corrigee"]))
    cur.execute("SELECT id, question, reponse, lang FROM chatbot_connaissances WHERE actif = 1 ORDER BY id")
    out = []
    for r in cur.fetchall():
        texte = r["reponse"]
        for ancien, nouveau in corr.get(r["id"], []):
            texte = texte.replace(ancien, nouveau)
        out.append({"id": f"kb{r['id']:04d}", "type": "reponse_validee_afi", "titre": r["question"][:500],
                    "texte": f"{r['question']}\n{texte}", "source_url": SOURCE_KB, "langue": r["lang"],
                    "kb_id": r["id"], "contient_chiffre": bool(re.search(r"\d", texte))})
    return out


def fiches_zones(cur):
    """Une fiche par zone visible, sans chiffre : elle sert à retrouver la zone par son nom ou ses voisins."""
    noms = {"aeroport": "aéroport", "port": "port", "gare": "gare", "autoroute": "autoroute"}
    cur.execute("SELECT zone_id, nom_fr, nom_ar, gouvernorat_fr, gouvernorat_ar, zone_developpement_regional dr "
                "FROM v_pub_zones ORDER BY zone_id")
    zones = cur.fetchall()
    cur.execute("SELECT zone_id, GROUP_CONCAT(alias ORDER BY alias SEPARATOR ', ') a FROM dalila_zone_alias GROUP BY zone_id")
    alias = {r["zone_id"]: r["a"] for r in cur.fetchall()}
    cur.execute("SELECT zone_id, type, nom FROM v_pub_zone_distances")
    proches = collections.defaultdict(list)
    for r in cur.fetchall():
        if r["type"] in noms and r["nom"]:
            proches[r["zone_id"]].append(f"{noms[r['type']]} {r['nom']}")
    out = []
    for z in zones:
        texte = (f"Zone industrielle {z['nom_fr']} ({z['nom_ar']}), gouvernorat de {z['gouvernorat_fr']} "
                 f"({z['gouvernorat_ar']}). "
                 + ("Zone de développement régional. " if z["dr"] else "Zone du littoral (hors développement régional). ")
                 + (f"Autres noms : {alias[z['zone_id']]}. " if z["zone_id"] in alias else "")
                 + (f"Infrastructures de référence : {', '.join(sorted(proches[z['zone_id']]))}. "
                    if proches[z["zone_id"]] else "")
                 + "Le prix au m², les lots disponibles et les distances sont lus en direct dans la base de l'AFI.")
        out.append({"id": f"zone{z['zone_id']}"[:12], "type": "fiche_zone", "titre": f"Zone {z['nom_fr']}",
                    "texte": texte, "source_url": "base AFI (vues v_pub_*), lue en direct", "langue": "fr",
                    "zone_id": z["zone_id"]})
    return out


def surfaces_contours(cur):
    """Surface couverte par les contours des lots de chaque zone (chevauchements comptés une fois), en m²."""
    import math
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    cur.execute("SELECT TRIM(ZONE_ID) z, LOT_COORDINATES k FROM lots_kml")
    par = collections.defaultdict(list)
    for r in cur.fetchall():
        pts = [tuple(map(float, p.split(",")[:2])) for p in (r["k"] or "").split() if p.count(",") >= 1]
        if len(pts) >= 3:
            par[r["z"]].append(pts)
    out = []
    for z, polys in par.items():
        lat0 = math.radians(sum(p[1] for ps in polys for p in ps) / sum(len(ps) for ps in polys))
        R = 6371008.8  # projection locale : écart de moins de 1 % à l'échelle d'une zone
        geoms = [g for g in (Polygon([(math.radians(x) * R * math.cos(lat0), math.radians(y) * R) for x, y in ps]).buffer(0)
                             for ps in polys) if g.area > 0]
        if geoms:
            out.append((z, round(unary_union(geoms).area), len(geoms)))
    return out


def main():
    con = db("root")
    cur = con.cursor()
    for t in ("dalila_gouvernorats", "dalila_corrections", "dalila_lots_a_confirmer", "dalila_zone_alias",
              "dalila_zone_groupe_dr", "dalila_prix_publies", "dalila_prix_site", "dalila_zone_surface_contours", "dalila_cahiers",
              "dalila_sources"):
        cur.execute(f"DELETE FROM {t}")
    cur.executemany("INSERT INTO dalila_zone_surface_contours VALUES (%s,%s,%s)", surfaces_contours(cur))
    cur.executemany("INSERT INTO dalila_prix_site VALUES (%s,%s,%s,%s,%s)",
                    [(r["zone_id"], r["nom_sur_la_page"], r["prix_m2_dt"], r["prix_m2_subventionne_dt"], r["source"])
                     for r in lire_csv(REF / "prix_site_afi.csv")])
    cur.executemany("INSERT INTO dalila_prix_publies VALUES (%s,%s,%s)",
                    [(r["zone_id"], r["prix_m2_dt"], r["source"]) for r in lire_csv(REF / "derniers_prix_publies.csv")])
    cur.executemany("INSERT INTO dalila_zone_groupe_dr VALUES (%s,%s,%s,%s)",
                    [(r["zone_id"], r["groupe"], r["delegation"], r["source"])
                     for r in lire_csv(REF / "groupes_developpement_regional.csv")])
    cur.executemany("INSERT INTO dalila_gouvernorats VALUES (%s,%s,%s,%s)",
                    [(r["code"], r["nom_fr"], r["nom_ar"], "carte publique de l'AFI")
                     for r in lire_csv(REF / "gouvernorats.csv")])
    vide = lambda v: None if v == "" else v  # CSV : cellule vide = NULL
    cur.executemany("INSERT INTO dalila_corrections (table_afi,cle,champ,valeur_afi,valeur_corrigee,appliquee,source,raison) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(r["table_afi"], r["cle"], r["champ"], vide(r["valeur_afi"]), vide(r["valeur_corrigee"]),
                      int(r["appliquee"]), r["source"], r["raison"]) for r in lire_csv(CORR / "dalila_corrections.csv")])
    cur.executemany("INSERT INTO dalila_lots_a_confirmer VALUES (%s,%s,%s,%s)",
                    [(r["lot_id"], r["etape_afi"], r["raison"], r["source"]) for r in lire_csv(CORR / "lots_a_confirmer.csv")])
    cur.executemany("INSERT INTO dalila_zone_alias VALUES (%s,%s,%s,%s)",
                    [(r["zone_id"], r["alias"], r["langue"], r["source"]) for r in lire_csv(CORR / "alias_zones.csv")])
    cur.executemany("INSERT INTO dalila_cahiers (zone_id,zone,annee,lecture,lien_pdf,remarque) VALUES (%s,%s,%s,%s,%s,%s)",
                    [(r["zone_id"] or None, r["zone"], r["annee"], r["lecture"], r["lien_pdf"], r["remarque"])
                     for r in lire_csv(REF / "cahiers.csv")])

    P = [json.loads(l) for l in open(DONNEES / "corpus" / "passages.jsonl", encoding="utf-8")]
    P += reponses_afi(cur) + fiches_zones(cur)
    # Mise à jour sans tout effacer : un passage dont le texte n'a pas changé garde ses vecteurs (longs à calculer) ;
    # texte changé -> vecteurs remis à NULL (vectoriser les recalcule) ; passage disparu -> supprimé.
    cols = [r["Field"] for r in (cur.execute("SHOW COLUMNS FROM dalila_passages LIKE 'embedding%%'"), cur.fetchall())[1]]
    raz = ", ".join(f"{c} = IF(texte <=> VALUES(texte), {c}, NULL)" for c in cols)
    cur.execute("CREATE TEMPORARY TABLE IF NOT EXISTS t_ids (id VARCHAR(12) PRIMARY KEY) "
                "DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci")
    cur.execute("DELETE FROM t_ids")
    cur.executemany("INSERT IGNORE INTO t_ids VALUES (%s)", [(p["id"],) for p in P])
    cur.execute("DELETE FROM dalila_passages WHERE id NOT IN (SELECT id FROM t_ids)")
    cur.executemany(
        "INSERT INTO dalila_passages (id,type,titre,texte,source_url,date_source,langue,zone_id,page,article,texte_ocr,"
        "kb_id,pertinence,contient_chiffre,longueur) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        f"ON DUPLICATE KEY UPDATE {raz}, type=VALUES(type), titre=VALUES(titre), texte=VALUES(texte), "
        "source_url=VALUES(source_url), date_source=VALUES(date_source), langue=VALUES(langue), zone_id=VALUES(zone_id), "
        "page=VALUES(page), article=VALUES(article), texte_ocr=VALUES(texte_ocr), kb_id=VALUES(kb_id), "
        "pertinence=VALUES(pertinence), contient_chiffre=VALUES(contient_chiffre), longueur=VALUES(longueur)",
        [(p["id"], p["type"], (p.get("titre") or "")[:500], p["texte"], (p.get("source_url") or "")[:700],
          p.get("date_source"), p.get("langue"), p.get("zone_id") or None, p.get("page"), p.get("article") or None,
          int(bool(p.get("texte_ocr"))), p.get("kb_id"), p.get("pertinence") or "principale",
          int(bool(p.get("contient_chiffre"))), len(p["texte"])) for p in P])
    src = collections.defaultdict(lambda: [None, 0])
    for p in P:
        s = src[(p.get("source_url") or "")[:700]]
        s[0] = s[0] or p.get("date_source")
        s[1] += 1
    cur.executemany("INSERT INTO dalila_sources (source_url,organisme,lu_le,nb_passages) VALUES (%s,%s,%s,%s)",
                    [(u, (re.search(r"https?://(?:www\.)?([^/]+)", u) or [None, "base AFI"])[1], d, n)
                     for u, (d, n) in src.items()])
    for t in ("v_pub_zones", "v_pub_lots", "v_pub_lots_disponibles", "dalila_passages", "dalila_sources"):
        cur.execute(f"SELECT COUNT(*) AS n FROM {t}")
        print(t, cur.fetchone()["n"])
    cur.execute("SELECT type, pertinence, COUNT(*) n FROM dalila_passages GROUP BY 1, 2 ORDER BY 1, 2")
    print("passages :", {f"{r['type']}/{r['pertinence']}": r["n"] for r in cur.fetchall()})
    cur.execute("SELECT etat, COUNT(*) AS n FROM v_dalila_corrections_etat GROUP BY etat")
    print("corrections :", {r["etat"]: r["n"] for r in cur.fetchall()})
    cur.execute("SELECT " + ", ".join(f"SUM({c} IS NULL) AS {c}" for c in cols) + " FROM dalila_passages")
    print("passages sans vecteur (à calculer par vectoriser) :", {k: int(v or 0) for k, v in cur.fetchone().items()})


if __name__ == "__main__":
    main()
