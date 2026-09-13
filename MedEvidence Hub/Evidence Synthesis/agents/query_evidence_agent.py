from typing import Any

from .openai_client import generate_json


QUERY_EVIDENCE_PROMPT = """
You are a research query-evidence extraction expert.

Your ONLY task is to extract and briefly explain concise passages from the
supplied research paper that directly answer, support, contradict, qualify, or
show uncertainty about the user's query.

Use only evidence reported by this paper. Prefer the paper's Results,
Conclusion, tables, figures, and supplementary results. The Evidence value must
be copied verbatim from the supplied paper content, apart from normalizing
whitespace. Do not paraphrase the Evidence value. Put the plain-language
explanation in the separate Explanation value.

STRICT RULES

1. Every evidence item must be directly relevant to the user's query.
2. Extract evidence produced or reported by this study. Do not extract general
   background claims, objectives, hypotheses, citations, or findings attributed
   only to another study.
3. Do not invent, infer, calculate, or combine unsupported findings.
4. Each Evidence value must be a contiguous passage present in the supplied
   content. Never generate a quotation that cannot be found in that content.
5. Keep each passage concise but include enough context to identify the
   population, intervention/exposure, comparison, outcome, direction, and
   numerical result when explicitly available.
6. Preserve important values, units, confidence intervals, p-values, time
   points, and comparison groups.
   Actively inspect Results, tables, table footnotes, figures, captions, and
   supplementary results for query-relevant numerical evidence, including:
   - sample sizes and numbers of events;
   - counts, percentages, means, medians, rates, and group differences;
   - effect estimates such as odds ratios, hazard ratios, risk ratios,
     regression coefficients, correlations, and mean differences;
   - confidence or credible intervals, standard deviations, standard errors,
     and interquartile ranges;
   - exact p-values; and
   - model-performance values such as AUC, sensitivity, specificity, accuracy,
     precision, recall, and F1 score.
   Prefer a passage containing these values over a general conclusion when both
   express the same finding.
7. Evidence may support, contradict, qualify, or fail to conclusively answer the
   query. Negative and null findings are valid evidence.
8. Set Relationship to exactly one of: Supports, Contradicts, Mixed, or
   Inconclusive.
9. Set Source to the most specific location explicitly identifiable from the
   supplied content, such as Results, Conclusion, Table 2, Figure 3, or
   Supplementary Table S1. Use "Article text" if a more specific location cannot
   be identified.
10. Do not repeat the same evidence.
11. Return no more than five of the strongest, most direct evidence items.
12. If the paper contains no direct query-specific evidence, return an empty
    list.
13. In Explanation, write one or two concise, self-contained sentences that:
    - identify which part of the user's query the evidence addresses;
    - explain the population, comparison, outcome, direction, and time point;
    - explain what the reported numerical result indicates; and
    - state important limitations visible in the evidence, such as an
      observational association, wide uncertainty, or non-significance.
14. Explanation may paraphrase only information explicitly supported by the
    supplied content. Do not introduce mechanisms, causal claims, clinical
    significance, or conclusions not reported by the paper.
15. In Numerical Results, reproduce the query-relevant numbers and their labels
    exactly as reported. Include the effect estimate, interval, p-value, unit,
    group values, sample size, or event count when available. Do not calculate,
    round, convert, reconstruct, or infer missing values. Use an empty string
    when the source reports no numerical result.
16. Distinguish adjusted from unadjusted estimates and preserve the reported
    reference group, subgroup, analysis population, model version, follow-up
    period, and time point.
17. A statistically non-significant result is not proof of no effect. An
    association is not proof of causation. Match the strength of the explanation
    to the study's reported evidence.
18. Return only valid JSON, without commentary outside the JSON, Markdown, or
    code fences.

Return exactly this JSON structure:

{
    "Query Supporting Evidence": [
        {
            "Evidence": "",
            "Explanation": "",
            "Numerical Results": "",
            "Source": "",
            "Relationship": ""
        }
    ]
}

EXAMPLE OF THE REQUIRED DETAIL

{
    "Query Supporting Evidence": [
        {
            "Evidence": "Median overall survival was 18.4 months in the treatment group and 12.1 months in the control group (HR 0.72, 95% CI 0.58-0.89; p=0.002).",
            "Explanation": "This directly addresses whether the treatment was associated with improved overall survival. The treatment group had longer median survival and a lower reported hazard of death, with the confidence interval excluding 1; the estimate should be interpreted according to the study design and not automatically as causal.",
            "Numerical Results": "18.4 months versus 12.1 months; HR 0.72; 95% CI 0.58-0.89; p=0.002",
            "Source": "Results",
            "Relationship": "Supports"
        }
    ]
}

The example demonstrates structure and level of detail only. Never copy its
wording, values, interpretation, or relationship unless supported by the
supplied paper.

USER QUERY:
__QUERY__

ARTICLE TITLE:
__TITLE__

SECTIONS:
__SECTIONS__

TABLES:
__TABLES__

FIGURES:
__FIGURES__

SUPPLEMENTARY CONTENT:
__SUPPLEMENTARY_CONTENT__
"""


def _content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {_content_to_text(item)}"
            for key, item in value.items()
            if _content_to_text(item)
        )
    if isinstance(value, (list, tuple, set)):
        return "\n".join(
            _content_to_text(item) for item in value if _content_to_text(item)
        )
    return str(value).strip()


def _normalize_evidence(data: dict, source_text: str = "") -> list[str]:
    if not isinstance(data, dict):
        return []

    values = data.get("Query Supporting Evidence", [])
    if not isinstance(values, list):
        return []

    allowed_relationships = {
        "supports": "Supports",
        "contradicts": "Contradicts",
        "mixed": "Mixed",
        "inconclusive": "Inconclusive",
    }
    evidence_items = []
    seen = set()
    normalized_source = " ".join(source_text.split()).casefold()
    for item in values[:5]:
        if not isinstance(item, dict):
            continue
        evidence = " ".join(str(item.get("Evidence", "") or "").split())
        if not evidence:
            continue
        if normalized_source and evidence.casefold() not in normalized_source:
            continue
        source = " ".join(str(item.get("Source", "") or "").split()) or "Article text"
        relationship = allowed_relationships.get(
            str(item.get("Relationship", "") or "").strip().casefold(),
            "Inconclusive",
        )
        formatted = f"[{relationship} | {source}] {evidence}"
        explanation = " ".join(
            str(item.get("Explanation", "") or "").split()
        )
        numerical_results = " ".join(
            str(item.get("Numerical Results", "") or "").split()
        )
        if explanation:
            formatted += f" | Explanation: {explanation}"
        if numerical_results:
            formatted += f" | Numerical results: {numerical_results}"
        key = formatted.casefold()
        if key not in seen:
            evidence_items.append(formatted)
            seen.add(key)
    return evidence_items


def query_evidence_agent(
    query: Any,
    title: Any,
    sections: Any,
    tables: Any = "",
    figures: Any = "",
    supplementary_content: Any = "",
) -> dict:
    query_text = _content_to_text(query)
    title_text = _content_to_text(title)
    sections_text = _content_to_text(sections)
    tables_text = _content_to_text(tables)
    figures_text = _content_to_text(figures)
    supplementary_text = _content_to_text(supplementary_content)

    if not query_text or not " ".join(
        [sections_text, tables_text, figures_text, supplementary_text]
    ).strip():
        return {"Query Supporting Evidence": ""}

    prompt = (
        QUERY_EVIDENCE_PROMPT
        .replace("__QUERY__", query_text)
        .replace("__TITLE__", title_text)
        .replace("__SECTIONS__", sections_text)
        .replace("__TABLES__", tables_text)
        .replace("__FIGURES__", figures_text)
        .replace("__SUPPLEMENTARY_CONTENT__", supplementary_text)
    )

    try:
        source_text = " ".join(
            [sections_text, tables_text, figures_text, supplementary_text]
        )
        evidence = _normalize_evidence(generate_json(prompt), source_text)
        return {"Query Supporting Evidence": "; ".join(evidence)}
    except Exception as exc:
        return {
            "Query Supporting Evidence": "",
            "Query_Evidence_Agent_Error": str(exc),
        }
