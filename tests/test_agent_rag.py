import json
import unittest
from unittest.mock import patch

from dalila.harnais.agent import Agent, _cle_appel, _compact
from dalila.harnais.garde_fous import contient_preuves, verifier_ancrage
from dalila.traitement.passages import EntreePassages, chercher_passages


class FakeRecherche:
    def __init__(self):
        self.calls = []

    def chercher(self, question, **kwargs):
        self.calls.append((question, kwargs))
        return {"resultats": [{
            "id": "p000001",
            "type": "procedure",
            "titre": "Acquisition d'un lot",
            "source_url": "https://afi.nat.tn/acquisition.pdf",
            "date_source": "2026-11-27",
            "texte": "Procédure et documents à fournir.",
            "texte_ocr": True,
            "similarite": 0.84,
        }]}


class PassageAdapterTests(unittest.TestCase):
    def test_keeps_citation_metadata_and_search_arguments(self):
        recherche = FakeRecherche()
        with patch("dalila.traitement.passages._recherche", return_value=recherche):
            result = chercher_passages(EntreePassages(
                question="procédure acquisition", zone_id="930508", regime="littoral", nombre=3
            )).model_dump(mode="json")

        self.assertEqual(recherche.calls, [("procédure acquisition", {
            "k": 3, "zone_ids": ["930508"], "regime": "littoral"
        })])
        passage = result["passages"][0]
        self.assertEqual(passage["id"], "p000001")
        self.assertEqual(passage["titre"], "Acquisition d'un lot")
        self.assertEqual(passage["source"], "https://afi.nat.tn/acquisition.pdf")
        self.assertEqual(passage["url"], "https://afi.nat.tn/acquisition.pdf")
        self.assertEqual(passage["date_source"], "2026-11-27")
        self.assertEqual(passage["texte"], "Procédure et documents à fournir.")
        self.assertTrue(passage["texte_lu_par_ocr"])
        self.assertEqual(passage["lien"], passage["url"])
        self.assertEqual(result["sources"], [{
            "titre": "Acquisition d'un lot",
            "url": "https://afi.nat.tn/acquisition.pdf",
            "date_source": "2026-11-27",
        }])

    def test_keeps_non_url_source_label(self):
        recherche = FakeRecherche()
        recherche.chercher = lambda *args, **kwargs: {"resultats": [{
            "id": "kb0001", "type": "reponse_validee_afi", "titre": "Question AFI",
            "source_url": "Base de connaissances AFI", "date_source": None,
            "texte": "Réponse validée.", "texte_ocr": False,
        }]}
        with patch("dalila.traitement.passages._recherche", return_value=recherche):
            result = chercher_passages(EntreePassages(question="question")).model_dump(mode="json")

        passage = result["passages"][0]
        self.assertEqual(passage["source"], "Base de connaissances AFI")
        self.assertIsNone(passage["url"])
        self.assertIsNone(passage["lien"])


class ToolResultCompactionTests(unittest.TestCase):
    def test_removes_empty_fields_but_preserves_false_and_zero(self):
        result = json.loads(_compact({
            "none": None,
            "empty_list": [],
            "empty_dict": {},
            "zero": 0,
            "false": False,
            "nested": {"empty": None, "items": [None, 0, False]},
        }))
        self.assertEqual(result, {
            "zero": 0,
            "false": False,
            "nested": {"items": [None, 0, False]},
        })


class EvidenceGuardTests(unittest.TestCase):
    def setUp(self):
        self.results = [{
            "passages": [{
                "id": "p000001", "titre": "Acquisition AFI",
                "url": "https://afi.nat.tn/acquisition.pdf",
                "texte": "Les pièces sont précisées dans le document.",
            }],
            "sources": [{"titre": "Acquisition AFI", "url": "https://afi.nat.tn/acquisition.pdf"}],
        }]

    def test_accepts_citation_matching_tool_result(self):
        result = verifier_ancrage(
            "Voir [Acquisition AFI](https://afi.nat.tn/acquisition.pdf).",
            self.results,
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["sources_absentes"])

    def test_accepts_returned_pdf_identifier(self):
        result = verifier_ancrage("[[PDF:p000001:Acquisition AFI]]", self.results)
        self.assertTrue(result["ok"])
        wrong_title = verifier_ancrage("[[PDF:p000001:Faux titre]]", self.results)
        self.assertFalse(wrong_title["ok"])

    def test_rejects_unreturned_pdf_identifier(self):
        result = verifier_ancrage("[[PDF:p999999:Acquisition AFI]]", self.results)
        self.assertFalse(result["ok"])
        self.assertEqual(result["sources_inconnues"], ["p999999"])

    def test_validates_each_source_title(self):
        valid = verifier_ancrage("Sources: Acquisition AFI", self.results)
        unknown = verifier_ancrage("Sources: Faux titre", self.results)
        mixed = verifier_ancrage("Sources: Acquisition AFI; Faux titre", self.results)
        wrong_link_title = verifier_ancrage(
            "[Faux titre](https://afi.nat.tn/acquisition.pdf)", self.results
        )

        self.assertTrue(valid["ok"])
        self.assertFalse(unknown["ok"])
        self.assertIn("Faux titre", unknown["sources_inconnues"])
        self.assertFalse(mixed["ok"])
        self.assertIn("Faux titre", mixed["sources_inconnues"])
        self.assertFalse(wrong_link_title["ok"])

    def test_title_must_belong_to_the_cited_url(self):
        data = [{"sources": [
            {"titre": "Autre source", "url": "https://afi.nat.tn/autre.pdf"},
            {"url": "https://afi.nat.tn/acquisition.pdf"},
        ]}]
        result = verifier_ancrage(
            "[Autre source](https://afi.nat.tn/acquisition.pdf)", data
        )
        self.assertFalse(result["ok"])

    def test_validates_pdf_urls(self):
        valid = verifier_ancrage(
            "[[PDF:https://afi.nat.tn/acquisition.pdf:Acquisition AFI]]", self.results
        )
        unknown = verifier_ancrage(
            "[[PDF:https://example.invalid/acquisition.pdf:Acquisition AFI]]", self.results
        )
        self.assertTrue(valid["ok"])
        self.assertFalse(unknown["ok"])
        self.assertIn("https://example.invalid/acquisition.pdf", unknown["sources_inconnues"])

    def test_accepts_reported_price_and_rejects_absent_price(self):
        data = [{"prix_m2_dt": 120}]
        present = verifier_ancrage("Le prix est de 120 DT/m².", data)
        natural = verifier_ancrage("Le terrain coûte 120 DT/m².", data)
        without_unit_detail = verifier_ancrage("Le prix est de 120 DT.", data)
        absent = verifier_ancrage("Le prix est de 121 DT/m².", data)
        self.assertTrue(present["ok"])
        self.assertTrue(natural["ok"])
        self.assertTrue(without_unit_detail["ok"])
        self.assertEqual(present["nombres_inconnus"], [])
        self.assertFalse(absent["ok"])
        self.assertEqual(absent["nombres_inconnus"], [121])

    def test_price_per_m2_and_total_price_are_not_interchangeable(self):
        price_m2 = verifier_ancrage(
            "Le terrain coûte 120 DT/m².", [{"prix_m2_dt": 120}]
        )
        total_price = verifier_ancrage(
            "Le prix total du terrain est de 120 DT.", [{"prix_total_dt": 120}]
        )
        total_from_unit_price = verifier_ancrage(
            "Le prix total du terrain est de 120 DT.", [{"prix_m2_dt": 120}]
        )
        unit_price_from_total = verifier_ancrage(
            "Le terrain coûte 120 DT/m².", [{"prix_total_dt": 120}]
        )

        self.assertTrue(price_m2["ok"])
        self.assertTrue(total_price["ok"])
        self.assertFalse(total_from_unit_price["ok"])
        self.assertEqual(total_from_unit_price["nombres_inconnus"], [120])
        self.assertFalse(unit_price_from_total["ok"])
        self.assertEqual(unit_price_from_total["nombres_inconnus"], [120])

    def test_small_unjustified_price_surface_and_delay_are_rejected(self):
        cases = [
            "Le terrain coûte 5 DT/m².",
            "La superficie est de 4 m².",
            "Le délai est de 3 jours.",
        ]
        for response in cases:
            with self.subTest(response=response):
                result = verifier_ancrage(response, [])
                self.assertFalse(result["ok"])
                self.assertTrue(result["nombres_inconnus"])

    def test_ocr_text_nested_in_price_field_is_not_numeric_evidence(self):
        resultats = [{"prix": {"texte_ocr": "120"}}]
        result = verifier_ancrage("Le terrain coûte 120 DT/m².", resultats)
        self.assertFalse(result["ok"])
        self.assertEqual(result["nombres_inconnus"], [120])

    def test_grouped_surface_values_accept_ascii_and_existing_space_separators(self):
        data = [{"surface_m2": 5000}]
        for response in (
            "La superficie est de 5000 m².",
            "La superficie est de 5 000 m².",
            "La superficie est de 5\u00a0000 m².",
            "La superficie est de 5\u202f000 m².",
        ):
            with self.subTest(response=response):
                self.assertTrue(verifier_ancrage(response, data)["ok"])

    def test_fees_budget_and_total_price_do_not_justify_price_per_m2(self):
        response = "Le terrain coûte 120 DT/m²."
        for data in (
            {"frais": 120},
            {"budget_max_dt": 120},
            {"prix_total_dt": 120},
        ):
            with self.subTest(data=data):
                result = verifier_ancrage(response, [data])
                self.assertFalse(result["ok"])
                self.assertEqual(result["nombres_inconnus"], [120])

    def test_form_number_in_document_does_not_justify_price(self):
        url = "https://afi.nat.tn/formulaire.pdf"
        data = [{
            "passages": [{
                "id": "p-form",
                "titre": "Formulaire AFI",
                "url": url,
                "texte": "Le formulaire 120 doit être déposé au guichet.",
            }],
            "sources": [{"titre": "Formulaire AFI", "url": url}],
        }]
        result = verifier_ancrage(
            f"Le prix est de 120 DT/m². [Formulaire AFI]({url})", data
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["nombres_inconnus"], [120])

    def test_surface_value_does_not_justify_same_price(self):
        data = [{"surface_m2": 500}]
        price = verifier_ancrage("Le prix est de 500 DT.", data)
        surface = verifier_ancrage("La surface est de 500 m².", data)
        self.assertFalse(price["ok"])
        self.assertEqual(price["nombres_inconnus"], [500])
        self.assertTrue(surface["ok"])

    def test_lot_count_does_not_justify_same_delay(self):
        data = [{"nombre_total": 120}]
        delay = verifier_ancrage("Le délai est de 120 jours.", data)
        lot_count = verifier_ancrage("Il y a 120 lots.", data)
        self.assertFalse(delay["ok"])
        self.assertEqual(delay["nombres_inconnus"], [120])
        self.assertTrue(lot_count["ok"])

    def test_document_number_does_not_justify_a_structured_claim(self):
        data = [{"passages": [{
            "id": "p-ref",
            "titre": "Référence de formulaire",
            "url": "https://afi.nat.tn/reference.pdf",
            "texte": "Le formulaire porte le numéro 120.",
        }]}]
        result = verifier_ancrage("Le nombre de lots est de 120.", data)
        self.assertFalse(result["ok"])
        self.assertEqual(result["nombres_inconnus"], [120])

    def test_property_cue_in_another_sentence_does_not_classify_number(self):
        data = [{"delai_jours": 120}]
        result = verifier_ancrage(
            "Le formulaire porte le numéro 120. Le délai standard s'applique.", data
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["nombres_inconnus"], [120])

    def test_structured_delay_employment_distance_and_rate(self):
        cases = [
            ({"delai_jours": 30}, "Le délai est de 30 jours."),
            ({"emplois_directs": 80}, "Le projet créera 80 emplois."),
            ({"distance_km": 12}, "La distance est de 12 km."),
            ({"taux_subvention": 35}, "Le taux est de 35 %."),
        ]
        for data, response in cases:
            with self.subTest(response=response):
                result = verifier_ancrage(response, [data])
                self.assertTrue(result["ok"])

    def test_identifier_filename_and_url_numbers_do_not_justify_price(self):
        data = [{
            "passages": [{
                "id": "document120",
                "titre": "Plan 120.pdf",
                "url": "https://afi.nat.tn/plan120.pdf",
                "texte": "Plan de la zone.",
            }],
        }]
        result = verifier_ancrage(
            "Le prix est de 120 DT. [Plan 120.pdf](https://afi.nat.tn/plan120.pdf).",
            data,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["nombres_inconnus"], [120])

    def test_numbers_from_question_and_small_enumerations_remain_allowed(self):
        from_question = verifier_ancrage("Le prix est de 120 DT.", [], "Est-ce 120 DT ?")
        enumeration = verifier_ancrage("Options : 1) A, 2) B.", [])
        self.assertTrue(from_question["ok"])
        self.assertTrue(enumeration["ok"])

    def test_rejects_unreturned_citation_and_missing_citation(self):
        unknown = verifier_ancrage(
            "Source : [AFI](https://example.invalid/document).", self.results
        )
        missing = verifier_ancrage("La procédure est décrite dans le document.", self.results)
        self.assertFalse(unknown["ok"])
        self.assertTrue(unknown["sources_inconnues"])
        self.assertFalse(missing["ok"])
        self.assertTrue(missing["sources_absentes"])

    def test_rejects_unjustified_numbers(self):
        result = verifier_ancrage(
            "Le prix est de 120 DT/m². [Acquisition AFI](https://afi.nat.tn/acquisition.pdf).",
            self.results,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["nombres_inconnus"], [120])
        self.assertFalse(result["sources_inconnues"])

    def test_empty_and_failed_tools_are_not_evidence(self):
        self.assertFalse(contient_preuves([]))
        self.assertFalse(contient_preuves([{"erreur": "outil indisponible"}]))
        self.assertFalse(contient_preuves([{"passages": [], "sources": []}]))
        self.assertTrue(contient_preuves([{"nombre_total": 0, "lots": [], "sources": []}]))
        self.assertTrue(contient_preuves([{"lieux": [], "note": "Demander le gouvernorat."}]))

    def test_agent_abstains_without_tool_evidence(self):
        with patch("dalila.harnais.agent.discuter", return_value={
            "content": "Il existe 25 lots disponibles.", "tool_calls": [], "duree_s": 0.01
        }):
            result = Agent().repondre("Y a-t-il des lots ?")
        self.assertEqual(result["source"], "repli")
        self.assertTrue(result["ancrage"]["preuves_absentes"])
        self.assertIn("aucune donnée exploitable", result["erreur"])

    def test_agent_exposes_tool_results_for_the_http_source_adapter(self):
        url = "https://afi.nat.tn/charges.pdf"
        tool_result = {
            "passages": [{
                "id": "p000123",
                "type": "document",
                "titre": "Cahier des charges AFI",
                "source": "AFI",
                "url": url,
                "date_source": "2026-11-27",
                "texte": "Procédure.",
            }],
            "sources": [{"titre": "Cahier des charges AFI", "url": url}],
        }
        replies = iter([
            {
                "content": "",
                "tool_calls": [{
                    "nom": "chercher_passages",
                    "arguments": {"question": "procédure AFI", "nombre": 5},
                }],
                "duree_s": 0.01,
            },
            {
                "content": f"Voir [Cahier des charges AFI]({url}).",
                "tool_calls": [],
                "duree_s": 0.01,
            },
        ])
        with patch("dalila.harnais.agent.discuter", side_effect=lambda *args, **kwargs: next(replies)):
            with patch("dalila.harnais.agent.appeler", return_value=tool_result):
                result = Agent().repondre("Quelle est la procédure ?")

        self.assertEqual(result["resultats_outils"], [tool_result])
        self.assertTrue(result["ancrage"]["ok"])

    def test_passage_call_cache_ignores_spacing_and_case_only(self):
        self.assertEqual(
            _cle_appel("chercher_passages", {"question": "  Prix   à Sfax ", "nombre": 5}),
            _cle_appel("chercher_passages", {"question": "prix à sfax", "nombre": 5}),
        )
        self.assertNotEqual(
            _cle_appel("chercher_passages", {"question": "Prix à Sfax", "nombre": 5}),
            _cle_appel("chercher_passages", {"question": "Prix à Sfax", "nombre": 8}),
        )


if __name__ == "__main__":
    unittest.main()
