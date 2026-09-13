import re

from Bio import Entrez
from config import EMAIL, NCBI_API_KEY

Entrez.email = EMAIL
if NCBI_API_KEY:
    Entrez.api_key = NCBI_API_KEY


def fetch_metadata(pmids: list[str]):
    """Fetch PubMed XML metadata for PMID values."""
    if not pmids:
        return []

    handle = Entrez.efetch(
        db="pubmed",
        id=",".join(pmids),
        rettype="xml",
        retmode="xml",
    )

    records = Entrez.read(handle)
    handle.close()

    return records.get("PubmedArticle", [])


def parse_articles(articles) -> list[dict]:
    """Convert Entrez PubMedArticle XML objects into table-friendly records."""
    records = []

    for article in articles:
        citation = article.get("MedlineCitation", {})
        pubmed_data = article.get("PubmedData", {})
        article_data = citation.get("Article", {})

        pmid = str(citation.get("PMID", ""))
        title = str(article_data.get("ArticleTitle", ""))
        abstract = _extract_abstract(article_data)
        journal = str(article_data.get("Journal", {}).get("Title", ""))
        publication_year = _extract_year(article_data)
        authors, affiliations = _extract_authors_and_affiliations(article_data)
        doi, pmcid = _extract_article_ids(pubmed_data)
        mesh_terms = _extract_mesh_terms(citation)
        keywords = _extract_keywords(citation)
        publication_types = _extract_publication_types(article_data)
        chemical_list = _extract_chemical_list(citation)
        languages = [str(language) for language in article_data.get("Language", [])]

        records.append(
            {
                "PMID": pmid,
                "PMCID": pmcid,
                "Title": title,
                "Abstract": abstract,
                "Journal": journal,
                "PublicationYear": publication_year,
                "Authors": "; ".join(authors),
                "Affiliations": " | ".join(affiliations),
                "Language": "; ".join(languages),
                "DOI": doi,
                "MeSH Terms": "; ".join(mesh_terms),
                "Keywords": "; ".join(keywords),
                "Publication Types": "; ".join(publication_types),
                "Chemical List": "; ".join(chemical_list),
                "PubMedURL": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "PMCURL": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else "",
                "Status": "PMCID found" if pmcid else "No PMCID found",
            }
        )

    return records


def attach_pmcids_from_links(records: list[dict], pmid_to_pmcid: dict[str, str]) -> list[dict]:
    """Fill missing PMCID values from a PMID-to-PMCID map."""
    updated = []

    for record in records:
        item = record.copy()
        pmid = item.get("PMID", "")
        linked_pmcid = pmid_to_pmcid.get(pmid, "")

        if linked_pmcid and not item.get("PMCID"):
            item["PMCID"] = linked_pmcid
            item["PMCURL"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{linked_pmcid}/"
            item["Status"] = "PMCID found"

        updated.append(item)

    return updated


def parse_pmc_summaries(summaries) -> list[dict]:
    """Convert PMC esummary records into table-friendly records."""
    records = []

    for item in summaries:
        article_ids = item.get("ArticleIds", {})
        pmid = str(article_ids.get("pmid", ""))
        pmcid = str(article_ids.get("pmcid", ""))
        doi = str(article_ids.get("doi", "") or item.get("DOI", ""))
        authors = item.get("AuthorList", [])
        pub_date = str(item.get("PubDate", ""))

        records.append(
            {
                "PMID": pmid,
                "PMCID": pmcid,
                "Title": str(item.get("Title", "")),
                "Abstract": "",
                "Journal": str(item.get("FullJournalName", "") or item.get("Source", "")),
                "PublicationYear": pub_date[:4],
                "Authors": ", ".join(authors),
                "Affiliations": "",
                "Language": "",
                "DOI": doi,
                "MeSH Terms": "",
                "Keywords": "",
                "Publication Types": "",
                "Chemical List": "",
                "PubMedURL": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "PMCURL": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else "",
                "Status": "PMCID found" if pmcid else "No PMCID found",
            }
        )

    return records


def merge_pubmed_metadata(records: list[dict], pubmed_records: list[dict]) -> list[dict]:
    """Overlay richer PubMed metadata onto existing PMCID records."""
    by_pmid = {record.get("PMID", ""): record for record in pubmed_records}
    merged = []

    for record in records:
        pmid = record.get("PMID", "")
        pubmed_record = by_pmid.get(pmid, {})
        item = record.copy()

        for key, value in pubmed_record.items():
            if key == "PMCID" and item.get("PMCID"):
                continue
            if value not in ("", None, [], {}):
                item[key] = value

        merged.append(item)

    return merged


def _extract_year(article_data) -> str:
    try:
        pub_date = article_data["Journal"]["JournalIssue"]["PubDate"]
    except KeyError:
        return ""

    if "Year" in pub_date:
        return str(pub_date["Year"])
    if "MedlineDate" in pub_date:
        year_match = re.search(r"\d{4}", str(pub_date["MedlineDate"]))
        return year_match.group(0) if year_match else ""
    return ""


def _extract_authors_and_affiliations(article_data) -> tuple[list[str], list[str]]:
    authors = []
    affiliations = []
    for author in article_data.get("AuthorList", []):
        collective_name = str(author.get("CollectiveName", "")).strip()
        last = author.get("LastName", "")
        first = author.get("ForeName", "")
        name = collective_name or f"{first} {last}".strip()
        if name:
            authors.append(name)

        for affiliation_info in author.get("AffiliationInfo", []):
            affiliation = str(affiliation_info.get("Affiliation", "")).strip()
            if affiliation:
                affiliations.append(affiliation)

    unique_affiliations = []
    seen = set()
    for affiliation in affiliations:
        key = affiliation.casefold()
        if key not in seen:
            unique_affiliations.append(affiliation)
            seen.add(key)
    return authors, unique_affiliations


def _extract_abstract(article_data) -> str:
    abstract = article_data.get("Abstract", {})
    texts = []

    for item in abstract.get("AbstractText", []):
        label = item.attributes.get("Label", "") if hasattr(item, "attributes") else ""
        text = str(item)
        if label:
            texts.append(f"{label}: {text}")
        else:
            texts.append(text)

    return "\n".join(texts)


def _extract_mesh_terms(citation) -> list[str]:
    terms = []

    for heading in citation.get("MeshHeadingList", []):
        descriptor = heading.get("DescriptorName", "")
        if descriptor:
            terms.append(str(descriptor))

    return terms


def _extract_keywords(citation) -> list[str]:
    keywords = []

    for keyword_list in citation.get("KeywordList", []):
        for keyword in keyword_list:
            keywords.append(str(keyword))

    return keywords


def _extract_publication_types(article_data) -> list[str]:
    return [str(item) for item in article_data.get("PublicationTypeList", [])]


def _extract_chemical_list(citation) -> list[str]:
    chemicals = []

    for chemical in citation.get("ChemicalList", []):
        name = chemical.get("NameOfSubstance", "")
        if name:
            chemicals.append(str(name))

    return chemicals


def _extract_article_ids(pubmed_data) -> tuple[str, str]:
    doi = ""
    pmcid = ""

    for item in pubmed_data.get("ArticleIdList", []):
        id_type = item.attributes.get("IdType")
        if id_type == "doi":
            doi = str(item)
        elif id_type == "pmc":
            pmcid = str(item)

    return doi, pmcid
