"""Remplit les tables dalila_* depuis le dossier dalila_fusion (fusion vérifiée, avec ses champs de provenance).

python -m backend.ingest.charger_fusion
- Pas de comptes stockés : les nombres de lots par zone sont calculés par les vues.
- Passages : les doublons exacts (même texte) ne sont chargés qu'une fois ; les passages « secondaires »
  sont chargés avec leur étiquette (on peut les filtrer en SQL).
"""
import csv, json, re, collections
from backend.config import DONNEES, db


def charger(p):
    return json.load(open(DONNEES / p, encoding="utf-8"))


def main():
    con = db("root")
    cur = con.cursor()
    for t in ("dalila_gouvernorats", "dalila_zones", "dalila_zone_distances", "dalila_zone_equipements",
              "dalila_services_proches", "dalila_lot_statut", "dalila_cahiers", "dalila_sources", "dalila_passages"):
        cur.execute(f"DELETE FROM {t}")
    src_carte = "carte publique afi.e-industrie.gov.tn (lue le 2026-11-25)"
    cur.executemany("INSERT INTO dalila_gouvernorats VALUES (%s,%s,%s,%s)",
                    [(g["code"], g["nom_fr"], g["nom_ar"], src_carte) for g in charger("1_zones_et_lots/gouvernorats.json")])
    zones = charger("1_zones_et_lots/zones.json")
    for z in zones:
        cur.execute("INSERT INTO dalila_zones VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (
            z["zone_id"], z["nom_fr"], z["nom_ar"], z["gouvernorat"]["code"], z["lat"], z["lng"],
            z["surface_totale_m2"], z["surface_amenagee_m2"], z["prix_m2_dt"] or None,
            int(bool(z["zone_developpement_regional"])), int(bool(z["sur_carte_en_ligne"])),
            int(bool(z["zone_visible_dans_la_base"])), "; ".join(z.get("sources") or [])))
        for k, v in (z.get("distances") or {}).items():
            if v and v.get("km") is not None:
                cur.execute("INSERT INTO dalila_zone_distances VALUES (%s,%s,%s,%s,%s)",
                            (z["zone_id"], k, v.get("nom"), v["km"], v.get("source")))
        for k, v in (z.get("equipements") or {}).items():
            cur.execute("INSERT INTO dalila_zone_equipements VALUES (%s,%s,%s,%s,%s)",
                        (z["zone_id"], k, str(v.get("valeur")), v.get("unite"), v.get("source")))
    cur.executemany("INSERT INTO dalila_services_proches (zone_id,categorie,nom,distance_km,lat,lng,source) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    [(s["zone_id"], s["categorie"], s["nom"], s["distance_km"], s["lat"], s["lng"], s["source"])
                     for s in charger("1_zones_et_lots/services_proches.json")])
    cur.executemany("INSERT INTO dalila_lot_statut VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    [(l["lot_id"], l["zone_id"], l["statut"], l.get("libelle_carte"), l.get("etape_retenue"),
                      int(bool(l.get("a_confirmer"))), l.get("source_statut"))
                     for l in charger("1_zones_et_lots/lots.json")])
    cur.executemany("INSERT INTO dalila_cahiers (zone_id,zone,annee,fichier_texte,lecture,lien_pdf,remarque) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    [(r["zone_id"], r["zone"], r["annee"], r["fichier_texte"], r["lecture"], r["lien_pdf"], r["remarque"])
                     for r in csv.DictReader(open(DONNEES / "2_cahiers_des_charges/index.csv", encoding="utf-8-sig"))])
    # passages : doublons exacts retirés au chargement
    vus, garde, doublons = set(), [], 0
    for l in open(DONNEES / "6_pret_pour_le_llm/passages.jsonl", encoding="utf-8"):
        p = json.loads(l)
        cle = re.sub(r"\s+", " ", p["texte"]).strip()
        if cle in vus or p.get("doublon_de"):
            doublons += 1
            continue
        vus.add(cle)
        garde.append(p)
    cur.executemany(
        "INSERT INTO dalila_passages (id,type,titre,texte,source_url,date_source,langue,zone_id,page,article,texte_ocr,"
        "kb_id,pertinence,contient_chiffre,longueur) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        [(p["id"], p["type"], (p.get("titre") or "")[:500], p["texte"], (p.get("source_url") or "")[:700],
          p.get("date_source"), p.get("langue"), p.get("zone_id") or None, p.get("page"), (p.get("article") or None),
          int(bool(p.get("texte_ocr"))), p.get("kb_id"), p.get("pertinence") or "principale",
          int(bool(p.get("contient_chiffre"))), len(p["texte"])) for p in garde])
    src = collections.defaultdict(lambda: [None, None, 0])
    for p in garde:
        s = src[(p.get("source_url") or "")[:700]]
        s[0], s[1] = p["type"], p.get("date_source")
        s[2] += 1
    cur.executemany("INSERT INTO dalila_sources (source_url,organisme,lu_le,nb_passages) VALUES (%s,%s,%s,%s)",
                    [(u, (re.search(r"https?://(?:www\.)?([^/]+)", u) or [None, "base AFI"])[1], d, n)
                     for u, (t, d, n) in src.items()])
    for t in ("dalila_zones", "dalila_lot_statut", "dalila_passages", "dalila_sources", "v_pub_lots_disponibles"):
        cur.execute(f"SELECT COUNT(*) AS n FROM {t}")
        print(t, cur.fetchone()["n"])
    print("doublons écartés :", doublons)


if __name__ == "__main__":
    main()
