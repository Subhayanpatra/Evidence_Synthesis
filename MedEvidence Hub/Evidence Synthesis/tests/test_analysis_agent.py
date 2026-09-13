import unittest
from unittest.mock import patch

from agents.analysis_agent import _normalize_analyst_results, analysis_agent


class AnalysisAgentTests(unittest.TestCase):
    def test_normalizes_method_result_objects_and_strings(self):
        result = _normalize_analyst_results(
            {
                "Analyst result": [
                    {
                        "Method": "Cox Proportional Hazards Regression",
                        "Result": "Treatment reduced mortality (HR 0.72).",
                    },
                    "Random Forest: Accuracy was 89%.",
                    {"Method": "Kaplan-Meier Analysis", "Result": ""},
                    "invalid",
                ]
            }
        )

        self.assertEqual(
            result,
            [
                "Cox Proportional Hazards Regression: Treatment reduced mortality (HR 0.72).",
                "Random Forest: Accuracy was 89%.",
            ],
        )

    @patch("agents.analysis_agent.generate_json")
    def test_returns_analysis_and_analyst_result_columns(self, generate_json):
        generate_json.return_value = {
            "Analysis": ["Kaplan-Meier Analysis", "Cox Proportional Hazards Regression"],
            "Analyst result": [
                {
                    "Method": "Kaplan-Meier Analysis",
                    "Result": "Median overall survival was 18.4 months.",
                },
                {
                    "Method": "Cox Proportional Hazards Regression",
                    "Result": "Treatment reduced mortality (HR 0.72).",
                },
            ],
        }

        result = analysis_agent("Methods and results")

        self.assertEqual(
            result,
            {
                "Analysis": "Kaplan-Meier Analysis; Cox Proportional Hazards Regression",
                "Analyst result": (
                    "Kaplan-Meier Analysis: Median overall survival was 18.4 months.; "
                    "Cox Proportional Hazards Regression: Treatment reduced mortality (HR 0.72)."
                ),
            },
        )

    def test_empty_content_returns_both_columns(self):
        self.assertEqual(
            analysis_agent(""),
            {"Analysis": "", "Analyst result": ""},
        )


if __name__ == "__main__":
    unittest.main()
