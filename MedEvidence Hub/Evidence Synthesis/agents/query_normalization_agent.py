"""Normalize a user's health-research query before Europe PMC retrieval."""

from __future__ import annotations

from .openai_client import generate_json


PROMPT = r"""You are an expert search specialist for medical, clinical,
healthcare, and life-sciences research literature.

TASK
Convert any user input into a concise, optimized Europe PMC Boolean search query. The input may be a paper title, disease, drug, treatment, clinical question, medical sentence, abbreviation, misspelling, or combination of medical, clinical, healthcare, or life-sciences research concepts.

Do not copy or mechanically rewrite a title. Identify the few concepts with the greatest retrieval value so the query can find the target paper and closely related papers.

1. INTERPRET AND NORMALIZE
- Correct spelling, capitalization, spacing, and hyphenation.
- Expand an abbreviation when its medical meaning is clear (for example, NSCLC -> Non-Small Cell Lung Cancer; T2DM -> Type 2 Diabetes Mellitus).
- Correct obvious abbreviation typos when unambiguous (for example, NSCLS -> NSCLC -> Non-Small Cell Lung Cancer).
- Normalize a clear misspelling to the intended standard concept (for example, "Diabate mallu" -> Diabetes Mellitus).
- Preserve established gene/protein notation such as PD-L1, EGFR, HER2, BRCA1, and mTOR.
- Standardize forms such as PD L1 positive -> PD-L1-positive.
- Never invent a disease subtype, stage, treatment, outcome, population, database, or code that the user did not state.

BRAND-TO-GENERIC NORMALIZATION
Convert a recognized brand to its generic drug name when the mapping is clear, for example Keytruda -> Pembrolizumab, Jardiance -> Empagliflozin, and Ozempic -> Semaglutide. Do not add a generic drug when the user mentions only a drug class.

CRITICAL INTENT PRESERVATION RULE
Conciseness must not change the user's research intent. Keep a lower-priority concept when it defines the requested relationship, outcome, setting, method, database, economic question, or coding request. Remove only concepts that are generic, redundant, or unlikely to improve retrieval.

If a short abbreviation has multiple plausible medical meanings and context does not resolve it, do not guess. Set is_ambiguous and requires_user_selection to true, leave boolean_query and normalized_query empty, and return 2-6 ranked ambiguity_options. Each option must have option_id, full_form, category, and normalized_query.

2. EXTRACT MEDICAL, CLINICAL, HEALTHCARE, AND LIFE-SCIENCES ENTITIES
Select meaningful searchable concepts such as:
- disease, disorder, syndrome, or clinical condition
- drug, drug class, treatment, procedure, herbal medicine, or device
- biomarker, gene, protein, organism, organ, microbiota, or anatomical site
- distinctive clinical outcome, population, setting, database, study method, economic concept, or coding system when it is essential to the user's intent

normalized_entities must contain only clean, standardized concepts selected for the final Boolean query. Every normalized entity must be represented in boolean_query. Do not put filler phrases or Boolean operators in normalized_entities.

3. REMOVE LOW-VALUE LANGUAGE
Exclude generic title/research wording when it does not define the request, including: effect, effects, role, study, study protocol, review, comprehensive review, investigation, analysis, assessment, evaluation, comparison, association, relationship, potential, patients with, among, using, through, based on, may, could, should, would, such as, and including.

Also exclude publication-design wording such as randomized, controlled trial, double-blind, or meta-analysis unless the user explicitly asks to restrict retrieval by study design.

Do not remove a clinical outcome, economic concept, method, setting, database, or coding system merely because it has lower general priority. Retain it when it is central or helps distinguish the target paper. For example, retain Defecation, Overall Survival, Primary Care, Optum, or International Classification of Diseases when explicitly central.

removed_words must list meaningful words or phrases from the input that were excluded from the Boolean query. Do not list punctuation or trivial articles such as "a", "an", or "the".

4. RANK AND SELECT
General priority:
1) disease/condition
2) drug/treatment/procedure/herbal medicine/device
3) distinctive biomarker, anatomy, organism, or microbiota
4) essential outcome, population, setting, method, database, economic concept, or coding system

Normally retain 2-4 high-value concepts. Use one concept when the input contains only one valid concept. Use a fifth concept only when it is essential to preserve intent or distinguish a specific target paper. Prefer a simpler query; too many AND clauses reduce recall.

For a probable paper title, retain distinctive concepts needed to retrieve that paper, not just its disease. For a broad topic, use fewer concepts. For a short misspelled term or abbreviation, normalize it without adding unrelated concepts.

5. BUILD THE BOOLEAN QUERY
- Use AND between different concepts.
- Use OR only inside parentheses for true synonyms, abbreviations, spelling variants, or alternative drug names when these materially improve retrieval.
- Put quotation marks around multi-word phrases.
- Do not add MeSH field tags unless the user explicitly asks for a MeSH-specific query.
- boolean_query and normalized_query must contain the same Europe-PMC-ready query. normalized_query is a backward-compatible alias required by the application.

Examples:

Input: MI
If no context resolves MI, return ambiguity options such as Myocardial Infarction and Mitral Insufficiency rather than guessing.

Input: NSCLS
normalized_entities: ["Non-Small Cell Lung Cancer"]
boolean_query: "\"Non-Small Cell Lung Cancer\""

Input: Diabate mallu
normalized_entities: ["Diabetes Mellitus"]
boolean_query: "\"Diabetes Mellitus\""

Input: Breast Cancer for ICD code
normalized_entities: ["Breast Cancer", "International Classification of Diseases"]
removed_words: ["for", "code"]
boolean_query: "\"Breast Cancer\" AND (\"International Classification of Diseases\" OR ICD)"

Input: Chronic limb threatening ischemia and diabetes mellitus: the severity of tibial atherosclerosis and outcome after infrapopliteal revascularization.
normalized_entities: ["Chronic Limb-Threatening Ischemia", "Diabetes Mellitus", "Tibial Atherosclerosis", "Infrapopliteal Revascularization"]
removed_words: ["Severity", "Outcome after"]
boolean_query: "\"Chronic Limb-Threatening Ischemia\" AND \"Diabetes Mellitus\" AND \"Tibial Atherosclerosis\" AND \"Infrapopliteal Revascularization\""

Input: Non-laboratory-based risk assessment model for case detection of diabetes mellitus and pre-diabetes in primary care.
normalized_entities: ["Diabetes Mellitus", "Prediabetes", "Non-Laboratory-Based Risk Assessment", "Primary Care"]
removed_words: ["Model for", "Case detection of"]
boolean_query: "\"Diabetes Mellitus\" AND Prediabetes AND \"Non-Laboratory-Based Risk Assessment\" AND \"Primary Care\""

VALIDITY
Return an invalid result only when no meaningful medical, clinical, healthcare, pharmaceutical, life-sciences, RWE, HEOR, outcome, treatment, coding, or research concept exists. A single disease, outcome, or valid abbreviation can be valid.

OUTPUT
Return only one valid JSON object. Do not use Markdown, comments, code fences, or any text outside the JSON.

Input:
{user_input}

Return exactly this structure:
{{
  "input": "",
  "original_user_query": "",
  "normalized_entities": [],
  "removed_words": [],
  "boolean_query": "",
  "normalized_query": "",
  "reason": "",
  "is_valid_medical_query": true,
  "confidence": 0.0,
  "query_style": "keyword_query",
  "is_ambiguous": false,
  "requires_user_selection": false,
  "ambiguity_options": []
}}

query_style must be exactly keyword_query, detailed_query, or invalid_query. Use detailed_query for a title or detailed clinical/research sentence, while still returning a concise Boolean query.
"""


def normalize_query(user_input: str) -> dict:
    """Return a validated, Europe-PMC-ready normalized query."""
    cleaned_input = " ".join(str(user_input).split())
    if not cleaned_input:
        return _invalid_result("")

    try:
        raw = generate_json(PROMPT.format(user_input=repr(cleaned_input)))
    except Exception as exc:
        return {
            "input": cleaned_input,
            "original_user_query": cleaned_input,
            "normalized_entities": [],
            "removed_words": [],
            "boolean_query": "",
            "normalized_query": "",
            "reason": "",
            "is_valid_medical_query": None,
            "confidence": 0.0,
            "query_style": "",
            "normalization_method": "Error",
            "normalization_warning": "",
            "error": str(exc),
        }

    if not isinstance(raw, dict):
        raise ValueError("Query normalization agent returned a non-object response.")

    boolean_query = str(raw.get("boolean_query", "")).strip()
    normalized_query = str(raw.get("normalized_query", "")).strip()
    # Accept the old response contract during rollout, but always expose both keys.
    final_query = boolean_query or normalized_query
    original_user_query = str(raw.get("original_user_query", "")).strip()
    normalized_entities = _normalize_string_list(raw.get("normalized_entities"))
    removed_words = _normalize_string_list(raw.get("removed_words"))
    reason = str(raw.get("reason", "")).strip()
    is_valid = _as_boolean(raw.get("is_valid_medical_query", False))

    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Query normalization agent returned an invalid confidence.") from exc
    confidence = max(0.0, min(1.0, confidence))

    is_ambiguous = _as_boolean(raw.get("is_ambiguous", False))
    ambiguity_options = _normalize_ambiguity_options(raw.get("ambiguity_options"))
    if is_ambiguous and len(ambiguity_options) >= 2:
        return {
            "input": cleaned_input,
            "original_user_query": original_user_query or cleaned_input,
            "normalized_entities": [],
            "removed_words": removed_words,
            "boolean_query": "",
            "normalized_query": "",
            "reason": reason,
            "is_valid_medical_query": True,
            "confidence": confidence,
            "query_style": _normalize_query_style(raw.get("query_style")),
            "is_ambiguous": True,
            "requires_user_selection": True,
            "ambiguity_options": ambiguity_options,
            "normalization_method": "OpenAI GPT",
            "normalization_warning": "",
        }

    if (
        not is_valid
        or not final_query
        or final_query.upper() in {
            "INVALID",
            "INVALID_QUERY",
            "INVALID_DISEASE",
            "INVALID_MEDICAL_TERM",
        }
    ):
        return _invalid_result(cleaned_input, confidence)

    return {
        "input": cleaned_input,
        "original_user_query": original_user_query or cleaned_input,
        "normalized_entities": normalized_entities,
        "removed_words": removed_words,
        "boolean_query": final_query,
        "normalized_query": final_query,
        "reason": reason,
        "is_valid_medical_query": True,
        "confidence": confidence,
        "query_style": _normalize_query_style(raw.get("query_style")),
        "is_ambiguous": False,
        "requires_user_selection": False,
        "ambiguity_options": [],
        "normalization_method": "OpenAI GPT",
        "normalization_warning": "",
    }


def _as_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "yes", "1"}


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values = []
    for item in value:
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
    return values


def _normalize_query_style(value: object) -> str:
    query_style = str(value or "").strip()
    if query_style not in {"keyword_query", "detailed_query"}:
        return "keyword_query"
    return query_style


def _normalize_ambiguity_options(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    options = []
    for position, item in enumerate(value[:6], start=1):
        if not isinstance(item, dict):
            continue
        normalized_query = str(item.get("normalized_query", "")).strip()
        full_form = str(item.get("full_form", "")).strip()
        if not normalized_query or not full_form:
            continue
        options.append(
            {
                "option_id": item.get("option_id", position),
                "full_form": full_form,
                "category": str(item.get("category", "")).strip(),
                "normalized_query": normalized_query,
            }
        )
    return options


def _invalid_result(user_input: str, confidence: float = 0.0) -> dict:
    return {
        "input": user_input,
        "original_user_query": user_input,
        "normalized_entities": [],
        "removed_words": [],
        "boolean_query": "",
        "normalized_query": "INVALID_MEDICAL_TERM",
        "reason": "No meaningful medical, clinical, healthcare, or life-sciences research concept was identified.",
        "is_valid_medical_query": False,
        "confidence": confidence,
        "query_style": "invalid_query",
        "is_ambiguous": False,
        "requires_user_selection": False,
        "ambiguity_options": [],
        "normalization_method": "OpenAI GPT",
        "normalization_warning": "",
    }
