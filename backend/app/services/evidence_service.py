import asyncio
from datetime import date

from app.models.evidence import PubMedArticle
from app.models.pmc import PMCArticle
from app.services.pmc_service import PMCService
from app.services.pubmed_service import PubMedService


class EvidenceService:
    def __init__(self, pubmed: PubMedService, pmc: PMCService) -> None:
        self.pubmed = pubmed
        self.pmc = pmc

    async def search(
        self, query: str, max_results: int = 5, date_from: str | None = None
    ) -> tuple[list[PubMedArticle], list[PMCArticle]]:
        pmc_from = date_from or f"{date.today().year - 5}-01-01"
        pubmed_task = self.pubmed.search(query=query, max_results=max_results)
        pmc_task = self.pmc.search(query=query, date_from=pmc_from, max_results=max_results)
        pubmed_result, pmc_result = await asyncio.gather(pubmed_task, pmc_task, return_exceptions=True)
        articles = pubmed_result if isinstance(pubmed_result, list) else []
        pmc_articles = pmc_result if isinstance(pmc_result, list) else []
        return articles, pmc_articles
