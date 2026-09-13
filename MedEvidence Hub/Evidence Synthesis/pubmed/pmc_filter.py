"""Compatibility entry point for PMCID-based paper discovery."""

from .europe_pmc import search_europe_pmc


def get_required_pmc_papers(
    disease,
    required_papers=20,
    batch_size=100,
    start_year=None,
    end_year=None,
    max_batches=20,
):
    """Return open-access PMCID papers found through Europe PMC.

    ``max_batches`` remains in the signature for compatibility with existing
    callers; Europe PMC cursor pagination is handled by ``search_europe_pmc``.
    """
    return search_europe_pmc(
        query=disease,
        max_results=required_papers,
        start_year=start_year,
        end_year=end_year,
        page_size=batch_size,
    )
