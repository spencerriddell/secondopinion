import asyncio
import logging
from datetime import date

from app.models.evidence import PubMedArticle
from app.models.pmc import PMCArticle
from app.services.pmc_service import PMCService
from app.services.pubmed_service import PubMedService


class EvidenceService:
    DEFAULT_LOOKBACK_YEARS = 5
    logger = logging.getLogger("secondopinion.evidence")

    def __init__(self, pubmed: PubMedService, pmc: PMCService) -> None:
        self.pubmed = pubmed
        self.pmc = pmc

    async def search(
        self, query: str, max_results: int = 3, date_from: str | None = None
    ) -> tuple[list[PubMedArticle], list[PMCArticle]]:
        pmc_from = date_from or f"{date.today().year - self.DEFAULT_LOOKBACK_YEARS}-01-01"
        pubmed_task = self.pubmed.search(query=query, max_results=max_results)
        pmc_task = self.pmc.search(query=query, date_from=pmc_from, max_results=max_results)
        pubmed_result, pmc_result = await asyncio.gather(pubmed_task, pmc_task, return_exceptions=True)
        if isinstance(pubmed_result, Exception):
            self.logger.warning("PubMed evidence retrieval failed: %s", pubmed_result)
        if isinstance(pmc_result, Exception):
            self.logger.warning("PMC evidence retrieval failed: %s", pmc_result)
        articles = pubmed_result if isinstance(pubmed_result, list) else []
        pmc_articles = pmc_result if isinstance(pmc_result, list) else []
        return articles, pmc_articles
