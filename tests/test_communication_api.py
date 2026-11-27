import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from dalila.communication.api import create_app
from dalila.communication.schemas import GeoJSONFeatureCollection, MapZonesResponse


class CommunicationApiTests(unittest.TestCase):
    def setUp(self):
        self.agent = Mock()
        self.map_service = Mock()
        self.app = create_app(agent_factory=lambda: self.agent, map_service=self.map_service)
        self.client = TestClient(self.app)

    def test_chat_delegates_to_agent_and_returns_only_verified_source_metadata(self):
        self.agent.repondre.return_value = {
            "reponse": "Le cahier des charges décrit la procédure.",
            "source": "dalila",
            "ancrage": {"ok": True},
            "erreur": None,
            "resultats_outils": [{
                "passages": [{
                    "id": "p000123",
                    "titre": "Cahier des charges AFI",
                    "source": "AFI",
                    "url": "https://afi.nat.tn/charges.pdf",
                    "date_source": "2026-11-27",
                    "texte": "Procédure.",
                }],
                "sources": [{
                    "titre": "Cahier des charges AFI",
                    "url": "https://afi.nat.tn/charges.pdf",
                }],
            }],
        }

        response = self.client.post("/api/v1/chat", json={
            "message": "Je cherche un lot à Sfax",
            "history": [{"role": "user", "content": "Bonjour"}],
            "lang": "fr",
            "context": {"page": "carte", "zone_id": "930508"},
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "answered")
        self.assertEqual(body["answer"], "Le cahier des charges décrit la procédure.")
        self.assertEqual(body["sources"], [{
            "source_id": "p000123",
            "title": "Cahier des charges AFI",
            "source": "AFI",
            "url": "https://afi.nat.tn/charges.pdf",
            "date": "2026-11-27",
        }])
        self.assertIsNone(body["map_data"])
        self.assertIsNone(body["error"])
        self.assertTrue(body["request_id"])
        self.assertEqual(response.headers["X-Request-ID"], body["request_id"])

        args, kwargs = self.agent.repondre.call_args
        self.assertEqual(args, ("Je cherche un lot à Sfax",))
        self.assertEqual(kwargs["historique"], [{"role": "user", "content": "Bonjour"}])
        self.assertEqual(kwargs["lang"], "fr")
        self.assertIn('"zone_id":"930508"', kwargs["contexte"])

    def test_map_zones_and_lot_geojson_are_served_from_the_map_service(self):
        self.map_service.zones.return_value = MapZonesResponse(
            zones=[{
                "zone_id": "930508",
                "name_fr": "Zone témoin",
                "governorate_fr": "Sfax",
                "latitude": 34.7,
                "longitude": 10.7,
            }]
        )
        self.map_service.lots.return_value = GeoJSONFeatureCollection(
            type="FeatureCollection",
            source_id="afi_sql_kml",
            notice="Availability is unknown.",
            features=[{
                "type": "Feature",
                "id": "42",
                "geometry": {"type": "Polygon", "coordinates": [[[10.0, 34.0], [10.1, 34.0],
                                                                   [10.1, 34.1], [10.0, 34.0]]]},
                "properties": {"zone_id": "930508", "lot_id": "42", "availability_state": "unknown"},
            }],
            truncated=True,
            next_cursor=42,
        )

        zones_response = self.client.get("/api/v1/map/zones")
        lots_response = self.client.get(
            "/api/v1/map/zones/930508/lots?limit=1&after_lot_id=10"
        )

        self.assertEqual(zones_response.status_code, 200)
        self.assertEqual(zones_response.json()["zones"][0]["source_id"], "afi_sql")
        self.assertEqual(lots_response.status_code, 200)
        lots = lots_response.json()
        self.assertEqual(lots["source_id"], "afi_sql_kml")
        self.assertEqual(lots["features"][0]["properties"]["availability_state"], "unknown")
        self.assertTrue(lots["truncated"])
        self.assertEqual(lots["next_cursor"], 42)
        self.map_service.lots.assert_called_once_with("930508", 1, 10)

    def test_unknown_map_zone_is_a_structured_not_found_error(self):
        self.map_service.lots.return_value = None

        response = self.client.get("/api/v1/map/zones/unknown/lots")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_agent_abstention_is_structured_without_invented_sources(self):
        self.agent.repondre.return_value = {
            "reponse": "Je ne peux pas vérifier cette information.",
            "source": "repli",
            "ancrage": {"ok": False, "preuves_absentes": True},
            "erreur": "aucune donnée exploitable retournée par les outils",
            "resultats_outils": [{"erreur": "outil indisponible"}],
        }

        response = self.client.post("/api/v1/chat", json={"message": "Quel est le prix ?"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "abstained")
        self.assertEqual(body["sources"], [])
        self.assertEqual(body["error"]["code"], "insufficient_evidence")

    def test_invalid_request_uses_stable_error_contract(self):
        response = self.client.post("/api/v1/chat", json={"message": " "})

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["error"]["code"], "invalid_request")
        self.assertTrue(body["request_id"])

    def test_unexpected_agent_error_does_not_leak_internal_details(self):
        self.agent.repondre.side_effect = RuntimeError("private connection detail")
        client = TestClient(self.app, raise_server_exceptions=False)

        with patch("dalila.communication.api.logger.exception") as log_error:
            response = client.post("/api/v1/chat", json={"message": "Question"})

        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["error"]["code"], "internal_error")
        self.assertNotIn("private connection detail", response.text)
        log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
