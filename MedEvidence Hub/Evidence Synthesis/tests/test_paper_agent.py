import unittest
from unittest.mock import patch

from agents.paper_agent import process_paper


class PaperAgentPipelineTests(unittest.TestCase):
    @patch("agents.paper_agent.relevance_agent")
    @patch("agents.paper_agent.extract_pmc_supplementary_material")
    @patch("agents.paper_agent.parse_pmc_xml")
    @patch("agents.paper_agent.get_pmc_xml")
    def test_irrelevant_paper_skips_supplementary_and_detailed_agents(
        self,
        get_pmc_xml,
        parse_pmc_xml,
        extract_supplementary,
        relevance_agent,
    ):
        get_pmc_xml.return_value = "<article/>"
        parse_pmc_xml.return_value = {
            "Full_Text": "Complete but unrelated article text " * 20,
            "Sections": {"Methods": "Unrelated methods"},
            "Figures": [],
            "Tables": [],
        }
        relevance_agent.return_value = {
            "Relevant": False,
            "Relevance_Score": 0.1,
            "Relevance_Reason": "Does not answer the query",
        }

        result = process_paper(
            "PMC999",
            title="Unrelated paper",
            query="diabetes",
            run_extended_agents=True,
        )

        self.assertFalse(result["Relevant"])
        self.assertEqual(
            result["Supplementary_Status"],
            "Not requested (paper not relevant)",
        )
        extract_supplementary.assert_not_called()

    @patch("agents.paper_agent.query_evidence_agent")
    @patch("agents.paper_agent.outcome_agent")
    @patch("agents.paper_agent.analysis_agent")
    @patch("agents.paper_agent.code_extraction_agent")
    @patch("agents.paper_agent.slr_agent")
    @patch("agents.paper_agent.relevance_agent")
    @patch("agents.paper_agent.extract_pmc_supplementary_material")
    @patch("agents.paper_agent.parse_pmc_xml")
    @patch("agents.paper_agent.get_pmc_xml")
    def test_baseline_stops_after_relevance(
        self,
        get_pmc_xml,
        parse_pmc_xml,
        extract_supplementary,
        relevance_agent,
        slr_agent,
        code_agent,
        analysis_agent,
        outcome_agent,
        query_evidence_agent,
    ):
        get_pmc_xml.return_value = "<article/>"
        parse_pmc_xml.return_value = {
            "Full_Text": "Complete article text",
            "Sections": {"Methods": "Study methods"},
            "Figures": ["Figure caption"],
            "Tables": ["Table content"],
        }
        extract_supplementary.return_value = {
            "Supplementary_Content": "Supplement text",
            "Supplementary_Status": "Downloaded",
            "Supplementary_Files": [{"name": "supplement.pdf"}],
        }
        relevance_agent.return_value = {
            "Relevant": True,
            "Relevance_Score": 0.9,
            "Relevance_Reason": "Matches the query",
        }
        slr_agent.return_value = {
            "Is_SLR": False,
            "Study_Design": "Retrospective Cohort Study",
        }

        result = process_paper(
            "PMC123",
            title="Example",
            query="diabetes",
            run_extended_agents=False,
        )

        self.assertEqual(result["Full_Text"], "Complete article text")
        self.assertEqual(result["Supplementary_Status"], "Downloaded")
        self.assertTrue(result["Relevant"])
        self.assertIsNone(result["Is_SLR"])
        self.assertEqual(result["Study_Design"], "")
        self.assertEqual(result["ICD_10_CM"], "")
        self.assertEqual(result["Analysis"], "")
        self.assertEqual(result["Analyst result"], "")
        self.assertEqual(result["Query Supporting Evidence"], "")
        self.assertEqual(result["Outcome"], "")
        self.assertEqual(result["Country"], "")
        self.assertEqual(
            relevance_agent.call_args.args[2],
            {"Methods": "Study methods"},
        )
        slr_agent.assert_not_called()
        code_agent.assert_not_called()
        analysis_agent.assert_not_called()
        outcome_agent.assert_not_called()
        query_evidence_agent.assert_not_called()

    @patch("agents.paper_agent.query_evidence_agent")
    @patch("agents.paper_agent.outcome_agent")
    @patch("agents.paper_agent.analysis_agent")
    @patch("agents.paper_agent.code_extraction_agent")
    @patch("agents.paper_agent.slr_agent")
    @patch("agents.paper_agent.relevance_agent")
    @patch("agents.paper_agent.extract_pmc_supplementary_material")
    @patch("agents.paper_agent.parse_pmc_xml")
    @patch("agents.paper_agent.get_pmc_xml")
    def test_detailed_agents_receive_sections_instead_of_full_text(
        self,
        get_pmc_xml,
        parse_pmc_xml,
        extract_supplementary,
        relevance_agent,
        slr_agent,
        code_agent,
        analysis_agent,
        outcome_agent,
        query_evidence_agent,
    ):
        sections = {
            "Methods": "Structured methods content",
            "Results": "Structured numerical results",
        }
        get_pmc_xml.return_value = "<article/>"
        parse_pmc_xml.return_value = {
            "Full_Text": "Flattened full text must remain stored only",
            "Sections": sections,
            "Figures": [],
            "Tables": [],
        }
        extract_supplementary.return_value = {
            "Supplementary_Content": "",
            "Supplementary_Status": "No supplementary files found",
            "Supplementary_Files": [],
        }
        relevance_agent.return_value = {
            "Relevant": True,
            "Relevance_Score": 0.9,
            "Relevance_Reason": "Relevant",
        }
        slr_agent.return_value = {"Is_SLR": False, "Study_Design": "Cohort Study"}
        code_agent.return_value = {}
        analysis_agent.return_value = {"Analysis": "", "Analyst result": ""}
        outcome_agent.return_value = {"Outcome": "Reported outcome", "Country": ""}
        query_evidence_agent.return_value = {"Query Supporting Evidence": "Evidence"}

        result = process_paper(
            "PMC123",
            title="Example",
            query="diabetes",
            run_extended_agents=True,
        )

        self.assertEqual(result["Full_Text"], "Flattened full text must remain stored only")
        self.assertEqual(relevance_agent.call_args.args[2], sections)
        self.assertEqual(slr_agent.call_args.args[1], sections)
        self.assertEqual(query_evidence_agent.call_args.args[2], sections)
        self.assertEqual(code_agent.call_args.args[1], sections)
        self.assertEqual(analysis_agent.call_args.args[0], sections)
        self.assertEqual(outcome_agent.call_args.args[0], sections)


if __name__ == "__main__":
    unittest.main()
