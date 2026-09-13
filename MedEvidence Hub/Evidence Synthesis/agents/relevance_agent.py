from typing import Any

from .openai_client import generate_json


RELEVANCE_PROMPT = """
You are a Section-Based Relevance Agent for medical, clinical, healthcare, and
life-sciences research literature.

Your task is to determine whether a medical, clinical, healthcare, or
life-sciences research paper is relevant to the user's clinical research query.

Evaluate relevance using the complete research meaning of the query.

Do not classify a paper as relevant only because it contains one isolated keyword.

Consider whether the paper meaningfully discusses the important concepts in the query, such as:

- disease or medical condition
- treatment, drug, intervention, or comparator
- population
- outcome or endpoint
- study design
- database or data source
- real-world evidence
- healthcare resource utilization
- costs or economic outcomes
- clinical setting

Rules:

1. Read the paper title and all supplied article sections.
2. Compare the paper with the corrected user query.
3. A paper is relevant when its main topic, population, methods, treatment, outcome, or research objective meaningfully matches the query.
4. A paper is not relevant when the query concepts appear only incidentally, in references, background discussion, or unrelated sections.
5. Do not invent information.
6. If the full text is missing or too short, mark the paper as not relevant.
7. Return only valid JSON.
8. Do not use Markdown or code fences.

Return exactly:

{
  "Relevant": true,
  "Relevance_Score": 0.0,
  "Relevance_Reason": ""
}

Relevance_Score must be between 0.0 and 1.0.

Corrected user query:
__QUERY__

Paper title:
__TITLE__

ARTICLE SECTIONS:
__SECTIONS__
"""


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {_text(item)}"
            for key, item in value.items()
            if _text(item)
        )
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_text(item) for item in value if _text(item))
    return str(value).strip()


def relevance_agent(query: Any, title: Any, sections: Any, max_characters: int = 60000) -> dict:
    query_text = _text(query)
    title_text = _text(title)
    sections_text = _text(sections)

    if not query_text:
        return {
            "Relevant": False,
            "Relevance_Score": 0.0,
            "Relevance_Reason": "The corrected query is missing.",
        }

    if not sections_text or len(sections_text) < 200:
        return {
            "Relevant": False,
            "Relevance_Score": 0.0,
            "Relevance_Reason": "Article sections are missing or too short.",
        }

    prompt = (
        RELEVANCE_PROMPT
        .replace("__QUERY__", query_text)
        .replace("__TITLE__", title_text)
        .replace("__SECTIONS__", sections_text[:max_characters])
    )

    try:
        data = generate_json(prompt)
    except Exception as exc:
        return {
            "Relevant": False,
            "Relevance_Score": 0.0,
            "Relevance_Reason": f"Agent request failed: {exc}",
        }

    if not isinstance(data, dict):
        data = {}

    relevant = data.get("Relevant", False)
    if isinstance(relevant, str):
        relevant = relevant.strip().lower() == "true"
    else:
        relevant = bool(relevant)

    try:
        score = float(data.get("Relevance_Score", 0.0))
    except (TypeError, ValueError):
        score = 0.0

    return {
        "Relevant": relevant,
        "Relevance_Score": round(max(0.0, min(score, 1.0)), 4),
        "Relevance_Reason": str(data.get("Relevance_Reason", "")).strip(),
    }
