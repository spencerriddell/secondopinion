from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.models.evidence import GuidelineReference, PubMedArticle, TrialData
from app.services.guideline_service import GuidelineService
from app.services.pubmed_service import PubMedService

router = APIRouter(tags=["evidence"])
_guideline_service = GuidelineService()


def _pubmed(settings: Settings = Depends(get_settings)) -> PubMedService:
    return PubMedService(email=settings.ncbi_email, api_key=settings.pubmed_api_key)


@router.get("/api/evidence/{pmid}", response_model=PubMedArticle)
async def get_evidence(pmid: str, pubmed: PubMedService = Depends(_pubmed)) -> PubMedArticle:
    article = await pubmed.fetch_by_pmid(pmid)
    if not article:
        raise HTTPException(status_code=404, detail="PubMed article not found")
    return article


@router.get("/api/evidence/search", response_model=list[PubMedArticle])
async def search_evidence(
    query: str = Query(min_length=2),
    max_results: int = Query(default=3, ge=1, le=20),
    pubmed: PubMedService = Depends(_pubmed),
) -> list[PubMedArticle]:
    return await pubmed.search(query=query, max_results=max_results)


@router.get("/api/guidelines/search", response_model=list[GuidelineReference])
async def search_guidelines(cancer_type: str | None = None, treatment: str | None = None) -> list[GuidelineReference]:
    return _guideline_service.search(cancer_type=cancer_type, treatment=treatment)


@router.get("/api/trials/{trial_id}", response_model=TrialData)
async def get_trial(trial_id: str) -> TrialData:
    return TrialData(
        trial_name=f"Trial {trial_id}",
        phase="III",
        n_patients=550,
        primary_outcome="Progression-free survival",
        efficacy_rate=0.62,
    )
