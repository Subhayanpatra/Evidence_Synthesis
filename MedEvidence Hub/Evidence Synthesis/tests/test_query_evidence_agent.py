import unittest
from unittest.mock import patch

from agents.query_evidence_agent import _normalize_evidence, query_evidence_agent


class QueryEvidenceAgentTests(unittest.TestCase):
    def test_normalizes_structured_evidence(self):
        result = _normalize_evidence(
            {
                "Query Supporting Evidence": [
                    {
                        "Evidence": "Median survival was 22.0 months versus 10.7 months.",
                        "Explanation": "The treatment group had longer reported median survival.",
                        "Numerical Results": "22.0 months versus 10.7 months",
                        "Source": "Results",
                        "Relationship": "supports",
                    },
                    {
                        "Evidence": "No significant difference was observed.",
                        "Source": "Table 2",
                        "Relationship": "unknown",
                    },
                    {"Evidence": "", "Source": "Results", "Relationship": "Supports"},
                ]
            }
        )

        self.assertEqual(
            result,
            [
                (
                    "[Supports | Results] Median survival was 22.0 months versus 10.7 months. "
                    "| Explanation: The treatment group had longer reported median survival. "
                    "| Numerical results: 22.0 months versus 10.7 months"
                ),
                "[Inconclusive | Table 2] No significant difference was observed.",
            ],
        )

    @patch("agents.query_evidence_agent.generate_json")
    def test_returns_query_supporting_evidence_column(self, generate_json):
        generate_json.return_value = {
            "Query Supporting Evidence": [
                {
                    "Evidence": "The intervention reduced 30-day readmissions.",
                    "Source": "Conclusion",
                    "Relationship": "Supports",
                }
            ]
        }

        result = query_evidence_agent(
            "Does the intervention reduce readmissions?",
            "Example paper",
            "The intervention reduced 30-day readmissions.",
        )

        self.assertEqual(
            result,
            {
                "Query Supporting Evidence": (
                    "[Supports | Conclusion] "
                    "The intervention reduced 30-day readmissions."
                )
            },
        )

    def test_missing_query_returns_empty_evidence(self):
        self.assertEqual(
            query_evidence_agent("", "Example paper", "Article results"),
            {"Query Supporting Evidence": ""},
        )


if __name__ == "__main__":
    unittest.main()
