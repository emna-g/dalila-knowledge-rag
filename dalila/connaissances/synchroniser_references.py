"""Upsert canonical reference CSVs into their MariaDB mirrors without deleting rows.

Run after applying the targeted additive migration:
    python -m dalila.connaissances.synchroniser_references
Add --surfaces to recompute the optional union of AFI lot contours.

This is an upsert-only synchronization: references removed from the CSVs are
intentionally left in MariaDB and must be reconciled manually after review.
"""

import argparse
import csv

from dalila.config import RACINE, db
from dalila.traitement.references import (
    alias_zones,
    derniers_prix_publies_par_zone,
    gouvernorats_par_code,
    groupes_developpement_regional_par_zone,
    normaliser_nom_lieu,
    prix_site_afi_par_zone,
)


def _verifier_cles_uniques(nom, lignes, cle):
    vues = set()
    for ligne in lignes:
        valeur = cle(ligne)
        if valeur in vues:
            raise ValueError(f"Clé dupliquée dans les références {nom}: {valeur!r}")
        vues.add(valeur)


def synchroniser(cur, inclure_surfaces=False):
    gouvernorats = gouvernorats_par_code()
    alias = list(alias_zones())
    with open(RACINE / "db" / "corrections" / "lots_a_confirmer.csv", encoding="utf-8-sig", newline="") as fichier:
        lots_a_confirmer = list(csv.DictReader(fichier))
    groupes = groupes_developpement_regional_par_zone()
    prix_publies = derniers_prix_publies_par_zone()
    prix_site = prix_site_afi_par_zone()
    surfaces = []
    if inclure_surfaces:
        from dalila.connaissances.charger import surfaces_contours

        surfaces = surfaces_contours(cur)

    alias_rows = [(r["zone_id"], r["alias"], r["langue"], r["source"]) for r in alias]
    confirmation_rows = [
        (int(row["lot_id"]), int(row["etape_afi"]), row["raison"], row["source"])
        for row in lots_a_confirmer
    ]
    group_rows = [
        (zone_id, valeur["groupe"], valeur["delegation"], valeur["source"])
        for zone_id, valeur in groupes.items()
    ]
    published_rows = [
        (zone_id, valeur["prix_m2_dt"], valeur["source"], valeur["date_source"])
        for zone_id, valeur in prix_publies.items()
    ]
    site_rows = [
        (zone_id, valeur["nom_sur_la_page"], valeur["prix_m2_dt"],
         valeur["prix_m2_subventionne_dt"], valeur["source"], valeur["date_source"])
        for zone_id, valeur in prix_site.items()
    ]

    _verifier_cles_uniques(
        "alias_zones.csv",
        alias_rows,
        lambda row: (row[0].casefold(), normaliser_nom_lieu(row[1])),
    )
    _verifier_cles_uniques("lots_a_confirmer.csv", confirmation_rows, lambda row: row[0])
    _verifier_cles_uniques("groupes_developpement_regional.csv", group_rows, lambda row: row[0])
    _verifier_cles_uniques("derniers_prix_publies.csv", published_rows, lambda row: row[0])
    _verifier_cles_uniques("prix_site_afi.csv", site_rows, lambda row: row[0])
    _verifier_cles_uniques("surfaces AFI", surfaces, lambda row: row[0])

    cur.executemany(
        "INSERT INTO dalila_gouvernorats (code,nom_fr,nom_ar,source) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE nom_fr=VALUES(nom_fr), nom_ar=VALUES(nom_ar), source=VALUES(source)",
        [
            (
                code,
                valeur["nom_fr"],
                valeur["nom_ar"],
                valeur.get("source", "db/reference/gouvernorats.csv"),
            )
            for code, valeur in gouvernorats.items()
        ],
    )

    cur.executemany(
        "INSERT INTO dalila_zone_alias (zone_id,alias,langue,source) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE langue=VALUES(langue), source=VALUES(source)",
        alias_rows,
    )
    cur.executemany(
        "INSERT INTO dalila_lots_a_confirmer (lot_id,etape_afi,raison,source) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE etape_afi=VALUES(etape_afi), raison=VALUES(raison), source=VALUES(source)",
        confirmation_rows,
    )

    cur.executemany(
        "INSERT INTO dalila_zone_groupe_dr (zone_id,groupe,delegation,source) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE groupe=VALUES(groupe), delegation=VALUES(delegation), source=VALUES(source)",
        group_rows,
    )

    cur.executemany(
        "INSERT INTO dalila_prix_publies (zone_id,prix_m2_dt,source,date_source) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE prix_m2_dt=VALUES(prix_m2_dt), source=VALUES(source), "
        "date_source=VALUES(date_source)",
        published_rows,
    )

    cur.executemany(
        "INSERT INTO dalila_prix_site "
        "(zone_id,nom_sur_la_page,prix_m2_dt,prix_m2_subventionne_dt,source,date_source) "
        "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
        "nom_sur_la_page=VALUES(nom_sur_la_page), prix_m2_dt=VALUES(prix_m2_dt), "
        "prix_m2_subventionne_dt=VALUES(prix_m2_subventionne_dt), source=VALUES(source), "
        "date_source=VALUES(date_source)",
        site_rows,
    )

    if inclure_surfaces:
        cur.executemany(
            "INSERT INTO dalila_zone_surface_contours (zone_id,surface_m2,nb_contours) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE surface_m2=VALUES(surface_m2), nb_contours=VALUES(nb_contours)",
            surfaces,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synchronise les références DALILA sans supprimer de lignes.")
    parser.add_argument(
        "--surfaces",
        action="store_true",
        help="recalculer les surfaces issues des contours KML AFI",
    )
    args = parser.parse_args(argv)

    con = db("ingest")
    try:
        con.autocommit(False)
        with con.cursor() as cur:
            synchroniser(cur, inclure_surfaces=args.surfaces)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
