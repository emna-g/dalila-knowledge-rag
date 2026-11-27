"""Charge les tables dalila_* sans effacement par défaut.

python -m dalila.connaissances.charger
python -m dalila.connaissances.charger --replace-dalila-data --confirm-replace-dalila-data

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
import argparse
import collections
import csv
import json
import math
import re
import warnings
from dalila.config import DONNEES, RACINE, db
from dalila.connaissances.synchroniser_references import synchroniser as synchroniser_references
from dalila.traitement.references import alias_zones, nom_gouvernorat

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
    cur.execute("SELECT zone_id, nom_fr, nom_ar, gouvernorat_code, zone_developpement_regional dr "
                "FROM v_pub_zones ORDER BY zone_id")
    zones = cur.fetchall()
    alias = collections.defaultdict(list)
    for valeur in alias_zones():
        alias[valeur["zone_id"]].append(valeur["alias"])
    cur.execute("SELECT zone_id, type, nom FROM v_pub_zone_distances")
    proches = collections.defaultdict(list)
    for r in cur.fetchall():
        if r["type"] in noms and r["nom"]:
            proches[r["zone_id"]].append(f"{noms[r['type']]} {r['nom']}")
    out = []
    for z in zones:
        nom_gouv = nom_gouvernorat(z["gouvernorat_code"])
        nom_gouv_ar = nom_gouvernorat(z["gouvernorat_code"], "ar")
        texte = f"Zone industrielle {z['nom_fr']}"
        if z["nom_ar"]:
            texte += f" ({z['nom_ar']})"
        texte += ". "
        if nom_gouv:
            texte += f"Gouvernorat de {nom_gouv}"
            if nom_gouv_ar:
                texte += f" ({nom_gouv_ar})"
            texte += ". "
        if z["dr"] == 1:
            texte += "Zone de développement régional. "
        elif z["dr"] == 0:
            texte += "Zone hors développement régional. "
        if alias[z["zone_id"]]:
            texte += f"Autres noms : {', '.join(sorted(alias[z['zone_id']]))}. "
        if proches[z["zone_id"]]:
            texte += f"Infrastructures de référence : {', '.join(sorted(proches[z['zone_id']]))}. "
        texte += "Le prix au m², les lots disponibles et les distances sont lus en direct dans la base de l'AFI."
        out.append({"id": f"zone{z['zone_id']}"[:12], "type": "fiche_zone", "titre": f"Zone {z['nom_fr']}",
                    "texte": texte, "source_url": "base AFI (vues v_pub_*), lue en direct", "langue": "fr",
                    "zone_id": z["zone_id"]})
    return out


def surfaces_contours(cur):
    """Surface couverte par les contours des lots de chaque zone (chevauchements comptés une fois), en m²."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    cur.execute("SELECT TRIM(ZONE_ID) z, LOT_COORDINATES k FROM lots_kml")
    par = collections.defaultdict(list)
    invalides = 0
    for r in cur.fetchall():
        if not r["z"] or not r["k"]:
            invalides += 1
            continue
        try:
            pts = []
            for point in r["k"].split():
                coordonnees = point.split(",")
                if len(coordonnees) < 2:
                    raise ValueError
                longitude, latitude = map(float, coordonnees[:2])
                if not math.isfinite(longitude) or not math.isfinite(latitude):
                    raise ValueError
                if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                    raise ValueError
                pts.append((longitude, latitude))
        except ValueError:
            invalides += 1
            continue
        if len(pts) < 3:
            invalides += 1
            continue
        polygon = Polygon(pts).buffer(0)
        if polygon.is_empty or polygon.area <= 0:
            invalides += 1
            continue
        par[r["z"]].append(pts)
    if invalides:
        warnings.warn(f"{invalides} contour(s) KML absent(s) ou invalide(s) ignoré(s)", RuntimeWarning)

    out = []
    for z, polys in par.items():
        lat0 = math.radians(sum(p[1] for ps in polys for p in ps) / sum(len(ps) for ps in polys))
        R = 6371008.8  # projection locale : écart de moins de 1 % à l'échelle d'une zone
        geoms = [g for g in (Polygon([(math.radians(x) * R * math.cos(lat0), math.radians(y) * R) for x, y in ps]).buffer(0)
                             for ps in polys) if g.area > 0]
        if geoms:
            out.append((z, round(unary_union(geoms).area), len(geoms)))
    return out


_TABLES_DALILA = (
    "dalila_gouvernorats",
    "dalila_corrections",
    "dalila_lots_a_confirmer",
    "dalila_zone_alias",
    "dalila_zone_groupe_dr",
    "dalila_prix_publies",
    "dalila_prix_site",
    "dalila_zone_surface_contours",
    "dalila_echantillon_eval",
    "dalila_cahiers",
    "dalila_sources",
    "dalila_passages",
)


def analyser_arguments(argv=None):
    parser = argparse.ArgumentParser(description="Charge les données DALILA sans supprimer de lignes par défaut.")
    parser.add_argument(
        "--replace-dalila-data",
        action="store_true",
        help="effacer les données DALILA avant rechargement (destructif)",
    )
    parser.add_argument(
        "--confirm-replace-dalila-data",
        action="store_true",
        help="confirmation obligatoire avec --replace-dalila-data",
    )
    parser.add_argument(
        "--surfaces",
        action="store_true",
        help="recalculer les surfaces issues des contours KML AFI",
    )
    args = parser.parse_args(argv)
    if args.replace_dalila_data != args.confirm_replace_dalila_data:
        parser.error(
            "--replace-dalila-data et --confirm-replace-dalila-data doivent être fournis ensemble."
        )
    return args


def effacer_donnees_dalila(cur, confirmer=False):
    if not confirmer:
        raise ValueError("Effacement refusé sans confirmation explicite.")
    for table in _TABLES_DALILA:
        cur.execute(f"DELETE FROM {table}")


def role_connexion(args):
    return "root" if args.replace_dalila_data else "ingest"


def _sources_passages(passages):
    agregats = collections.defaultdict(lambda: [None, 0])
    for passage in passages:
        url = (passage.get("source_url") or "")[:700]
        valeur = agregats[url]
        date_source = passage.get("date_source")
        if valeur[0] is not None and date_source is not None and valeur[0] != date_source:
            raise ValueError(f"Dates de source contradictoires pour {url!r}.")
        valeur[0] = valeur[0] or date_source
        valeur[1] += 1

    prefixes = {}
    for url in agregats:
        prefixe = url[:500].casefold()
        precedent = prefixes.get(prefixe)
        if precedent is not None and precedent != url:
            raise ValueError("Deux URL de source partagent la clé unique de 500 caractères.")
        prefixes[prefixe] = url

    return [
        (url, (re.search(r"https?://(?:www\.)?([^/]+)", url) or [None, "base AFI"])[1], date_source, nombre)
        for url, (date_source, nombre) in agregats.items()
    ]


def _charger(cur, remplacer=False, surfaces=False):
    if remplacer:
        effacer_donnees_dalila(cur, confirmer=True)

    synchroniser_references(cur, inclure_surfaces=surfaces)
    vide = lambda v: None if v == "" else v
    cur.executemany(
        "INSERT INTO dalila_corrections "
        "(table_afi,cle,champ,valeur_afi,valeur_corrigee,appliquee,source,raison) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
        "valeur_afi=VALUES(valeur_afi), valeur_corrigee=VALUES(valeur_corrigee), "
        "appliquee=VALUES(appliquee), source=VALUES(source), raison=VALUES(raison)",
        [(r["table_afi"], r["cle"], r["champ"], vide(r["valeur_afi"]), vide(r["valeur_corrigee"]),
          int(r["appliquee"]), r["source"], r["raison"]) for r in lire_csv(CORR / "dalila_corrections.csv")],
    )
    for r in lire_csv(REF / "cahiers.csv"):
        valeurs = (r["zone_id"] or None, r["zone"], r["annee"], r["lecture"], r["lien_pdf"], r["remarque"])
        cur.execute(
            "INSERT INTO dalila_cahiers (zone_id,zone,annee,lecture,lien_pdf,remarque) "
            "SELECT %s,%s,%s,%s,%s,%s FROM DUAL WHERE NOT EXISTS ("
            "SELECT 1 FROM dalila_cahiers WHERE zone_id <=> %s AND zone <=> %s AND annee <=> %s "
            "AND lecture <=> %s AND lien_pdf <=> %s AND remarque <=> %s)",
            valeurs + valeurs,
        )

    with open(DONNEES / "corpus" / "passages.jsonl", encoding="utf-8") as fichier:
        passages = [json.loads(ligne) for ligne in fichier]
    passages += reponses_afi(cur) + fiches_zones(cur)
    cols = [r["Field"] for r in (cur.execute("SHOW COLUMNS FROM dalila_passages LIKE 'embedding%%'"), cur.fetchall())[1]]
    raz = ", ".join(f"{col} = IF(texte <=> VALUES(texte), {col}, NULL)" for col in cols)
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
          int(bool(p.get("contient_chiffre"))), len(p["texte"])) for p in passages],
    )
    cur.executemany(
        "INSERT INTO dalila_sources (source_url,organisme,lu_le,nb_passages) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE organisme=VALUES(organisme), lu_le=VALUES(lu_le), nb_passages=VALUES(nb_passages)",
        _sources_passages(passages),
    )


def main(argv=None):
    args = analyser_arguments(argv)
    con = db(role_connexion(args))
    con.autocommit(False)
    try:
        with con.cursor() as cur:
            _charger(cur, remplacer=args.replace_dalila_data, surfaces=args.surfaces)
            cols = [r["Field"] for r in (cur.execute(
                "SHOW COLUMNS FROM dalila_passages LIKE 'embedding%%'"
            ), cur.fetchall())[1]]
            for table in ("v_pub_zones", "v_pub_lots", "v_pub_lots_disponibles", "dalila_passages", "dalila_sources"):
                cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
                print(table, cur.fetchone()["n"])
            cur.execute("SELECT type, pertinence, COUNT(*) n FROM dalila_passages GROUP BY 1, 2 ORDER BY 1, 2")
            print("passages :", {f"{r['type']}/{r['pertinence']}": r["n"] for r in cur.fetchall()})
            cur.execute("SELECT etat, COUNT(*) AS n FROM v_dalila_corrections_etat GROUP BY etat")
            print("corrections :", {r["etat"]: r["n"] for r in cur.fetchall()})
            cur.execute("SELECT " + ", ".join(f"SUM({col} IS NULL) AS {col}" for col in cols) + " FROM dalila_passages")
            print("passages sans vecteur (à calculer par vectoriser) :",
                  {key: int(value or 0) for key, value in cur.fetchone().items()})
            con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
