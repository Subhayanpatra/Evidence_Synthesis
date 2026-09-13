"""Europe PMC publication search mapped to the application's paper schema."""

from __future__ import annotations

from typing import Any

import requests

from config import EMAIL


SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search_europe_pmc(
    query: str,
    max_results: int = 20,
    start_year: int | None = None,
    end_year: int | None = None,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Return open-access, PMCID-linked Europe PMC papers by relevance."""
    if max_results <= 0 or not str(query).strip():
        return []

    search_query = f"({str(query).strip()}) AND OPEN_ACCESS:y AND IN_PMC:y"
    if start_year and end_year:
        search_query += f" AND FIRST_PDATE:[{int(start_year)} TO {int(end_year)}]"

    papers: list[dict[str, Any]] = []
    seen_pmcids: set[str] = set()
    cursor_mark = "*"

    while len(papers) < max_results:
        params = {
            "query": search_query,
            "format": "json",
            "resultType": "core",
            "pageSize": min(max(page_size, 1), 1000),
            "cursorMark": cursor_mark,
        }
        if EMAIL:
            params["email"] = EMAIL

        response = requests.get(SEARCH_URL, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("resultList", {}).get("result", [])

        if not results:
            break

        for article in results:
            paper = _parse_result(article)
            pmcid = paper["PMCID"]
            if pmcid and pmcid not in seen_pmcids:
                papers.append(paper)
                seen_pmcids.add(pmcid)
            if len(papers) >= max_results:
                break

        next_cursor = payload.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor_mark:
            break
        cursor_mark = next_cursor

    return papers


def _parse_result(article: dict[str, Any]) -> dict[str, Any]:
    pmid = str(article.get("pmid") or "")
    pmcid = str(article.get("pmcid") or "")

    return {
        "PMID": pmid,
        "PMCID": pmcid,
        "Title": article.get("title") or "",
        "Abstract": article.get("abstractText") or "",
        "Journal": article.get("journalTitle") or "",
        "PublicationYear": str(article.get("pubYear") or ""),
        "Authors": article.get("authorString") or "",
        "Affiliations": _affiliations(article),
        "Language": _join(article.get("languageList", {}).get("language", [])),
        "DOI": article.get("doi") or "",
        "MeSH Terms": _mesh_terms(article),
        "Keywords": _join(article.get("keywordList", {}).get("keyword", [])),
        "Publication Types": _join(article.get("pubTypeList", {}).get("pubType", [])),
        "Chemical List": _chemical_names(article),
        "PubMedURL": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        "PMCURL": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else "",
        "Status": "PMCID found" if pmcid else "No PMCID found",
        "Search_Source": "Europe PMC",
        "Is_Open_Access": article.get("isOpenAccess"),
        "Cited_By_Count": article.get("citedByCount"),
    }


def _join(values: Any) -> str:
    if not isinstance(values, list):
        values = [values] if values else []
    return "; ".join(str(value) for value in values if value not in (None, ""))


def _affiliations(article: dict[str, Any]) -> str:
    values = []
    for author in article.get("authorList", {}).get("author", []):
        affiliation = author.get("affiliation")
        if affiliation and affiliation not in values:
            values.append(affiliation)
    return " | ".join(values)


def _mesh_terms(article: dict[str, Any]) -> str:
    values = []
    for heading in article.get("meshHeadingList", {}).get("meshHeading", []):
        descriptor = heading.get("descriptorName")
        if isinstance(descriptor, dict):
            descriptor = descriptor.get("value") or descriptor.get("#text")
        if descriptor:
            values.append(str(descriptor))
    return "; ".join(values)


def _chemical_names(article: dict[str, Any]) -> str:
    values = []
    for chemical in article.get("chemicalList", {}).get("chemical", []):
        if isinstance(chemical, dict):
            value = chemical.get("name") or chemical.get("substanceName")
        else:
            value = chemical
        if value:
            values.append(str(value))
    return "; ".join(values)
