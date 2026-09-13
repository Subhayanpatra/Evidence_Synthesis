import json
from typing import Any

from .openai_client import generate_json


SLR_PROMPT = """
You are an expert Systematic Literature Review (SLR) Identification Agent.

Classify the supplied medical, clinical, healthcare, or life-sciences research
article and identify its study design.

Set Is_SLR=true only when the article itself systematically identifies,
screens, selects, and synthesizes previous studies. A paper is not an SLR
merely because it mentions systematic reviews, searches literature for
background, combines multiple cohorts, or uses meta-analysis as a statistical
method on newly generated results.

Study_Design must be a concise, specific label supported by the article, such
as "Systematic Review and Meta-analysis", "Randomized Controlled Trial",
"Retrospective Cohort Study", "Cross-sectional Study", "Case-control Study",
"Scoping Review", "Narrative Review", or "Unclear".

If the evidence is insufficient, set Is_SLR=null and Study_Design="Unclear".
Do not invent evidence. Return only valid JSON with exactly these keys:

{
  "Is_SLR": true,
  "Study_Design": ""
}

ARTICLE TITLE:
__TITLE__

EXTRACTED SECTIONS:
__SECTIONS__
"""


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _nullable_boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def slr_agent(
    title: Any,
    sections: Any,
    max_characters: int = 90000,
) -> dict:
    title_text = _text(title)
    sections_text = _text(sections)

    if not sections_text:
        return {"Is_SLR": None, "Study_Design": "Unclear"}

    prompt = (
        SLR_PROMPT
        .replace("__TITLE__", title_text)
        .replace("__SECTIONS__", sections_text[:max_characters])
    )

    try:
        data = generate_json(prompt)
    except Exception:
        return {"Is_SLR": None, "Study_Design": "Unclear"}

    if not isinstance(data, dict):
        data = {}

    study_design = str(data.get("Study_Design", "") or "").strip()
    return {
        "Is_SLR": _nullable_boolean(data.get("Is_SLR")),
        "Study_Design": study_design or "Unclear",
    }
