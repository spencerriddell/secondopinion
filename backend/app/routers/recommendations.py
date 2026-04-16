from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.models.ehr import PatientEHR
from app.models.recommendation import Recommendation, RecommendationResponse
from app.services.ehr_service import EHRService
from app.services.guideline_service import GuidelineService
from app.services.pubmed_service import PubMedService
from app.services.recommendation_service import RecommendationService

router = APIRouter(tags=["recommendations"])
_ehr_service = EHRService()
_guideline_service = GuidelineService()
_store: dict[str, Recommendation] = {}
_patient_index: dict[str, list[str]] = {}


def _pubmed(settings: Settings = Depends(get_settings)) -> PubMedService:
    return PubMedService(email=settings.ncbi_email)


def _recommendation_service(settings: Settings = Depends(get_settings)) -> RecommendationService:
    return RecommendationService(anthropic_api_key=settings.anthropic_api_key)


@router.post("/api/recommendations", response_model=RecommendationResponse)
async def create_recommendations(
    payload: dict,
    pubmed: PubMedService = Depends(_pubmed),
    recommendation_service: RecommendationService = Depends(_recommendation_service),
) -> RecommendationResponse:
    try:
        patient = _ehr_service.parse_and_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    patient_id = patient.patient_id or str(uuid4())
    patient.patient_id = patient_id

    try:
        articles = await pubmed.search(f"{patient.cancer_type.value} {patient.stage.value}")
    except Exception:
        articles = []
    guidelines = _guideline_service.search(cancer_type=patient.cancer_type.value)
    recommendations = await recommendation_service.generate(patient, articles, guidelines)

    for recommendation in recommendations:
        _store[recommendation.recommendation_id] = recommendation
        _patient_index.setdefault(patient_id, []).append(recommendation.recommendation_id)

    return RecommendationResponse(patient_id=patient_id, recommendations=recommendations)


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
