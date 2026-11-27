import re
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from dalila.connaissances.migrer import selectionner_migrations, verifier_base_neuve
from dalila.connaissances.synchroniser_references import synchroniser
from dalila.connaissances import synchroniser_references
from dalila.traitement.references import (
    alias_zones,
    codes_gouvernorats_pour_nom,
    derniers_prix_publies_par_zone,
    gouvernorats_absents,
    gouvernorats_par_code,
    groupe_developpement_regional,
    groupes_developpement_regional_par_zone,
    nom_gouvernorat,
    prix_site_afi_par_zone,
)


class ReferenceContractTests(unittest.TestCase):
    def test_governorate_reference_resolves_24_codes_from_sourced_names(self):
        gouvernorats = gouvernorats_par_code()

        self.assertEqual(len(gouvernorats), 24)
        self.assertEqual(gouvernorats_absents(), ())
        self.assertEqual(nom_gouvernorat(8), "Gafsa")
        self.assertEqual(nom_gouvernorat(8, "ar"), "قفصة")
        self.assertIn("932001", gouvernorats[8]["source"])
        self.assertEqual(codes_gouvernorats_pour_nom("Sfax"), (20,))
        self.assertEqual(codes_gouvernorats_pour_nom("صفاقس"), (20,))
        self.assertEqual(codes_gouvernorats_pour_nom("Gafsa"), (8,))

    def test_aliases_regions_and_group_are_resolved_from_their_canonical_sources(self):
        aliases = {(row["zone_id"], row["alias"]) for row in alias_zones()}
        groups = groupes_developpement_regional_par_zone()

        self.assertIn(("930607", "ENFIDHA 2"), aliases)
        self.assertEqual(codes_gouvernorats_pour_nom("Grand Tunis"), (1, 2, 3, 4))
        self.assertEqual(groups["931005"]["groupe"], 1)
        self.assertEqual(groupe_developpement_regional("931005", 1), 1)
        self.assertIsNone(groupe_developpement_regional("931005", 0))
        self.assertIsNone(groupe_developpement_regional("931005", None))
        self.assertIsNone(groupe_developpement_regional("unknown-zone", 1))

    def test_price_provenance_keeps_published_site_and_source_dates_separate(self):
        published = derniers_prix_publies_par_zone()["88888"]
        site = prix_site_afi_par_zone()["931005"]

        self.assertEqual(published["prix_m2_dt"], 50)
        self.assertEqual(published["date_source"], date(2026, 11, 25))
        self.assertEqual(site["prix_m2_dt"], 38)
        self.assertEqual(site["prix_m2_subventionne_dt"], Decimal("13.3"))
        self.assertEqual(site["date_source"], date(2026, 11, 25))

    def test_reference_synchronizer_only_upserts_canonical_rows(self):
        class CaptureCursor:
            def __init__(self):
                self.statements = []

            def executemany(self, sql, rows):
                self.statements.append((sql, list(rows)))

        cursor = CaptureCursor()
        synchroniser(cursor)
        first_run = list(cursor.statements)
        synchroniser(cursor)

        self.assertEqual(len(first_run), 6)
        self.assertEqual(cursor.statements, first_run + first_run)
        self.assertTrue(all("INSERT INTO" in sql and "ON DUPLICATE KEY UPDATE" in sql
                            for sql, _ in cursor.statements))
        sql = "\n".join(statement for statement, _ in cursor.statements).upper()
        self.assertFalse(re.search(r"\b(DROP|DELETE|TRUNCATE|REPLACE)\b", sql))
        rows_by_table = {
            re.search(r"INSERT INTO\s+(\w+)", statement, re.I).group(1): rows
            for statement, rows in cursor.statements
        }
        self.assertEqual(len(rows_by_table["dalila_gouvernorats"]), 24)
        self.assertEqual(len(rows_by_table["dalila_zone_groupe_dr"]), 30)
        self.assertEqual(len(rows_by_table["dalila_lots_a_confirmer"]), 1)

    def test_reference_synchronizer_rejects_duplicate_alias_keys_before_writing(self):
        alias = {"zone_id": "930607", "alias": "ENFIDHA 2", "langue": "fr", "source": "test"}

        class CaptureCursor:
            def __init__(self):
                self.statements = []

            def executemany(self, sql, rows):
                self.statements.append((sql, list(rows)))

        cursor = CaptureCursor()
        with patch.object(synchroniser_references, "alias_zones", return_value=(alias, alias)):
            with self.assertRaisesRegex(ValueError, "Clé dupliquée"):
                synchroniser(cursor)
        self.assertEqual(cursor.statements, [])

    def test_targeted_migration_selection_cannot_select_legacy_destructive_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            migration = directory / "004_reference_contract.sql"
            legacy = directory / "001_dalila_tables.sql"
            migration.touch()
            legacy.touch()

            self.assertEqual(
                selectionner_migrations(directory, migration=migration.name),
                [migration],
            )
            with self.assertRaises(ValueError):
                selectionner_migrations(directory, migration=legacy.name)
            with self.assertRaises(ValueError):
                selectionner_migrations(directory)
            with self.assertRaisesRegex(ValueError, "peut supprimer"):
                selectionner_migrations(directory, toutes=True)
            self.assertEqual(
                selectionner_migrations(directory, toutes=True, autoriser_historique_destructif=True),
                [legacy, migration],
            )

    def test_full_historical_migration_refuses_existing_dalila_objects_or_accounts(self):
        class CaptureCursor:
            def __init__(self, result_sets):
                self.result_sets = list(result_sets)
                self.statements = []

            def execute(self, sql):
                self.statements.append(sql)

            def fetchall(self):
                return self.result_sets.pop(0)

        cursor = CaptureCursor([[], []])
        verifier_base_neuve(cursor)
        self.assertIn("information_schema.TABLES", cursor.statements[0])
        self.assertIn("mysql.user", cursor.statements[1])

        existing = CaptureCursor([[{"nom": "dalila_passages"}], []])
        with self.assertRaisesRegex(RuntimeError, "base réellement neuve"):
            verifier_base_neuve(existing)
        existing_view = CaptureCursor([[{"nom": "v_dalila_zones"}], []])
        with self.assertRaisesRegex(RuntimeError, "base réellement neuve"):
            verifier_base_neuve(existing_view)
        existing_account = CaptureCursor([[], [{"nom": "dalila_ingest@%"}]])
        with self.assertRaisesRegex(RuntimeError, "dalila_ingest"):
            verifier_base_neuve(existing_account)

    def test_additive_migration_has_no_destructive_or_afi_data_statements(self):
        migration = (
            Path(__file__).parents[1]
            / "db"
            / "migrations"
            / "004_reference_contract.sql"
        ).read_text(encoding="utf-8")
        statements = "\n".join(
            line for line in migration.splitlines() if not line.lstrip().startswith("--")
        ).upper()

        self.assertFalse(re.search(r"\b(DROP|DELETE\s+FROM|TRUNCATE)\b", statements))
        self.assertEqual(statements.count("CREATE OR REPLACE VIEW"), 3)
        self.assertIn("CREATE OR REPLACE VIEW V_PUB_LOTS_V2", statements)
        self.assertIn("CREATE OR REPLACE VIEW V_PUB_LOTS_DISPONIBLES_V2", statements)
        self.assertIn("CREATE OR REPLACE VIEW V_PUB_ZONES_V2", statements)
        self.assertNotRegex(statements, r"CREATE OR REPLACE VIEW V_PUB_(LOTS|ZONES|LOTS_DISPONIBLES)\s")
        self.assertIn("PRIX_DERNIER_PUBLIE_DATE_SOURCE", statements)
        self.assertIn("PRIX_SITE_AFI_DATE_SOURCE", statements)
        self.assertIn("GROUPE_DEVELOPPEMENT_REGIONAL", statements)
        self.assertIn("CREATE USER IF NOT EXISTS 'DALILA_INGEST'@'%'", statements)
        self.assertIn("GRANT SELECT, INSERT, UPDATE ON AFI.DALILA_PASSAGES", statements)
        self.assertIn("GRANT SELECT, INSERT, DELETE ON AFI.DALILA_ECHANTILLON_EVAL", statements)


if __name__ == "__main__":
    unittest.main()
