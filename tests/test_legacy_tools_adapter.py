import unittest
from datetime import date
from unittest.mock import patch

from dalila.traitement.outils import Outils
from dalila.traitement.lots import EntreeLots, Lot, ResultatLots


class LegacyToolsAdapterTests(unittest.TestCase):
    @patch("dalila.traitement.outils.chercher_lots")
    def test_pipeline_adapter_uses_shared_governorate_codes_and_keeps_price_semantics(self, search):
        search.return_value = ResultatLots(
            nombre_total=1,
            lots=[Lot(
                lot_id=42,
                numero="12",
                zone_id="931011",
                zone="MENZEL CHEKIR",
                gouvernorat="Sfax",
                surface_m2=2398,
                prix_m2_dt=12.5,
                prix_total_dt=29975,
                prix_dernier_publie_source="dernier prix publié AFI",
                prix_dernier_publie_date_source=date(2026, 11, 25),
                prix_selon="dernier prix publié de la zone; total estimatif",
                a_confirmer=False,
            )],
            zones_prix_non_publie=[],
            filtres={},
            sources=[],
        )

        result = Outils().chercher_lots(gouvernorat="صفاقس", limite=1)

        entry = search.call_args.args[0]
        self.assertIsInstance(entry, EntreeLots)
        self.assertEqual(entry.gouvernorats, [20])
        self.assertEqual(result[0]["prix_m2_dt"], 12.5)
        self.assertEqual(result[0]["prix_terrain_estime_dt"], 29975)
        self.assertEqual(result[0]["prix_selon"], "dernier prix publié de la zone; total estimatif")
        self.assertEqual(result[0]["prix_dernier_publie_date_source"], date(2026, 11, 25))

    @patch("dalila.traitement.outils.chercher_lots")
    def test_legacy_adapter_uses_the_sourced_gafsa_governorate_code(self, search):
        search.return_value = ResultatLots(
            nombre_total=0,
            lots=[],
            zones_prix_non_publie=[],
            filtres={},
            sources=[],
        )

        Outils().chercher_lots(gouvernorat="Gafsa")

        entry = search.call_args.args[0]
        self.assertIsInstance(entry, EntreeLots)
        self.assertEqual(entry.gouvernorats, [8])

    @patch("dalila.traitement.outils.lister_zones")
    def test_pipeline_does_not_infer_a_single_regime_from_mixed_zones(self, list_zones):
        class Zone:
            def __init__(self, value):
                self.developpement_regional = value

        class Result:
            zones = [Zone(True), Zone(False)]

        list_zones.return_value = Result()

        self.assertIsNone(Outils().regime_gouvernorat("Sfax"))


if __name__ == "__main__":
    unittest.main()
