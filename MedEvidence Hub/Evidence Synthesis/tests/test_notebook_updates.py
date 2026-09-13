import unittest
from unittest.mock import patch

from agents.analysis_agent import ANALYSIS_PROMPT
from agents.query_evidence_agent import QUERY_EVIDENCE_PROMPT
from agents.code_agent import CODE_EXTRACTION_PROMPT, _normalize_code_result
from agents.openai_client import MODEL_NAME
from agents.outcome_agent import OUTCOME_COUNTRY_PROMPT
from agents.query_normalization_agent import PROMPT, normalize_query
from agents.slr_agent import SLR_PROMPT, slr_agent
from pubmed.metadata import _extract_authors_and_affiliations


class NotebookUpdateTests(unittest.TestCase):
    def test_uses_current_openai_gpt_model(self):
        self.assertEqual(MODEL_NAME, "gpt-5.6-sol")

    @patch("agents.query_normalization_agent.generate_json")
    def test_query_normalization_uses_shared_model_and_accepts_string_boolean(self, generate_json):
        generate_json.return_value = {
            "original_user_query": "non-small cell lung cancer survival",
            "normalized_query": "non-small cell lung cancer AND survival",
            "query_style": "keyword_query",
            "is_valid_medical_query": "true",
            "confidence": 0.94,
        }

        result = normalize_query("NSCLC survival")

        self.assertTrue(result["is_valid_medical_query"])
        self.assertEqual(result["query_style"], "keyword_query")
        self.assertNotIn("model_name", generate_json.call_args.kwargs)

    @patch("agents.query_normalization_agent.generate_json")
    def test_query_api_failure_is_not_reported_as_invalid_query(self, generate_json):
        generate_json.side_effect = RuntimeError("service unavailable")

        result = normalize_query("diabetes")

        self.assertIsNone(result["is_valid_medical_query"])
        self.assertEqual(result["normalization_method"], "Error")
        self.assertIn("service unavailable", result["error"])

    def test_query_prompt_contains_notebook_normalization_rules(self):
        self.assertIn("BRAND-TO-GENERIC NORMALIZATION", PROMPT)
        self.assertIn("CRITICAL INTENT PRESERVATION RULE", PROMPT)
        self.assertIn("PD-L1-positive", PROMPT)
        self.assertIn("requires_user_selection", PROMPT)

    @patch("agents.query_normalization_agent.generate_json")
    def test_query_normalization_exposes_entity_and_boolean_contract(self, generate_json):
        generate_json.return_value = {
            "original_user_query": "Diabetes Mellitus",
            "normalized_entities": ["Diabetes Mellitus"],
            "removed_words": [],
            "boolean_query": '"Diabetes Mellitus"',
            "normalized_query": '"Diabetes Mellitus"',
            "reason": "Corrected an unambiguous misspelling.",
            "query_style": "keyword_query",
            "is_valid_medical_query": True,
            "confidence": 0.97,
            "is_ambiguous": False,
            "requires_user_selection": False,
            "ambiguity_options": [],
        }

        result = normalize_query("Diabate mallu")

        self.assertEqual(result["normalized_entities"], ["Diabetes Mellitus"])
        self.assertEqual(result["boolean_query"], '"Diabetes Mellitus"')
        self.assertEqual(result["normalized_query"], result["boolean_query"])

    @patch("agents.query_normalization_agent.generate_json")
    def test_query_normalization_returns_ambiguity_options(self, generate_json):
        generate_json.return_value = {
            "original_user_query": "MI",
            "normalized_query": "",
            "query_style": "keyword_query",
            "is_valid_medical_query": True,
            "confidence": 0.8,
            "is_ambiguous": True,
            "requires_user_selection": True,
            "ambiguity_options": [
                {
                    "option_id": 1,
                    "full_form": "myocardial infarction",
                    "category": "cardiovascular disease",
                    "normalized_query": "myocardial infarction",
                },
                {
                    "option_id": 2,
                    "full_form": "mitral insufficiency",
                    "category": "heart valve disorder",
                    "normalized_query": "mitral insufficiency",
                },
            ],
        }

        result = normalize_query("MI")

        self.assertTrue(result["requires_user_selection"])
        self.assertEqual(len(result["ambiguity_options"]), 2)
        self.assertEqual(result["normalized_query"], "")

    def test_metadata_handles_collective_authors_and_unique_affiliations(self):
        article = {
            "AuthorList": [
                {
                    "CollectiveName": "Study Group",
                    "AffiliationInfo": [{"Affiliation": "Center A"}],
                },
                {
                    "ForeName": "Ada",
                    "LastName": "Lovelace",
                    "AffiliationInfo": [
                        {"Affiliation": "Center A"},
                        {"Affiliation": "Center B"},
                    ],
                },
            ]
        }

        authors, affiliations = _extract_authors_and_affiliations(article)

        self.assertEqual(authors, ["Study Group", "Ada Lovelace"])
        self.assertEqual(affiliations, ["Center A", "Center B"])

    def test_code_prompt_and_parser_preserve_notebook_evidence_contract(self):
        self.assertIn("Do NOT extract codes from other coding systems", CODE_EXTRACTION_PROMPT)
        self.assertIn('"Evidence": ""', CODE_EXTRACTION_PROMPT)
        result = _normalize_code_result(
            {
                "ICD_10_CM": [
                    {
                        "Code": "E10-E14",
                        "Name": "",
                        "Evidence": "Eligible patients had ICD-10-CM codes E10-E14.",
                    }
                ]
            }
        )
        self.assertEqual(
            result["ICD_10_CM"][0]["Evidence"],
            "Eligible patients had ICD-10-CM codes E10-E14.",
        )

    def test_analysis_and_outcome_prompts_include_expanded_notebook_rules(self):
        self.assertIn("Interrupted Time-Series Analysis", ANALYSIS_PROMPT)
        self.assertIn("numerical evidence is required", ANALYSIS_PROMPT)
        self.assertIn("analysed sample size or number of events", ANALYSIS_PROMPT)
        self.assertIn("Distinguish adjusted from unadjusted estimates", ANALYSIS_PROMPT)
        self.assertIn("self-contained, plain-language explanation", ANALYSIS_PROMPT)
        self.assertIn("Numerical Results", QUERY_EVIDENCE_PROMPT)
        self.assertIn("sample sizes and numbers of events", QUERY_EVIDENCE_PROMPT)
        self.assertIn("A statistically non-significant result", QUERY_EVIDENCE_PROMPT)
        self.assertIn("which part of the user's query", QUERY_EVIDENCE_PROMPT)
        self.assertIn("Generalized Additive Model", ANALYSIS_PROMPT)
        self.assertIn("Do not limit the extraction to statistical", ANALYSIS_PROMPT)
        self.assertIn("Predictive modelling and validation methods", ANALYSIS_PROMPT)
        self.assertIn("Qualitative, text, and mixed-methods analysis", ANALYSIS_PROMPT)
        self.assertIn("Mathematical, simulation, and algorithmic methods", ANALYSIS_PROMPT)
        self.assertIn("all analysis methods explicitly stated", ANALYSIS_PROMPT)
        self.assertIn('"Analyst result"', ANALYSIS_PROMPT)
        self.assertIn("Do not guess which method produced", ANALYSIS_PROMPT)
        self.assertIn("Republic of Korea -> South Korea", OUTCOME_COUNTRY_PROMPT)
        self.assertIn("Median overall survival was 18.4", OUTCOME_COUNTRY_PROMPT)

    @patch("agents.slr_agent.generate_json")
    def test_slr_agent_adds_requested_columns(self, generate_json):
        generate_json.return_value = {
            "Is_SLR": "true",
            "Study_Design": "Systematic Review and Meta-analysis",
        }

        result = slr_agent("Review title", {"Methods": "PRISMA"})

        self.assertEqual(
            result,
            {
                "Is_SLR": True,
                "Study_Design": "Systematic Review and Meta-analysis",
            },
        )
        self.assertIn("systematically identifies", SLR_PROMPT)


if __name__ == "__main__":
    unittest.main()
