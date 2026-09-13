import unittest
from unittest.mock import Mock, patch

from pubmed.europe_pmc import search_europe_pmc


class EuropePmcSearchTests(unittest.TestCase):
    @patch("pubmed.europe_pmc.requests.get")
    def test_maps_core_result_to_application_schema(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "resultList": {
                "result": [{
                    "pmid": "123",
                    "pmcid": "PMC456",
                    "doi": "10.1/example",
                    "title": "Example paper",
                    "abstractText": "Example abstract",
                    "journalTitle": "Example Journal",
                    "pubYear": "2024",
                    "authorString": "Smith J",
                    "isOpenAccess": "Y",
                    "citedByCount": 7,
                    "pubTypeList": {"pubType": ["research article"]},
                    "keywordList": {"keyword": ["EGFR"]},
                }]
            },
            "nextCursorMark": "next",
        }
        get.return_value = response

        papers = search_europe_pmc("EGFR", max_results=1, start_year=2020, end_year=2024)

        self.assertEqual(papers[0]["PMCID"], "PMC456")
        self.assertEqual(papers[0]["PMID"], "123")
        self.assertEqual(papers[0]["Search_Source"], "Europe PMC")
        self.assertEqual(papers[0]["Keywords"], "EGFR")
        params = get.call_args.kwargs["params"]
        self.assertIn("OPEN_ACCESS:y", params["query"])
        self.assertIn("IN_PMC:y", params["query"])
        self.assertIn("FIRST_PDATE:[2020 TO 2024]", params["query"])

    @patch("pubmed.europe_pmc.requests.get")
    def test_deduplicates_pmcids_across_cursor_pages(self, get):
        first = Mock()
        first.raise_for_status.return_value = None
        first.json.return_value = {
            "resultList": {"result": [{"pmcid": "PMC1"}]},
            "nextCursorMark": "page-2",
        }
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {
            "resultList": {"result": [{"pmcid": "PMC1"}, {"pmcid": "PMC2"}]},
            "nextCursorMark": "page-2",
        }
        get.side_effect = [first, second]

        papers = search_europe_pmc("cancer", max_results=2, page_size=1)

        self.assertEqual([paper["PMCID"] for paper in papers], ["PMC1", "PMC2"])
        self.assertEqual(get.call_args_list[1].kwargs["params"]["cursorMark"], "page-2")


if __name__ == "__main__":
    unittest.main()
