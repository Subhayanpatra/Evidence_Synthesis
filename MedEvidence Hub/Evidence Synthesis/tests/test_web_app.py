import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class WebApplicationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        with main._jobs_lock:
            main._jobs.clear()

    def test_serves_frontend_and_assets(self):
        index = self.client.get("/")
        stylesheet = self.client.get("/static/style.css")
        script = self.client.get("/static/script.js")

        self.assertEqual(index.status_code, 200)
        self.assertIn("Medical Research AI Platform", index.text)
        self.assertIn("Find evidence", index.text)
        self.assertIn("View Excel table", index.text)
        self.assertIn("Confirm normalized query", index.text)
        self.assertIn("Include SLR", index.text)
        self.assertIn("Exclude SLR", index.text)
        self.assertNotIn('id="extract-supplementary"', index.text)
        self.assertIn("Include SLR", index.text)
        self.assertIn("Exclude SLR", index.text)
        self.assertNotIn('id="extract-supplementary"', index.text)
        self.assertIn('id="data-sheet"', index.text)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn("--green:", stylesheet.text)
        self.assertIn(".sheet-table", stylesheet.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn('fetchJson("./api/search"', script.text)
        self.assertIn('fetchJson("./api/normalize"', script.text)
        self.assertIn("function renderDataSheet()", script.text)
        self.assertIn(
            'id="max-agent-papers" type="number" min="1" max="200" value="5"',
            index.text,
        )
        self.assertIn("const runAgents = elements.runAgents.checked;", script.text)
        self.assertIn('id="generate-sap"', index.text)
        self.assertIn('id="sap-result"', index.text)
        self.assertIn("generate_sap: elements.generateSap.checked", script.text)
        self.assertIn("function renderSap", script.text)

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_rejects_invalid_year_range(self):
        response = self.client.post(
            "/api/search",
            json={
                "medical_query": "diabetes",
                "normalized_query": "diabetes mellitus",
                "query_confirmed": True,
                "paper_count": 5,
                "use_year_filter": True,
                "start_year": 2026,
                "end_year": 2020,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_ignores_invalid_agent_count_when_agents_are_off(self):
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            run_agents=False,
            max_agent_papers=0,
        )

        self.assertEqual(request.max_agent_papers, 5)

    def test_rejects_invalid_agent_count_when_agents_are_on(self):
        response = self.client.post(
            "/api/search",
            json={
                "medical_query": "diabetes",
                "normalized_query": "diabetes mellitus",
                "query_confirmed": True,
                "run_agents": True,
                "max_agent_papers": 0,
            },
        )

        self.assertEqual(response.status_code, 422)

    @patch("main.process_paper")
    @patch("main.get_required_pmc_papers")
    def test_replaces_irrelevant_candidates_until_requested_count_is_reached(
        self,
        get_required_pmc_papers,
        process_paper,
    ):
        get_required_pmc_papers.return_value = [
            {"PMCID": "PMC-NO", "Title": "Unrelated"},
            {"PMCID": "PMC-YES-1", "Title": "Relevant one"},
            {"PMCID": "PMC-YES-2", "Title": "Relevant two"},
        ]
        process_paper.side_effect = [
            {"Relevant": False, "Relevance_Score": 0.1},
            {"Relevant": True, "Relevance_Score": 0.9},
            {"Relevant": True, "Relevance_Score": 0.95},
        ]
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=2,
            run_agents=False,
        )
        job_id = main._new_job(request)

        main._run_search_job(job_id, request)
        result = main._job_snapshot(job_id)["result"]

        self.assertEqual(result["returned"], 2)
        self.assertEqual(result["candidates_assessed"], 3)
        self.assertEqual(result["not_relevant"], 1)
        self.assertEqual(
            [paper["PMCID"] for paper in result["papers"]],
            ["PMC-YES-1", "PMC-YES-2"],
        )
        self.assertEqual(
            get_required_pmc_papers.call_args.kwargs["required_papers"],
            10,
        )

    @patch("main.process_paper")
    @patch("main.get_required_pmc_papers")
    def test_replaces_excluded_slr_until_requested_count_is_reached(
        self,
        get_required_pmc_papers,
        process_paper,
    ):
        get_required_pmc_papers.return_value = [
            {"PMCID": "PMC-SLR", "Title": "Systematic review"},
            {"PMCID": "PMC-STUDY-1", "Title": "Study one"},
            {"PMCID": "PMC-STUDY-2", "Title": "Study two"},
        ]
        process_paper.side_effect = [
            {"Relevant": True, "Is_SLR": True},
            {"Relevant": True, "Is_SLR": False},
            {"Relevant": True, "Is_SLR": False},
        ]
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=2,
            run_agents=True,
            max_agent_papers=2,
            slr_handling="exclude",
        )
        job_id = main._new_job(request)

        main._run_search_job(job_id, request)
        result = main._job_snapshot(job_id)["result"]

        self.assertEqual(result["returned"], 2)
        self.assertEqual(result["excluded_slr"], 1)
        self.assertEqual(
            [paper["PMCID"] for paper in result["papers"]],
            ["PMC-STUDY-1", "PMC-STUDY-2"],
        )

    @patch("main.process_paper")
    @patch("main.get_required_pmc_papers")
    def test_search_pipeline_builds_complete_job(
        self,
        get_required_pmc_papers,
        process_paper,
    ):
        get_required_pmc_papers.return_value = [
            {
                "PMCID": "PMC123",
                "PMID": "123",
                "Title": "Diabetes outcomes",
                "PublicationYear": "2025",
            }
        ]
        process_paper.return_value = {
            "Relevant": True,
            "Country": "United States",
            "ICD_10_CM": "E11.9 (Type 2 diabetes mellitus)",
        }
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            normalization_confidence=0.95,
            normalization_query_style="keyword_query",
            paper_count=1,
            run_agents=True,
            max_agent_papers=1,
            slr_handling="include",
        )
        job_id = main._new_job(request)

        main._run_search_job(job_id, request)
        job = main._job_snapshot(job_id)

        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["result"]["returned"], 1)
        self.assertEqual(job["result"]["metrics"]["countries"], 1)
        self.assertEqual(job["result"]["metrics"]["medical_codes"], 1)
        self.assertTrue(job["result"]["papers"][0]["Relevant"])
        self.assertEqual(job["result"]["normalization"]["confidence"], 0.95)
        self.assertTrue(process_paper.call_args.kwargs["include_supplementary"])
        self.assertTrue(process_paper.call_args.kwargs["run_extended_agents"])

    @patch("main.sap_agent")
    @patch("main.process_paper")
    @patch("main.get_required_pmc_papers")
    def test_sap_combines_all_returned_relevant_papers(
        self,
        get_required_pmc_papers,
        process_paper,
        sap_agent,
    ):
        get_required_pmc_papers.return_value = [
            {"PMCID": "PMC1", "Title": "First"},
            {"PMCID": "PMC2", "Title": "Second"},
        ]
        process_paper.side_effect = [
            {"Relevant": True, "Analysis": "Kaplan-Meier Analysis"},
            {"Relevant": True, "Analysis": "Cox Regression"},
        ]
        sap_agent.return_value = {
            "Title": "Combined SAP",
            "Contributing extracted papers": 2,
        }
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=2,
            run_agents=False,
            generate_sap=True,
        )
        job_id = main._new_job(request)

        main._run_search_job(job_id, request)
        result = main._job_snapshot(job_id)["result"]

        self.assertTrue(result["sap_requested"])
        self.assertEqual(result["sap"]["Contributing extracted papers"], 2)
        self.assertEqual(sap_agent.call_args.kwargs["requested"], 2)
        self.assertEqual(sap_agent.call_args.kwargs["returned"], 2)
        self.assertTrue(all(
            call.kwargs["run_extended_agents"]
            for call in process_paper.call_args_list
        ))

    @patch("main.process_paper")
    @patch("main.get_required_pmc_papers")
    def test_agents_off_still_processes_every_paper_through_relevance(
        self,
        get_required_pmc_papers,
        process_paper,
    ):
        get_required_pmc_papers.return_value = [
            {"PMCID": "PMC1", "Title": "First paper"},
            {"PMCID": "PMC2", "Title": "Second paper"},
        ]
        process_paper.side_effect = [
            {
                "Full_Text": "First full text",
                "Supplementary_Status": "No supplementary files found",
                "Relevant": True,
                "Is_SLR": None,
                "Study_Design": "",
            },
            {
                "Full_Text": "Second full text",
                "Supplementary_Status": "Downloaded",
                "Relevant": True,
                "Is_SLR": None,
                "Study_Design": "",
            },
        ]
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=2,
            run_agents=False,
            slr_handling="include",
        )
        job_id = main._new_job(request)

        main._run_search_job(job_id, request)
        papers = main._job_snapshot(job_id)["result"]["papers"]

        self.assertEqual(len(papers), 2)
        self.assertEqual(process_paper.call_count, 2)
        self.assertEqual(papers[0]["Full_Text"], "First full text")
        self.assertTrue(papers[1]["Relevant"])
        self.assertEqual(papers[1]["Study_Design"], "")
        for call in process_paper.call_args_list:
            self.assertTrue(call.kwargs["include_supplementary"])
            self.assertFalse(call.kwargs["run_extended_agents"])

    @patch("main.process_paper")
    @patch("main.get_required_pmc_papers")
    def test_exclude_slr_removes_classified_slr_papers(
        self,
        get_required_pmc_papers,
        process_paper,
    ):
        get_required_pmc_papers.return_value = [
            {"PMCID": "PMC-SLR", "Title": "Systematic review"},
            {"PMCID": "PMC-STUDY", "Title": "Cohort study"},
        ]
        process_paper.side_effect = [
            {"Relevant": True, "Is_SLR": True, "Study_Design": "Systematic Review"},
            {"Relevant": True, "Is_SLR": False, "Study_Design": "Cohort Study"},
        ]
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=2,
            run_agents=True,
            max_agent_papers=2,
            slr_handling="exclude",
        )
        job_id = main._new_job(request)

        main._run_search_job(job_id, request)
        papers = main._job_snapshot(job_id)["result"]["papers"]

        self.assertEqual([paper["PMCID"] for paper in papers], ["PMC-STUDY"])
        self.assertTrue(process_paper.call_args.kwargs["include_supplementary"])

    @patch("main.process_paper")
    @patch("main.get_required_pmc_papers")
    def test_exclude_slr_removes_classified_slr_papers(
        self,
        get_required_pmc_papers,
        process_paper,
    ):
        get_required_pmc_papers.return_value = [
            {"PMCID": "PMC-SLR", "Title": "Systematic review"},
            {"PMCID": "PMC-STUDY", "Title": "Cohort study"},
        ]
        process_paper.side_effect = [
            {"Relevant": True, "Is_SLR": True, "Study_Design": "Systematic Review"},
            {"Relevant": True, "Is_SLR": False, "Study_Design": "Cohort Study"},
        ]
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=2,
            run_agents=True,
            max_agent_papers=2,
            slr_handling="exclude",
        )
        job_id = main._new_job(request)

        main._run_search_job(job_id, request)
        papers = main._job_snapshot(job_id)["result"]["papers"]

        self.assertEqual([paper["PMCID"] for paper in papers], ["PMC-STUDY"])

    def test_downloads_completed_job_as_csv(self):
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=1,
        )
        job_id = main._new_job(request)
        main._update_job(
            job_id,
            status="complete",
            result={
                "normalization": {"normalized_query": "diabetes mellitus"},
                "papers": [{"PMCID": "PMC123", "Title": "Diabetes outcomes"}],
            },
        )

        response = self.client.get(f"/api/jobs/{job_id}/download")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("PMC123", response.content.decode("utf-8-sig"))

    def test_downloads_completed_sap_as_json(self):
        request = main.SearchRequest(
            medical_query="diabetes",
            normalized_query="diabetes mellitus",
            query_confirmed=True,
            paper_count=1,
            generate_sap=True,
        )
        job_id = main._new_job(request)
        main._update_job(
            job_id,
            status="complete",
            result={
                "normalization": {"normalized_query": "diabetes mellitus"},
                "papers": [{"PMCID": "PMC123"}],
                "sap": {"Title": "Combined SAP", "Contributing extracted papers": 1},
            },
        )

        response = self.client.get(f"/api/jobs/{job_id}/sap/download")

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers["content-type"])
        self.assertEqual(response.json()["Title"], "Combined SAP")

    @patch("main.normalize_query")
    def test_normalize_endpoint_returns_query_without_starting_search(self, normalize_query):
        normalize_query.return_value = {
            "original_user_query": "non-small cell lung cancer survival",
            "normalized_query": "non-small cell lung cancer AND survival",
            "is_valid_medical_query": True,
            "confidence": 0.96,
            "query_style": "keyword_query",
            "normalization_method": "OpenAI GPT",
        }

        response = self.client.post(
            "/api/normalize",
            json={"medical_query": "NSCLC survival"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["normalized_query"],
            "non-small cell lung cancer AND survival",
        )
        with main._jobs_lock:
            self.assertEqual(main._jobs, {})

    def test_search_rejects_unconfirmed_query(self):
        response = self.client.post(
            "/api/search",
            json={
                "medical_query": "diabetes",
                "normalized_query": "diabetes mellitus",
                "query_confirmed": False,
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
