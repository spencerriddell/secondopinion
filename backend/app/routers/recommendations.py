import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.models.ehr import PatientEHR
from app.models.recommendation import Recommendation, RecommendationResponse
from app.services.ehr_service import EHRService
from app.services.evidence_service import EvidenceService
from app.services.guideline_service import GuidelineService
from app.services.pmc_service import PMCService
from app.services.pubmed_service import PubMedService
from app.services.recommendation_service import RecommendationService

router = APIRouter(tags=["recommendations"])
_ehr_service = EHRService()
_guideline_service = GuidelineService()
_store: dict[str, Recommendation] = {}
_patient_index: dict[str, list[str]] = {}
logger = logging.getLogger("secondopinion.recommendations")


def _recommendation_service(settings: Settings = Depends(get_settings)) -> RecommendationService:
    return RecommendationService(
        llm_backend=settings.llm_backend,
        llm_model=settings.llm_model,
        llm_endpoint=settings.llm_endpoint,
    )


def _evidence_service(settings: Settings = Depends(get_settings)) -> EvidenceService:
    pubmed = PubMedService(email=settings.ncbi_email, api_key=settings.pubmed_api_key)
    pmc = PMCService(
        email=settings.pmc_email or settings.ncbi_email,
        batch_size=settings.pmc_batch_size,
    )
    return EvidenceService(pubmed=pubmed, pmc=pmc)


@router.post("/api/recommendations", response_model=RecommendationResponse)
async def create_recommendations(
    payload: dict,
    evidence_service: EvidenceService = Depends(_evidence_service),
    recommendation_service: RecommendationService = Depends(_recommendation_service),
) -> RecommendationResponse:
    try:
        patient = _ehr_service.parse_and_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    patient_id = patient.patient_id or str(uuid4())
    patient.patient_id = patient_id

    try:
        articles, pmc_articles = await evidence_service.search(
            f"{patient.cancer_type.value} {patient.stage.value}"
        )
    except Exception as exc:
        logger.warning("Evidence retrieval failed; falling back to empty evidence context: %s", exc)
        articles = []
        pmc_articles = []
    guidelines = _guideline_service.search(cancer_type=patient.cancer_type.value)
    recommendations = await recommendation_service.generate(patient, articles, guidelines, pmc_articles=pmc_articles)

    for recommendation in recommendations:
        _store[recommendation.recommendation_id] = recommendation
        _patient_index.setdefault(patient_id, []).append(recommendation.recommendation_id)

    return RecommendationResponse(patient_id=patient_id, recommendations=recommendations)


@router.get("/api/biomarkers/{cancer_type}", response_model=dict[str, str])
def get_supported_biomarkers(cancer_type: str) -> dict[str, str]:
    return _ehr_service.supported_biomarkers(cancer_type)


@router.get("/api/recommendations/{recommendation_id}", response_model=Recommendation)
async def get_recommendation(recommendation_id: str) -> Recommendation:
    recommendation = _store.get(recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation


@router.get("/api/recommendations/patient/{patient_id}", response_model=list[Recommendation])
async def get_patient_recommendations(patient_id: str) -> list[Recommendation]:
    ids = _patient_index.get(patient_id, [])
    return [_store[i] for i in ids if i in _store]
