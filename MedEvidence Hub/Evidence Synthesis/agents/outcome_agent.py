from typing import Any

from .openai_client import generate_json


OUTCOME_COUNTRY_PROMPT = """
You are an expert outcome and study-setting extraction agent for medical,
clinical, healthcare, and life-sciences research literature.

Your task has TWO steps.

STEP 1 - Extract the Primary Outcome

Identify the PRIMARY OUTCOME or main finding explicitly reported by the authors
in the medical, clinical, healthcare, or life-sciences research article.

The primary outcome is the central result, effect, or conclusion of the study.
It is not merely the name of an endpoint.

Use only the provided content. Do not use external knowledge.

Read all available article content, including structured abstract, methods,
results, discussion, conclusion, and other sections, plus tables, table titles, table captions, table
footnotes, figures, figure text, figure captions, appendices, and
supplementary content.

Supplementary content may contain extracted text from PDF, Word, Excel, CSV,
XML, text, table, figure, appendix, protocol, or supporting-information
files. Ignore unavailable sections and process all remaining content. Do not
duplicate information repeated across sources.

Give highest priority to:

1. RESULTS
2. CONCLUSION
3. DISCUSSION
4. TABLES and table footnotes
5. FIGURES and figure captions
6. SUPPLEMENTARY CONTENT

Use other content only when the main finding is not clearly reported in the
higher-priority content.

The outcome should describe the main study finding, not merely the name of the endpoint.

STEP 2 - Extract the Study Country

Identify the country or countries where the research study was conducted or where the study data originated.

Determine the country using explicit information about study setting, study population, participating hospitals, healthcare centers, clinics, registries, databases, claims databases, electronic health record databases, national healthcare systems, recruitment locations, data collection locations, and country-specific payer or insurance systems.

Do not determine the study country using author affiliations alone.

If the study uses data from multiple countries, return all explicitly reported countries.

If the study is described as multinational or international but individual countries are not listed, return ["Multinational"].

If the country cannot be determined explicitly, return an empty list.

PRIMARY OUTCOME RULES

1. Extract only the main finding explicitly reported by the authors.
2. Do not infer, invent, or overgeneralize findings.
3. Summarize the primary outcome in one to three concise sentences.
4. Preserve the original scientific meaning.
5. Include the important comparison when explicitly reported.
6. Include important numerical results when central to the main finding and
   explicitly reported, such as median survival, hazard ratio, odds ratio,
   risk difference, event rate, percentage change, or confidence interval.
7. Do not invent statistical significance.
8. Do not list every secondary outcome.
9. Do not return only the endpoint name.
10. Do not extract study design, statistical analysis methods, diseases without findings, medical coding systems, background information, study objectives, future research recommendations, study limitations, or author interpretations unsupported by the reported results.
11. If no primary outcome is explicitly reported, return "Not explicitly stated".

Incorrect outcome:

Overall survival

Correct outcome:

Patients receiving pembrolizumab had longer overall survival than patients
receiving chemotherapy.

Example:

Article text:
The primary endpoint was overall survival. Median overall survival was 18.4
months in the pembrolizumab group and 11.2 months in the chemotherapy group.

Correct outcome:
Pembrolizumab was associated with longer overall survival than chemotherapy,
with median overall survival of 18.4 months versus 11.2 months.

COUNTRY RULES

1. Extract only countries explicitly supported by the study setting or data
   source.
2. Do not infer the country from author names, author affiliations alone,
   journal name, corresponding-author address, or publication language.
3. A named database may support a country only when the article explicitly states the database location or population.
4. Standardize country names: USA or U.S. -> United States, UK or U.K. ->
   United Kingdom, and Republic of Korea -> South Korea.
5. Remove duplicate country names.
6. For a single-country study, return a list containing one country.
7. For a multicountry study, return all explicitly reported countries.
8. If the study is multinational but countries are not individually listed, return ["Multinational"].
9. If the study country is not explicitly stated, return an empty list.

Example:

Author affiliation: University of Tokyo, Japan
Study data: Patients were identified from the United States Medicare database.

Correct country: United States
Incorrect country: Japan

OUTPUT REQUIREMENTS

Return only valid JSON.
Do not provide explanations.
Do not use Markdown.
Do not wrap the JSON in code fences.

Return exactly this JSON structure:

{
    "Outcome": "",
    "Country": []
}

ARTICLE CONTENT

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
        return "\n".join(_content_to_text(item) for item in value if _content_to_text(item))
    return str(value).strip()


def _format_country(countries: Any) -> str:
    if isinstance(countries, str):
        countries = [countries]
    if not isinstance(countries, list):
        return ""

    cleaned = []
    seen = set()
    for country in countries:
        country = " ".join(str(country).split())
        key = country.casefold()
        if country and key not in seen:
            cleaned.append(country)
            seen.add(key)
    return "; ".join(cleaned)


def outcome_agent(
    sections: Any,
    tables: Any = "",
    figures: Any = "",
    supplementary_content: Any = "",
) -> dict:
    sections_text = _content_to_text(sections)
    tables_text = _content_to_text(tables)
    figures_text = _content_to_text(figures)
    supplementary_text = _content_to_text(supplementary_content)

    if not " ".join(
        [sections_text, tables_text, figures_text, supplementary_text]
    ).strip():
        return {"Outcome": "Not explicitly stated", "Country": ""}

    prompt = (
        OUTCOME_COUNTRY_PROMPT
        .replace("__SECTIONS__", sections_text)
        .replace("__TABLES__", tables_text)
        .replace("__FIGURES__", figures_text)
        .replace("__SUPPLEMENTARY_CONTENT__", supplementary_text)
    )

    try:
        data = generate_json(prompt)
        if not isinstance(data, dict):
            data = {}
        outcome = " ".join(str(data.get("Outcome", "Not explicitly stated")).split())
        return {
            "Outcome": outcome or "Not explicitly stated",
            "Country": _format_country(data.get("Country", [])),
        }
    except Exception as exc:
        return {
            "Outcome": "Not explicitly stated",
            "Country": "",
            "Outcome_Agent_Error": str(exc),
        }
