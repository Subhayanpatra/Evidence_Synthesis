import os
from concurrent.futures import ThreadPoolExecutor

from agents.analysis_agent import analysis_agent
from agents.code_agent import EMPTY_CODE_RESULT, code_extraction_agent
from agents.outcome_agent import outcome_agent
from agents.query_evidence_agent import query_evidence_agent
from agents.relevance_agent import relevance_agent
from agents.slr_agent import slr_agent
from parser.supplementary import extract_pmc_supplementary_material
from parser.xml_parser import parse_pmc_xml
from pubmed.downloader import get_pmc_xml


DETAILED_AGENT_MAX_WORKERS = max(
    1,
    min(5, int(os.getenv("DETAILED_AGENT_MAX_WORKERS", "3"))),
)


def process_paper(
    pmcid: str,
    title: str = "",
    query: str = "",
    include_supplementary: bool = True,
    run_extended_agents: bool = True,
    exclude_slr: bool = False,
) -> dict:
    xml_data = get_pmc_xml(pmcid)
    parsed = parse_pmc_xml(xml_data)

    full_text = parsed.get("Full_Text", "")
    sections = parsed.get("Sections", {})
    figures = parsed.get("Figures", [])
    tables = parsed.get("Tables", [])
    supplementary = {
        "Supplementary_Content": "",
        "Supplementary_Status": "Not requested",
        "Supplementary_Files": [],
    }

    if not full_text:
        return {
            **{key: "" for key in EMPTY_CODE_RESULT},
            "Full_Text": "",
            "Sections": {},
            "Figures": [],
            "Tables": [],
            **supplementary,
            "Relevant": False,
            "Relevance_Score": 0.0,
            "Relevance_Reason": "Full text not available in PMC XML",
            "Is_SLR": None,
            "Study_Design": "Unclear" if run_extended_agents else "",
            "Analysis": "",
            "Analyst result": "",
            "Query Supporting Evidence": "",
            "Outcome": "Full text not available in PMC XML",
            "Country": "",
        }

    relevance_result = relevance_agent(query, title, sections)
    result = {
        "Full_Text": full_text,
        "Sections": sections,
        "Figures": figures,
        "Tables": tables,
        **relevance_result,
    }

    if not relevance_result["Relevant"]:
        return {
            **result,
            **{
                **supplementary,
                "Supplementary_Status": "Not requested (paper not relevant)",
            },
            "Is_SLR": None,
            "Study_Design": "",
            **{key: "" for key in EMPTY_CODE_RESULT},
            "Analysis": "",
            "Analyst result": "",
            "Query Supporting Evidence": "",
            "Outcome": "",
            "Country": "",
        }

    preclassified_slr = slr_agent(title, sections) if exclude_slr else None
    if preclassified_slr and preclassified_slr.get("Is_SLR") is True:
        return {
            **result,
            **{
                **supplementary,
                "Supplementary_Status": "Not requested (excluded SLR)",
            },
            **preclassified_slr,
            **{key: "" for key in EMPTY_CODE_RESULT},
            "Analysis": "",
            "Analyst result": "",
            "Query Supporting Evidence": "",
            "Outcome": "",
            "Country": "",
        }

    if include_supplementary:
        try:
            supplementary = extract_pmc_supplementary_material(
                pmcid,
                xml_content=xml_data,
            )
        except Exception as exc:
            supplementary = {
                "Supplementary_Content": "",
                "Supplementary_Status": f"Processing failed: {exc}",
                "Supplementary_Files": [],
            }
    result.update(supplementary)
    supplementary_content = supplementary.get("Supplementary_Content", "")

    if not run_extended_agents:
        return {
            **result,
            "Is_SLR": None,
            "Study_Design": "",
            **{key: "" for key in EMPTY_CODE_RESULT},
            "Analysis": "",
            "Analyst result": "",
            "Query Supporting Evidence": "",
            "Outcome": "",
            "Country": "",
        }

    # Once relevance is established, these extraction tasks are independent.
    # A small per-paper pool reduces latency without concurrently processing
    # multiple papers or creating an excessive API burst.
    with ThreadPoolExecutor(
        max_workers=DETAILED_AGENT_MAX_WORKERS,
        thread_name_prefix="paper-detail",
    ) as executor:
        slr_future = None
        evidence_future = None
        if preclassified_slr is None:
            slr_future = executor.submit(slr_agent, title, sections)
        evidence_future = executor.submit(
            query_evidence_agent,
            query,
            title,
            sections,
            tables,
            figures,
            supplementary_content,
        )
        code_future = executor.submit(
            code_extraction_agent,
            title,
            sections,
            tables,
            figures,
            supplementary_content,
        )
        analysis_future = executor.submit(
            analysis_agent,
            sections,
            tables,
            figures,
            supplementary_content,
        )
        outcome_future = executor.submit(
            outcome_agent,
            sections,
            tables,
            figures,
            supplementary_content,
        )

        slr_result = (
            slr_future.result()
            if slr_future is not None
            else preclassified_slr
        )
        evidence_result = evidence_future.result()
        code_result = code_future.result()
        analysis_result = analysis_future.result()
        outcome_result = outcome_future.result()

    return {
        **result,
        **slr_result,
        **code_result,
        **analysis_result,
        **evidence_result,
        **outcome_result,
    }
