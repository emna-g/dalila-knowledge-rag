import unittest
from decimal import Decimal
from datetime import date
from unittest.mock import patch

from dalila.traitement import lieux, lots
from dalila.traitement.lieux import EntreeLieu, resoudre_lieu
from dalila.traitement.lots import EntreeLots, chercher_lots
from dalila.traitement.references import alias_zones_par_id, gouvernorats_par_code
from dalila.traitement.zones import (
    EntreeFiche,
    EntreeListeZones,
    EntreeProximite,
    fiche_zone,
    lister_zones,
    zones_proches,
)


class GeographicToolsCompatibilityTests(unittest.TestCase):
    def setUp(self):
        lieux._candidats.cache_clear()
        gouvernorats_par_code.cache_clear()
        alias_zones_par_id.cache_clear()

    def tearDown(self):
        lieux._candidats.cache_clear()
        gouvernorats_par_code.cache_clear()
        alias_zones_par_id.cache_clear()

    def test_reference_files_resolve_french_arabic_governorate_and_region_names(self):
        references = gouvernorats_par_code()
        self.assertEqual(references[20], {"nom_fr": "Sfax", "nom_ar": "صفاقس"})
        self.assertIn("ENFIDHA 2", alias_zones_par_id()["930607"])

        zone = {
            "zone_id": "931011",
            "nom_fr": "MENZEL CHEKIR",
            "nom_ar": "منزل شاكر",
            "gouvernorat_code": 20,
        }
        with patch("dalila.traitement.lieux.q", return_value=[zone]):
            sfax = resoudre_lieu(EntreeLieu(texte="صفاقس"))
            grand_tunis = resoudre_lieu(EntreeLieu(texte="Grand Tunis"))

        self.assertEqual((sfax.lieux[0].type, sfax.lieux[0].id, sfax.lieux[0].nom),
                         ("gouvernorat", "20", "Sfax"))
        self.assertEqual(grand_tunis.lieux[0].gouvernorats, [1, 2, 3, 4])

    def test_zone_alias_is_loaded_from_canonical_csv_without_db_alias_rows(self):
        zone = {
            "zone_id": "930607",
            "nom_fr": "ENNFIDHA II",
            "nom_ar": None,
            "gouvernorat_code": 21,
        }
        with patch("dalila.traitement.lieux.q", return_value=[zone]):
            result = resoudre_lieu(EntreeLieu(texte="ENFIDHA 2"))

        self.assertEqual([(lieu.type, lieu.id) for lieu in result.lieux], [("zone", "930607")])

    def _chercher_lots(self, prix_actuel=None, dernier_prix=None, a_confirmer=0, budget=None,
                       prix_source=None, prix_date=None):
        requetes = []
        prix_absent = prix_actuel is None and dernier_prix is None

        def q(sql, *params):
            requetes.append((sql, params))
            if sql.startswith("SELECT zone_id, gouvernorat_code, zone_developpement_regional"):
                return [{"zone_id": "931011", "gouvernorat_code": 20, "dr": 1, "g": None}]
            if "SELECT l.zone_id, MAX(" in sql:
                if budget is not None and prix_absent:
                    return []
                return [{"zone_id": "931011", "sans_prix": int(prix_absent), "n": 1}]
            if "SELECT l.lot_id" in sql:
                if budget is not None and prix_absent:
                    return []
                return [{
                    "lot_id": 42,
                    "lot_num": "12",
                    "zone_id": "931011",
                    "zone_fr": "MENZEL CHEKIR",
                    "surface_m2": 2398,
                    "prix_m2_dt": prix_actuel,
                    "prix_m2_dernier_publie_dt": dernier_prix,
                    "prix_dernier_publie_source": prix_source,
                    "prix_dernier_publie_date_source": prix_date,
                    "a_confirmer": a_confirmer,
                }]
            if sql == "SELECT zone_id, gouvernorat_code FROM v_pub_zones_v2":
                return [{"zone_id": "931011", "gouvernorat_code": 20}]
            raise AssertionError(f"Unexpected query: {sql}")

        with patch("dalila.traitement.lots.q", side_effect=q):
            result = chercher_lots(EntreeLots(gouvernorats=[20], budget_max_dt=budget))
        return result, requetes

    def test_versioned_lot_view_uses_zone_price_and_returns_an_estimate(self):
        result, requetes = self._chercher_lots(prix_actuel=Decimal("38"))

        lot = result.lots[0]
        self.assertEqual(result.nombre_total, 1)
        self.assertEqual(lot.gouvernorat, "Sfax")
        self.assertEqual(lot.prix_m2_dt, 38)
        self.assertEqual(lot.prix_total_dt, 91124)
        self.assertIn("tarif actuel au m² de la zone", lot.prix_selon)
        self.assertTrue(all("v_pub_lots_disponibles_v2" in sql for sql, _ in requetes
                            if sql.startswith("SELECT l.")))
        self.assertTrue(any("COALESCE(l.prix_m2_dt, l.prix_m2_dernier_publie_dt)" in sql
                            for sql, _ in requetes))

    def test_missing_zone_price_stays_unknown_and_is_reported(self):
        result, _ = self._chercher_lots(a_confirmer=1)

        lot = result.lots[0]
        self.assertIsNone(lot.prix_m2_dt)
        self.assertIsNone(lot.prix_total_dt)
        self.assertIsNone(lot.prix_selon)
        self.assertEqual(result.zones_prix_non_publie, ["931011"])
        self.assertTrue(lot.a_confirmer)

    def test_missing_zone_price_does_not_pass_budget_filter(self):
        result, requetes = self._chercher_lots(budget=100000)

        self.assertEqual(result.nombre_total, 0)
        self.assertEqual(result.lots, [])
        self.assertTrue(any("l.surface_m2 * COALESCE(l.prix_m2_dt, l.prix_m2_dernier_publie_dt) <= %s" in sql
                            for sql, _ in requetes))

    def test_last_published_zone_price_is_sourced_and_stays_distinct_from_current_price(self):
        result, _ = self._chercher_lots(
            dernier_prix=Decimal("50"),
            prix_source="prix AFI publié",
            prix_date=date(2026, 11, 25),
        )

        lot = result.lots[0]
        self.assertEqual(lot.prix_m2_dt, 50)
        self.assertEqual(lot.prix_total_dt, 119900)
        self.assertEqual(lot.prix_dernier_publie_source, "prix AFI publié")
        self.assertEqual(lot.prix_dernier_publie_date_source, date(2026, 11, 25))
        self.assertTrue(any(source.titre == "prix AFI publié" for source in result.sources))

    def test_zone_last_published_price_is_included_in_sourced_result(self):
        zone = {
            "zone_id": "88888",
            "nom_fr": "Zone sans tarif actuel",
            "nom_ar": None,
            "gouvernorat_code": 7,
            "zone_developpement_regional": 0,
            "groupe_developpement_regional": None,
            "prix_m2_dt": None,
            "prix_m2_dernier_publie_dt": None,
            "lots_disponibles": 0,
            "lots_disponibles_a_confirmer": 0,
            "lots_mis_aux_encheres": 0,
            "surface_totale_m2": None,
            "surface_amenagee_m2": None,
        }
        source = {
            "prix_m2_dt": Decimal("50"),
            "source": "dernier prix publié AFI, relevée le 2026-11-25",
            "date_source": date(2026, 11, 25),
        }
        with patch("dalila.traitement.zones.q", side_effect=[[zone], [], [], [], [], []]), patch(
            "dalila.traitement.zones.derniers_prix_publies_par_zone",
            return_value={"88888": source},
        ):
            fiche = fiche_zone(EntreeFiche(zone_id="88888"))

        self.assertEqual(fiche.prix_m2_dernier_publie_dt, 50)
        self.assertTrue(any(
            reference.titre == source["source"]
            and reference.date_source == date(2026, 11, 25)
            for reference in fiche.sources
        ))

    def test_zone_view_price_without_provenance_stays_unknown(self):
        zone = {
            "zone_id": "88888",
            "nom_fr": "Zone sans tarif actuel",
            "nom_ar": None,
            "gouvernorat_code": 7,
            "zone_developpement_regional": 0,
            "groupe_developpement_regional": None,
            "prix_m2_dt": None,
            "prix_m2_dernier_publie_dt": 50,
            "prix_dernier_publie_source": None,
            "lots_disponibles": 0,
            "lots_disponibles_a_confirmer": 0,
            "lots_mis_aux_encheres": 0,
            "surface_totale_m2": None,
            "surface_amenagee_m2": None,
        }
        with patch("dalila.traitement.zones.q", side_effect=[[zone], [], [], [], [], []]), patch(
            "dalila.traitement.zones.derniers_prix_publies_par_zone", return_value={}
        ):
            fiche = fiche_zone(EntreeFiche(zone_id="88888"))

        self.assertIsNone(fiche.prix_m2_dernier_publie_dt)
        self.assertIsNone(fiche.prix_dernier_publie_source)

    def test_zone_rejects_a_database_price_source_that_disagrees_with_the_canonical_reference(self):
        zone = {
            "zone_id": "88888",
            "nom_fr": "Zone sans tarif actuel",
            "nom_ar": None,
            "gouvernorat_code": 7,
            "zone_developpement_regional": 0,
            "groupe_developpement_regional": None,
            "prix_m2_dt": None,
            "prix_m2_dernier_publie_dt": 50,
            "prix_dernier_publie_source": "source différente",
            "prix_dernier_publie_date_source": date(2026, 11, 25),
            "lots_disponibles": 0,
            "lots_disponibles_a_confirmer": 0,
            "lots_mis_aux_encheres": 0,
            "surface_totale_m2": None,
            "surface_amenagee_m2": None,
        }
        source = {
            "prix_m2_dt": Decimal("50"),
            "source": "dernier prix publié AFI, relevée le 2026-11-25",
            "date_source": date(2026, 11, 25),
        }
        with patch("dalila.traitement.zones.q", side_effect=[[zone], [], [], [], [], []]), patch(
            "dalila.traitement.zones.derniers_prix_publies_par_zone",
            return_value={"88888": source},
        ):
            with self.assertRaisesRegex(ValueError, "Divergence de source"):
                fiche_zone(EntreeFiche(zone_id="88888"))

    def test_zone_tools_map_governorate_and_keep_absent_view_fields_unknown(self):
        zone = {
            "zone_id": "931011",
            "nom_fr": "MENZEL CHEKIR",
            "nom_ar": None,
            "gouvernorat_fr": None,
            "gouvernorat_code": 20,
            "zone_developpement_regional": 1,
            "groupe_developpement_regional": None,
            "prix_m2_dt": 38,
            "surface_totale_m2": None,
            "surface_amenagee_m2": None,
            "lots_disponibles": 2,
            "lots_disponibles_a_confirmer": 0,
            "lots_mis_aux_encheres": 0,
        }
        with patch("dalila.traitement.zones.q", side_effect=[[zone], [], [], [], [], []]) as query:
            fiche = fiche_zone(EntreeFiche(zone_id="931011"))
        self.assertEqual(fiche.gouvernorat, "Sfax")
        self.assertIsNone(fiche.prix_m2_dernier_publie_dt)
        self.assertIsNone(fiche.prix_en_conflit)
        self.assertIn("FROM v_pub_zones_v2", query.call_args_list[0].args[0])

        with patch("dalila.traitement.zones.q", return_value=[zone]):
            liste = lister_zones(EntreeListeZones(gouvernorats=[20]))
        self.assertEqual(liste.zones[0].gouvernorat, "Sfax")

        nearby = {**zone, "infra": "Port de Sfax", "km": Decimal("12.5")}
        with patch("dalila.traitement.zones.q", return_value=[nearby]):
            proches = zones_proches(EntreeProximite(type="port"))
        self.assertEqual(proches.zones[0].gouvernorat, "Sfax")

    def test_unknown_governorate_code_does_not_get_an_invented_label(self):
        zone = {
            "zone_id": "zone-unknown",
            "nom_fr": "Zone sans référentiel",
            "nom_ar": None,
            "gouvernorat_code": 999,
            "zone_developpement_regional": 0,
            "groupe_developpement_regional": None,
            "prix_m2_dt": None,
            "surface_totale_m2": None,
            "surface_amenagee_m2": None,
            "lots_disponibles": 0,
            "lots_disponibles_a_confirmer": 0,
            "lots_mis_aux_encheres": 0,
        }
        with patch("dalila.traitement.zones.q", return_value=[zone]):
            result = lister_zones(EntreeListeZones(gouvernorats=[999], seulement_avec_lots_disponibles=False))
        self.assertIsNone(result.zones[0].gouvernorat)


if __name__ == "__main__":
    unittest.main()
