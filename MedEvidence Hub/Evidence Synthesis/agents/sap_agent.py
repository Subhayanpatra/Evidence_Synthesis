import json
from typing import Any

from .openai_client import generate_json


SAP_PROMPT = """
You are a senior statistical-analysis-plan synthesis specialist.

Create ONE consolidated, evidence-informed draft Statistical Analysis Plan
(SAP) by synthesizing the extracted information from ALL supplied relevant
medical, clinical, healthcare, and life-sciences research papers.

SAP means Statistical Analysis Plan, never the SAP business software.

The supplied records are evidence from existing papers. They are not a protocol
for a new study. Use them to identify recurring populations, treatments or
exposures, comparators, outcomes, covariates, follow-up approaches, study
designs, and statistical methods. Do not pool numerical treatment effects and
do not call this a meta-analysis.

STRICT RULES

1. Produce one SAP across all supplied papers, not one SAP per paper.
2. Use only information present in the supplied records.
3. Never invent an eligibility rule, endpoint, time window, estimand, covariate,
   model, threshold, matching ratio, censoring rule, or missing-data strategy.
4. Distinguish evidence found in papers from recommended analysis choices.
5. A method's popularity does not automatically make it appropriate. Explain
   how each recommendation relates to the observed study designs and outcomes.
6. Where the evidence is incomplete or inconsistent, add a specific item to
   "User decisions required" instead of silently choosing.
7. Cite supporting papers using PMCID or PMID in every evidence-based section.
8. State how many requested, returned, and supplied papers contributed.
9. Call the output "Draft evidence-informed SAP - statistician review required."
10. Return valid JSON only, without Markdown or code fences.

Return exactly this structure:
{
  "Title": "",
  "Document status": "Draft evidence-informed SAP - statistician review required.",
  "Evidence summary": "",
  "Study objectives": [],
  "Study design and data sources": [],
  "Study population": [],
  "Treatments exposures and comparators": [],
  "Outcomes and endpoints": [],
  "Covariates and confounders": [],
  "Analysis populations": [],
  "Descriptive analyses": [],
  "Comparative analyses": [],
  "Time-to-event analyses": [],
  "Incidence-rate analyses": [],
  "Confounding-control methods": [],
  "Missing-data handling": [],
  "Subgroup and sensitivity analyses": [],
  "Model assumptions and diagnostics": [],
  "Planned tables figures and listings": [],
  "Limitations": [],
  "User decisions required": [],
  "Supporting papers": []
}

SEARCH QUESTION:
__QUERY__

REQUESTED PAPERS: __REQUESTED__
RETURNED RELEVANT PAPERS: __RETURNED__
CONTRIBUTING EXTRACTED PAPERS: __CONTRIBUTING__

EXTRACTED PAPER RECORDS:
__PAPERS__
"""


SAP_LIST_FIELDS = (
    "Study objectives",
    "Study design and data sources",
    "Study population",
    "Treatments exposures and comparators",
    "Outcomes and endpoints",
    "Covariates and confounders",
    "Analysis populations",
    "Descriptive analyses",
    "Comparative analyses",
    "Time-to-event analyses",
    "Incidence-rate analyses",
    "Confounding-control methods",
    "Missing-data handling",
    "Subgroup and sensitivity analyses",
    "Model assumptions and diagnostics",
    "Planned tables figures and listings",
    "Limitations",
    "User decisions required",
    "Supporting papers",
)


def _paper_evidence(paper: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "PMCID",
        "PMID",
        "Title",
        "PublicationYear",
        "Abstract",
        "Study_Design",
        "Analysis",
        "Analyst result",
        "Query Supporting Evidence",
        "Outcome",
        "Country",
    )
    return {
        field: paper.get(field)
        for field in fields
        if paper.get(field) not in (None, "", [], {})
    }


def _normalize_sap(data: Any, requested: int, returned: int, contributing: int) -> dict:
    if not isinstance(data, dict):
        data = {}
    result = {
        "Title": str(data.get("Title") or "Consolidated Statistical Analysis Plan").strip(),
        "Document status": "Draft evidence-informed SAP - statistician review required.",
        "Evidence summary": str(data.get("Evidence summary") or "").strip(),
        "Requested papers": requested,
        "Returned relevant papers": returned,
        "Contributing extracted papers": contributing,
    }
    for field in SAP_LIST_FIELDS:
        value = data.get(field, [])
        if not isinstance(value, list):
            value = [value] if value else []
        result[field] = [str(item).strip() for item in value if str(item).strip()]
    return result


def sap_agent(
    query: str,
    papers: list[dict[str, Any]],
    requested: int,
    returned: int,
) -> dict:
    evidence = [
        _paper_evidence(paper)
        for paper in papers
        if paper.get("Relevant") is True and not paper.get("Agent_Error")
    ]
    evidence = [paper for paper in evidence if paper]
    contributing = len(evidence)
    if not evidence:
        return {
            **_normalize_sap({}, requested, returned, 0),
            "SAP_Agent_Error": "No successfully extracted relevant papers were available for SAP synthesis.",
        }

    prompt = (
        SAP_PROMPT.replace("__QUERY__", str(query).strip())
        .replace("__REQUESTED__", str(requested))
        .replace("__RETURNED__", str(returned))
        .replace("__CONTRIBUTING__", str(contributing))
        .replace("__PAPERS__", json.dumps(evidence, ensure_ascii=False, default=str))
    )
    try:
        return _normalize_sap(
            generate_json(prompt), requested, returned, contributing
        )
    except Exception as exc:
        return {
            **_normalize_sap({}, requested, returned, contributing),
            "SAP_Agent_Error": str(exc),
        }
