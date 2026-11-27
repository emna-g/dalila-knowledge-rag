import unittest
from pathlib import Path
from unittest.mock import patch

from dalila.traitement.carte import lister_zones_carte, lots_carte


class MapDataTests(unittest.TestCase):
    def test_public_lot_views_exclude_lots_without_a_matching_visible_zone(self):
        migrations = Path(__file__).parents[1] / "db" / "migrations" / "002_views.sql"
        sql = migrations.read_text(encoding="utf-8")
        lots_view = sql.split("CREATE OR REPLACE VIEW v_pub_lots AS", 1)[1].split(
            "CREATE OR REPLACE VIEW v_pub_lots_disponibles", 1
        )[0]
        polygon_view = sql.split("CREATE OR REPLACE VIEW v_pub_lot_polygones AS", 1)[1].split(
            "CREATE OR REPLACE VIEW v_dalila_corrections_etat", 1
        )[0]

        self.assertIn("JOIN v_dalila_zones z ON z.zone_id = d.zone_id", lots_view)
        self.assertIn("WHERE z.visible = 1", lots_view)
        self.assertIn("FROM v_pub_lots v JOIN v_dalila_contours c", polygon_view)

    @patch("dalila.traitement.carte.q")
    def test_zones_use_only_public_afi_view_coordinates(self, query):
        query.return_value = [{
            "zone_id": "930508",
            "nom_fr": "Zone AFI",
            "nom_ar": None,
            "gouvernorat_fr": "Sfax",
            "gouvernorat_code": 20,
            "lat": "34.7",
            "lng": "10.7",
        }, {
            "zone_id": "930509",
            "nom_fr": None,
            "nom_ar": None,
            "gouvernorat_fr": "Sfax",
            "gouvernorat_code": 20,
            "lat": "999",
            "lng": None,
        }, {
            "zone_id": "931005",
            "nom_fr": "EL HANCH",
            "nom_ar": None,
            "gouvernorat_code": 8,
            "zone_developpement_regional": 1,
            "groupe_developpement_regional": None,
            "lat": "35.0",
            "lng": "9.0",
        }]

        result = lister_zones_carte()

        self.assertEqual(result["source_id"], "afi_sql")
        zones = {zone["zone_id"]: zone for zone in result["zones"]}
        self.assertEqual(zones["930508"]["governorate_fr"], "Sfax")
        self.assertEqual(zones["930508"]["latitude"], 34.7)
        self.assertEqual(zones["930508"]["longitude"], 10.7)
        self.assertIsNone(zones["930509"]["latitude"])
        self.assertIsNone(zones["930509"]["longitude"])
        self.assertEqual(zones["931005"]["governorate_fr"], "Gafsa")
        self.assertEqual(zones["931005"]["development_regional_group"], 1)
        self.assertTrue(zones["931005"]["development_regional"])
        query.assert_called_once()
        self.assertIn("FROM v_pub_zones", query.call_args.args[0])

    @patch("dalila.traitement.carte.q")
    def test_lot_contours_convert_only_valid_closed_kml_rings_and_paginate(self, query):
        query.side_effect = [
            [{"zone_id": "930508"}],
            [{
                "lot_id": 41,
                "zone_id": "930508",
                "lot_num": "A1",
                "surface_m2": 1200,
                "coordonnees": "10,34,0 10.1,34,0 10.1,34.1,0 10,34,0",
            }, {
                "lot_id": 42,
                "zone_id": "930508",
                "lot_num": "A2",
                "surface_m2": 800,
                "coordonnees": None,
            }, {
                "lot_id": 43,
                "zone_id": "930508",
                "lot_num": "A3",
                "surface_m2": 900,
                "coordonnees": "10,34,0 invalid 10.1,34.1,0 10,34,0",
            }, {
                "lot_id": 44,
                "zone_id": "930508",
                "lot_num": "A4",
                "surface_m2": 900,
                "coordonnees": "10,34,0 10.1,34,0 10.1,34.1,0 10,34,0",
            }],
        ]

        result = lots_carte("930508", limit=3, after_lot_id=20)

        self.assertEqual(result["source_id"], "afi_sql_kml")
        self.assertEqual(len(result["features"]), 1)
        feature = result["features"][0]
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertEqual(feature["geometry"]["coordinates"][0][0], (10.0, 34.0))
        self.assertEqual(feature["properties"]["availability_state"], "unknown")
        self.assertTrue(feature["properties"]["status_requires_afi_confirmation"])
        self.assertEqual(result["rejected_geometry_count"], 2)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["next_cursor"], 43)
        self.assertIn("LIMIT %s", query.call_args_list[1].args[0])

    @patch("dalila.traitement.carte.q")
    def test_lot_without_matching_public_zone_is_not_queried(self, query):
        query.return_value = []

        result = lots_carte("orphan-zone")

        self.assertIsNone(result)
        self.assertEqual(query.call_count, 1)
        self.assertIn("FROM v_pub_zones", query.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
