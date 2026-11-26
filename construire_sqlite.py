"""Construit la base de chiffres de Dalila en SQLite (un seul fichier, pas de serveur).

python construire_sqlite.py --donnees donnees/dalila_fusion --sortie base/dalila.sqlite

C'est la SOURCE UNIQUE des chiffres (prix, surfaces, statuts, distances). Le graphe et les passages n'en
contiennent pas (prix et statuts) : Dalila les lit ici au moment de répondre.
Mêmes tables et mêmes vues v_pub_* que base_mariadb/schema.sql (gardé pour un branchement MariaDB plus tard).
"""
import argparse, json, csv, sqlite3, pathlib

ap = argparse.ArgumentParser()
ap.add_argument("--donnees", required=True)
ap.add_argument("--sortie", default="base/dalila.sqlite")
a = ap.parse_args()
D, OUT = pathlib.Path(a.donnees), pathlib.Path(a.sortie)
OUT.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    OUT.unlink()  # fichier généré par ce script
db = sqlite3.connect(OUT)
load = lambda p: json.load(open(D / p, encoding="utf-8"))  # noqa: E731

db.executescript("""
CREATE TABLE gouvernorats (code INTEGER PRIMARY KEY, nom_fr TEXT, nom_ar TEXT);
CREATE TABLE zones (zone_id TEXT PRIMARY KEY, nom_fr TEXT, nom_ar TEXT, gouvernorat_code INTEGER, lat REAL, lng REAL,
  surface_totale_m2 REAL, surface_amenagee_m2 REAL, prix_m2_dt REAL, zone_developpement_regional INTEGER,
  sur_carte_en_ligne INTEGER, zone_visible_dans_la_base INTEGER, lots_disponibles INTEGER,
  lots_disponibles_a_confirmer INTEGER, lots_mis_aux_encheres INTEGER, lots_reserves INTEGER, lots_attribues INTEGER,
  source TEXT);
CREATE TABLE zone_distances (zone_id TEXT, type TEXT, nom TEXT, km REAL, source TEXT);
CREATE TABLE zone_equipements (zone_id TEXT, type TEXT, valeur TEXT, unite TEXT, source TEXT);
CREATE TABLE lots (lot_id INTEGER PRIMARY KEY, zone_id TEXT, lot_num TEXT, surface_m2 REAL, statut TEXT,
  libelle_carte TEXT, a_confirmer INTEGER, etape_retenue INTEGER, polygone INTEGER, source_statut TEXT);
CREATE TABLE services_proches (zone_id TEXT, categorie TEXT, nom TEXT, distance_km REAL, lat REAL, lng REAL, source TEXT);
CREATE TABLE cahiers_des_charges (zone_id TEXT, zone TEXT, annee TEXT, fichier_texte TEXT, lecture TEXT, lien_pdf TEXT,
  remarque TEXT);
CREATE TABLE connaissances_afi (id INTEGER PRIMARY KEY, question TEXT, reponse TEXT, mots_cles TEXT, langue TEXT,
  actif INTEGER, source TEXT);
CREATE INDEX i_lots_zone ON lots(zone_id);
CREATE INDEX i_lots_statut ON lots(statut);
""")
db.executemany("INSERT INTO gouvernorats VALUES (?,?,?)",
               [(g["code"], g["nom_fr"], g["nom_ar"]) for g in load("1_zones_et_lots/gouvernorats.json")])
for z in load("1_zones_et_lots/zones.json"):
    c = z.get("lots") or {}
    db.execute("INSERT INTO zones VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        z["zone_id"], z["nom_fr"], z["nom_ar"], z["gouvernorat"]["code"], z["lat"], z["lng"],
        z["surface_totale_m2"], z["surface_amenagee_m2"], z["prix_m2_dt"], int(bool(z["zone_developpement_regional"])),
        int(bool(z["sur_carte_en_ligne"])), int(bool(z["zone_visible_dans_la_base"])), c.get("disponible"),
        c.get("dont_a_confirmer"), c.get("mis_aux_encheres"), c.get("reserve"), c.get("attribue"),
        "; ".join(z.get("sources") or [])))
    for k, v in (z.get("distances") or {}).items():
        if v:
            db.execute("INSERT INTO zone_distances VALUES (?,?,?,?,?)", (z["zone_id"], k, v.get("nom"), v.get("km"), v.get("source")))
    for k, v in (z.get("equipements") or {}).items():
        db.execute("INSERT INTO zone_equipements VALUES (?,?,?,?,?)",
                   (z["zone_id"], k, str(v.get("valeur")), v.get("unite"), v.get("source")))
db.executemany("INSERT INTO lots VALUES (?,?,?,?,?,?,?,?,?,?)", [
    (l["lot_id"], l["zone_id"], str(l["lot_num"]), l["surface_m2"], l["statut"], l.get("libelle_carte"),
     int(bool(l.get("a_confirmer"))), l.get("etape_retenue"), int(bool(l.get("polygone"))), l.get("source_statut"))
    for l in load("1_zones_et_lots/lots.json")])
db.executemany("INSERT INTO services_proches VALUES (?,?,?,?,?,?,?)", [
    (s["zone_id"], s["categorie"], s["nom"], s["distance_km"], s["lat"], s["lng"], s["source"])
    for s in load("1_zones_et_lots/services_proches.json")])
db.executemany("INSERT INTO cahiers_des_charges VALUES (?,?,?,?,?,?,?)", [
    (r["zone_id"], r["zone"], r["annee"], r["fichier_texte"], r["lecture"], r["lien_pdf"], r["remarque"])
    for r in csv.DictReader(open(D / "2_cahiers_des_charges/index.csv", encoding="utf-8-sig"))])
db.executemany("INSERT INTO connaissances_afi VALUES (?,?,?,?,?,?,?)", [
    (k["id"], k["question"], k["reponse"], k["mots_cles"], k["langue"], int(bool(k["actif"])), k["source"])
    for k in load("3_connaissances_afi/base_connaissances_afi.json")])
db.executescript("""
CREATE VIEW v_pub_zones AS
SELECT z.zone_id, z.nom_fr, z.nom_ar, g.nom_fr AS gouvernorat_fr, g.nom_ar AS gouvernorat_ar, z.lat, z.lng,
 z.surface_totale_m2, z.surface_amenagee_m2, z.prix_m2_dt, z.zone_developpement_regional,
 z.lots_disponibles, z.lots_disponibles_a_confirmer, z.lots_mis_aux_encheres
FROM zones z LEFT JOIN gouvernorats g ON g.code = z.gouvernorat_code WHERE z.zone_visible_dans_la_base = 1;
CREATE VIEW v_pub_lots AS
SELECT l.lot_id, l.zone_id, z.nom_fr AS zone_fr, l.lot_num, l.surface_m2, l.statut, l.libelle_carte, l.a_confirmer,
 z.prix_m2_dt
FROM lots l JOIN zones z ON z.zone_id = l.zone_id WHERE z.zone_visible_dans_la_base = 1 AND l.statut <> 'non_affiche';
CREATE VIEW v_pub_lots_disponibles AS SELECT * FROM v_pub_lots WHERE statut = 'disponible';
""")
db.commit()
n = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
     ("gouvernorats", "zones", "lots", "zone_distances", "services_proches", "cahiers_des_charges", "connaissances_afi",
      "v_pub_zones", "v_pub_lots_disponibles")}
n["lots_disponibles_a_confirmer"] = db.execute("SELECT COUNT(*) FROM v_pub_lots_disponibles WHERE a_confirmer=1").fetchone()[0]
print(json.dumps(n, indent=1))
