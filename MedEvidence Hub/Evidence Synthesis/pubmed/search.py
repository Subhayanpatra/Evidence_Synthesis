from Bio import Entrez
from config import EMAIL, NCBI_API_KEY

Entrez.email = EMAIL
if NCBI_API_KEY:
    Entrez.api_key = NCBI_API_KEY


def search_pubmed(query: str,
                  retmax: int = 100,
                  retstart: int = 0):
    """
    Search PubMed and return PMIDs.
    """

    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=retmax,
        retstart=retstart,
        sort="relevance",
    )

    results = Entrez.read(handle)
    handle.close()

    return results["IdList"]
