import unittest
from unittest.mock import patch

from agents.sap_agent import sap_agent


class SapAgentTests(unittest.TestCase):
    @patch("agents.sap_agent.generate_json")
    def test_combines_all_relevant_papers_into_one_sap(self, generate_json):
        generate_json.return_value = {
            "Title": "Diabetes SAP",
            "Evidence summary": "Two papers informed the plan.",
            "Comparative analyses": ["Use an appropriate adjusted model (PMC1; PMC2)."],
            "Supporting papers": ["PMC1", "PMC2"],
        }
        papers = [
            {"PMCID": "PMC1", "Relevant": True, "Analysis": "Logistic Regression"},
            {"PMCID": "PMC2", "Relevant": True, "Analysis": "Cox Regression"},
        ]

        result = sap_agent("diabetes", papers, requested=2, returned=2)

        self.assertEqual(result["Contributing extracted papers"], 2)
        self.assertEqual(result["Requested papers"], 2)
        self.assertEqual(result["Supporting papers"], ["PMC1", "PMC2"])
        self.assertEqual(generate_json.call_count, 1)

    def test_returns_clear_error_without_contributing_papers(self):
        result = sap_agent("diabetes", [], requested=5, returned=0)

        self.assertEqual(result["Contributing extracted papers"], 0)
        self.assertIn("No successfully extracted", result["SAP_Agent_Error"])


if __name__ == "__main__":
    unittest.main()
