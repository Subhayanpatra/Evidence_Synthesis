import json
from typing import Any

from .openai_client import generate_json


EMPTY_CODE_RESULT = {
    "ICD_9_CM": [],
    "ICD_10_CM": [],
    "ICD_10_PCS": [],
    "CPT": [],
    "HCPCS": [],
    "NDC": [],
}


CODE_EXTRACTION_PROMPT = """
You are an expert information-extraction and medical-coding specialist for
medical, clinical, healthcare, and life-sciences research literature.

Your task is to extract ONLY explicitly written medical codes from a
medical, clinical, healthcare, or life-sciences research article with maximum
precision and zero hallucination.

Read all available article content, including title, abstract, introduction,
methods, results, discussion, conclusion, structured article sections, table text, table
captions, figure text, figure captions, appendices, and supplementary text.

PRIMARY OBJECTIVE

Extract only codes explicitly reported in the article.

Do NOT infer, predict, translate, or generate codes from disease names,
procedures, drugs, or external medical knowledge.

If a string is not clearly and explicitly identified as a supported medical
code, do NOT extract it.

SUPPORTED CODING SYSTEMS

Extract only codes belonging to these coding systems:

- ICD-9-CM
- ICD-10-CM
- ICD-10-PCS
- CPT
- HCPCS
- NDC

Do NOT extract codes from other coding systems, including SNOMED CT, LOINC,
RxNorm, ATC, MedDRA, Read Codes, OPCS, DSM, MeSH, UMLS, OMOP Concept IDs,
internal database identifiers, trial registration numbers, or reference
numbers.

WHAT TO EXTRACT

Extract any supported code explicitly present in the article.

The code may represent disease, diagnosis, medical condition, comorbidity, complication, symptom, procedure, surgery, therapy, treatment, drug, biologic, medical service, diagnostic test, or healthcare intervention.

Do not restrict extraction only to the primary disease.

STRICT EXTRACTION RULES

1. Extract only codes explicitly written in the article.
2. Never infer a code from a disease, diagnosis, therapy, procedure, or drug name.
3. Preserve each code exactly as written in the article. Keep periods,
   hyphens, ranges, and wildcard symbols exactly as written. Do not normalize,
   expand, or reform codes.
4. Assign every code to the correct coding system.
5. Remove duplicate codes within the same coding system.
6. Extract the associated name only when the article explicitly connects the code with a disease, diagnosis, therapy, drug, procedure, or other medical concept.
7. If a code is written but its meaning is not explicitly stated, extract the code and leave Name empty.
8. Do not identify a code name using external medical knowledge.
9. Do not add a code simply because it resembles a valid medical code.
10. The article must provide enough context to identify the string as a
    supported medical code.
11. Preserve explicitly reported code ranges exactly as written. Do not
    expand ranges into individual codes. Examples: E10-E14, 99201-99215,
    C50.9x.
12. Preserve explicit wildcard notation exactly as written. Do not expand
    wildcard codes. Examples: C50.x, I50.xx.
13. Codes may appear in narrative paragraphs, inclusion criteria, exclusion
    criteria, cohort definitions, algorithms, appendices, tables, table
    footnotes, figure captions, figure text, or supplementary material.
14. Do not extract PMIDs, PMCIDs, DOI numbers, clinical trial registration
    numbers, database identifiers, reference numbers, statistical values,
    laboratory values, page numbers, years, or sample sizes unless explicitly
    identified as one of the supported medical coding systems.
15. If the same code is associated with multiple names and the article is
    ambiguous, leave Name empty rather than guessing.
16. Return an empty list for a coding system when no explicit code is found.
17. Return only valid JSON.
18. Do not use Markdown.
19. Do not wrap the JSON in code fences.

OUTPUT FORMAT

Return exactly this JSON structure:

{
    "ICD_9_CM": [{"Code": "", "Name": "", "Evidence": ""}],
    "ICD_10_CM": [{"Code": "", "Name": "", "Evidence": ""}],
    "ICD_10_PCS": [{"Code": "", "Name": "", "Evidence": ""}],
    "CPT": [{"Code": "", "Name": "", "Evidence": ""}],
    "HCPCS": [{"Code": "", "Name": "", "Evidence": ""}],
    "NDC": [{"Code": "", "Name": "", "Evidence": ""}]
}

Code is the exact code as written in the article.
Name is the explicitly associated concept, or an empty string when not stated.
Evidence is the exact supporting article text, or an empty string when it is
not available.

EXAMPLES

Article text:
Patients with breast cancer were identified using ICD-10-CM codes C50.911 and
C50.919. Chemotherapy administration was identified using CPT code 96413.

Correct output includes C50.911 and C50.919 under ICD_10_CM and 96413 under
CPT, with the explicitly stated names and supporting evidence.

Article text:
Patients received pembrolizumab. No medical codes were reported.

Correct output contains an empty list for every coding system.

Article text:
Eligible patients had ICD-10-CM codes E10-E14 and CPT 99201-99215 visits.

Preserve E10-E14 and 99201-99215 exactly. Do not expand the ranges.

ARTICLE CONTENT

TITLE:
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


def content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {content_to_text(item)}"
            for key, item in value.items()
            if content_to_text(item)
        )
    if isinstance(value, (list, tuple, set)):
        return "\n".join(content_to_text(item) for item in value if content_to_text(item))
    return str(value).strip()


def _normalize_code_result(data: dict) -> dict:
    result = {key: [] for key in EMPTY_CODE_RESULT}
    if not isinstance(data, dict):
        return result

    for code_system in result:
        values = data.get(code_system, [])
        if not isinstance(values, list):
            continue

        seen_codes = set()
        for item in values:
            if isinstance(item, str):
                code = item.strip()
                name = ""
            elif isinstance(item, dict):
                code = str(item.get("Code", "")).strip()
                name = str(item.get("Name", "")).strip()
                evidence = str(item.get("Evidence", "")).strip()
            else:
                continue

            if isinstance(item, str):
                evidence = ""

            if not code or code.upper() in seen_codes:
                continue

            seen_codes.add(code.upper())
            result[code_system].append(
                {
                    "Code": code,
                    "Name": name,
                    "Evidence": evidence,
                }
            )

    return result


def format_code_values(values: Any) -> str:
    if not isinstance(values, list):
        return ""

    formatted = []
    for item in values:
        if not isinstance(item, dict):
            continue
        code = str(item.get("Code", "")).strip()
        name = str(item.get("Name", "")).strip()
        if code and name:
            formatted.append(f"{code} ({name})")
        elif code:
            formatted.append(code)
    return "; ".join(formatted)


def code_extraction_agent(
    title: Any,
    sections: Any,
    tables: Any = "",
    figures: Any = "",
    supplementary_content: Any = "",
) -> dict:
    title_text = content_to_text(title)
    sections_text = content_to_text(sections)
    tables_text = content_to_text(tables)
    figures_text = content_to_text(figures)
    supplementary_text = content_to_text(supplementary_content)

    if not " ".join(
        [sections_text, tables_text, figures_text, supplementary_text]
    ).strip():
        return {key: "" for key in EMPTY_CODE_RESULT}

    prompt = (
        CODE_EXTRACTION_PROMPT
        .replace("__TITLE__", title_text)
        .replace("__SECTIONS__", sections_text)
        .replace("__TABLES__", tables_text)
        .replace("__FIGURES__", figures_text)
        .replace("__SUPPLEMENTARY_CONTENT__", supplementary_text)
    )

    try:
        data = _normalize_code_result(generate_json(prompt))
    except Exception as exc:
        data = {**EMPTY_CODE_RESULT, "Code_Agent_Error": str(exc)}

    for code_system in EMPTY_CODE_RESULT:
        if isinstance(data.get(code_system), list):
            data[code_system] = format_code_values(data[code_system])

    return data
