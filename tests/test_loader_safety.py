import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dalila import config
from dalila.connaissances import charger
from dalila.connaissances.migrer import substituer_secrets
from dalila.connaissances import vectoriser


class LoaderSafetyTests(unittest.TestCase):
    def test_default_loader_arguments_are_non_destructive_and_replacement_requires_both_flags(self):
        self.assertFalse(charger.analyser_arguments([]).replace_dalila_data)
        self.assertFalse(charger.analyser_arguments([]).surfaces)
        self.assertTrue(charger.analyser_arguments(["--surfaces"]).surfaces)
        with self.assertRaises(SystemExit):
            charger.analyser_arguments(["--replace-dalila-data"])
        with self.assertRaises(SystemExit):
            charger.analyser_arguments(["--confirm-replace-dalila-data"])
        self.assertTrue(charger.analyser_arguments([
            "--replace-dalila-data",
            "--confirm-replace-dalila-data",
        ]).replace_dalila_data)
        self.assertEqual(charger.role_connexion(charger.analyser_arguments([])), "ingest")
        self.assertEqual(charger.role_connexion(charger.analyser_arguments([
            "--replace-dalila-data",
            "--confirm-replace-dalila-data",
        ])), "root")

    def test_loader_default_path_upserts_and_does_not_delete_when_sources_are_empty(self):
        class CaptureCursor:
            def __init__(self):
                self.statements = []
                self.rows = []

            def execute(self, sql, params=None):
                self.statements.append(sql)
                self.rows = [{"Field": "embedding_e5"}] if sql.startswith("SHOW COLUMNS") else []

            def executemany(self, sql, rows):
                self.statements.append(sql)
                self.rows = []

            def fetchall(self):
                return self.rows

        with tempfile.TemporaryDirectory() as temporary:
            corpus = Path(temporary) / "corpus"
            corpus.mkdir()
            (corpus / "passages.jsonl").write_text("", encoding="utf-8")
            cursor = CaptureCursor()
            lire_csv = charger.lire_csv

            def lire_csv_sans_corrections(chemin):
                if Path(chemin).name in ("dalila_corrections.csv", "lots_a_confirmer.csv"):
                    return []
                return lire_csv(chemin)

            appels_synchronisation = []
            synchroniser_reel = charger.synchroniser_references

            def synchroniser(cur, inclure_surfaces=False):
                appels_synchronisation.append(inclure_surfaces)
                return synchroniser_reel(cur, inclure_surfaces)

            with (
                patch.object(charger, "DONNEES", Path(temporary)),
                patch.object(charger, "lire_csv", side_effect=lire_csv_sans_corrections),
                patch.object(charger, "synchroniser_references", side_effect=synchroniser),
            ):
                charger._charger(cursor)

        commandes = "\n".join(cursor.statements).upper()
        self.assertFalse(any(token in commandes for token in ("DELETE FROM", "TRUNCATE", "DROP TABLE")))
        self.assertGreaterEqual(commandes.count("ON DUPLICATE KEY UPDATE"), 8)
        self.assertIn("WHERE NOT EXISTS", commandes)
        self.assertEqual(appels_synchronisation, [False])
        self.assertFalse(any("LOTS_KML" in sql for sql in cursor.statements))

    def test_surface_recalculation_skips_missing_or_invalid_kml_and_warns(self):
        class CaptureCursor:
            def execute(self, sql):
                self.sql = sql

            def fetchall(self):
                return [
                    {"z": "zone-1", "k": None},
                    {"z": "zone-2", "k": "nan,34 10,34 10,34.1"},
                    {"z": "zone-3", "k": "10,34 10.1,34 10.1,34.1 10,34"},
                ]

        with self.assertWarnsRegex(RuntimeWarning, "2 contour"):
            result = charger.surfaces_contours(CaptureCursor())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "zone-3")
        self.assertGreater(result[0][1], 0)

    def test_reference_clear_requires_explicit_confirmation(self):
        class CaptureCursor:
            def __init__(self):
                self.statements = []

            def execute(self, sql):
                self.statements.append(sql)

        cursor = CaptureCursor()
        with self.assertRaisesRegex(ValueError, "confirmation explicite"):
            charger.effacer_donnees_dalila(cursor)
        self.assertEqual(cursor.statements, [])

        charger.effacer_donnees_dalila(cursor, confirmer=True)
        self.assertEqual(len(cursor.statements), len(charger._TABLES_DALILA))
        self.assertTrue(all(statement.startswith("DELETE FROM dalila_") for statement in cursor.statements))

    def test_source_rows_aggregate_repeated_urls_and_reject_prefix_key_collisions(self):
        url = "https://afi.example.tn/source"
        self.assertEqual(
            charger._sources_passages([
                {"source_url": url, "date_source": "2026-11-27"},
                {"source_url": url, "date_source": None},
            ]),
            [(url, "afi.example.tn", "2026-11-27", 2)],
        )
        with self.assertRaisesRegex(ValueError, "clé unique"):
            charger._sources_passages([
                {"source_url": url},
                {"source_url": url.upper()},
            ])
        prefix = "https://afi.example.tn/" + ("x" * 480)
        with self.assertRaisesRegex(ValueError, "clé unique"):
            charger._sources_passages([
                {"source_url": prefix + "a"},
                {"source_url": prefix + "b"},
            ])
        with self.assertRaisesRegex(ValueError, "Dates de source contradictoires"):
            charger._sources_passages([
                {"source_url": url, "date_source": "2026-11-26"},
                {"source_url": url, "date_source": "2026-11-27"},
            ])

    def test_vectorizer_requires_an_explicit_sample_or_full_index_scope(self):
        with patch("sys.argv", ["vectoriser"]):
            with patch.object(vectoriser, "db") as connect:
                with self.assertRaises(SystemExit):
                    vectoriser.main()
                connect.assert_not_called()

        self.assertTrue(vectoriser.analyser_arguments(["--modele", "e5", "--echantillon"]).echantillon)
        self.assertTrue(vectoriser.analyser_arguments(["--modele", "bge", "--index-complet"]).index_complet)
        with self.assertRaises(SystemExit):
            vectoriser.analyser_arguments(["--echantillon", "--index-complet"])

    def test_ingest_connection_uses_a_dedicated_non_root_account(self):
        with patch.dict(os.environ, {"DB_INGEST_PASSWORD": "unit-test-only"}, clear=False):
            with patch("pymysql.connect") as connect:
                config.db("ingest")

        self.assertEqual(connect.call_args.kwargs["user"], "dalila_ingest")
        self.assertEqual(connect.call_args.kwargs["password"], "unit-test-only")

    def test_migration_password_substitution_escapes_sql_literals_without_echoing_them(self):
        statement = "CREATE USER 'dalila_ingest' IDENTIFIED BY ':DB_INGEST_PASSWORD';"
        result = substituer_secrets(statement, {"DB_INGEST_PASSWORD": "x'y\\z"})

        self.assertEqual(result, "CREATE USER 'dalila_ingest' IDENTIFIED BY 'x''y\\\\z';")
        with self.assertRaisesRegex(RuntimeError, "DB_INGEST_PASSWORD"):
            substituer_secrets(statement, {})


if __name__ == "__main__":
    unittest.main()
