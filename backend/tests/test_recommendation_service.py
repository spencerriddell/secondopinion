import asyncio

from app.models.ehr import Biomarker, CancerType, Genetics, OrganFunction, PatientEHR, Stage
from app.models.evidence import GuidelineReference, PubMedArticle
from app.services.recommendation_service import RecommendationService


def _patient() -> PatientEHR:
    return PatientEHR(
        patient_id="p1",
        cancer_type=CancerType.nsclc,
        stage=Stage.iv,
        biomarkers=[Biomarker(name="EGFR", value="positive")],
        genetics=[Genetics(mutation="EGFR", status="mutated")],
        age=66,
        ecog=1,
        comorbidities=["hypertension"],
        metastases=["bone"],
        progression=True,
        prior_treatments=["erlotinib"],
        organ_function=OrganFunction(renal="normal", hepatic="normal", cardiac="normal"),
    )


def _article() -> PubMedArticle:
    return PubMedArticle(
        pmid="12345",
        title="Targeted treatment outcomes",
        authors=["Doe J"],
        journal="Clinical Oncology",
        year=2024,
        abstract="Clinical efficacy observed.",
    )


def _guideline() -> GuidelineReference:
    return GuidelineReference(
        organization="NCCN",
        cancer_type="NSCLC",
        treatment="Targeted Therapy",
        version="v1.2026",
        last_updated="2026-01-01",
    )


def test_recommendation_service_falls_back_without_native_llm():
    service = RecommendationService(llm_backend="onnx", llm_model="mock")
    result = asyncio.run(service.generate(_patient(), [_article()], [_guideline()]))
    assert result
    assert len(result) == 5
    assert result[0].treatment.name == "Targeted Therapy"


def test_recommendation_service_uses_native_llm_json_payload():
    class StubLLM:
        is_available = True

        async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
            return (
                "analysis preface\n"
                '{"recommendations":[{"treatment_name":"Osimertinib","mechanism":"EGFR inhibition",'
                '"drug_class":"targeted","indication":"EGFR-mutated NSCLC"}]}\n'
                "trailer"
            )

    service = RecommendationService(llm_backend="onnx", llm_model="mock")
    service.llm_service = StubLLM()
    result = asyncio.run(service.generate(_patient(), [_article()], [_guideline()]))
    assert result
    assert len(result) == 5
    assert result[0].treatment.name == "Osimertinib"
