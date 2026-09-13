from Bio import Entrez

from config import EMAIL, NCBI_API_KEY


Entrez.email = EMAIL
if NCBI_API_KEY:
    Entrez.api_key = NCBI_API_KEY


def get_pmc_xml(pmcid: str):
    """Download real PMC XML using Entrez efetch."""
    clean_pmcid = str(pmcid).strip()
    if not clean_pmcid:
        return None

    if not clean_pmcid.startswith("PMC"):
        clean_pmcid = f"PMC{clean_pmcid}"

    try:
        handle = Entrez.efetch(
            db="pmc",
            id=clean_pmcid,
            rettype="full",
            retmode="xml",
        )
        xml_data = handle.read()
        handle.close()
        return xml_data
    except Exception:
        return None
