import asyncio

from app.models.ehr import Biomarker, CancerType, Genetics, OrganFunction, PatientEHR, Stage
from app.models.evidence import GuidelineReference, PubMedArticle
from app.models.pmc import PMCArticle
from app.services.recommendation_service import RecommendationService
from app.services.risk_analysis_service import LLMRiskAnalysisService, PMCAEParser, RiskAnalysisService, RiskArticleFilter


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
    assert len(result) >= service._min_recommendations
    assert len(result) <= service._max_recommendations
    assert result[0].treatment.name == "Targeted Therapy"
    # Risk scores should vary across treatments due to evidence-informed per-treatment scoring
    scores = [r.risk_score for r in result]
    assert len(set(scores)) > 1, "All recommendations should NOT have identical risk scores"
    assert isinstance(result[0].risk_mitigation_strategies, list)
    assert result[0].risk_confidence_grade in {"low", "moderate", "high"}


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
    assert len(result) >= service._min_recommendations
    assert len(result) <= service._max_recommendations
    assert result[0].treatment.name == "Osimertinib"
    scores = [r.risk_score for r in result]
    assert len(set(scores)) > 1, "Distinct treatments should have distinct risk scores"


def test_risk_analysis_service_scores_differ_by_drug_class():
    """Immunotherapy, chemotherapy, and targeted agents score differently for same patient."""
    risk_service = RiskAnalysisService()
    patient = _patient()

    targeted_score, _, _ = risk_service.score(patient, "Osimertinib", drug_class="targeted")
    immuno_score, _, _ = risk_service.score(patient, "Nivolumab + ipilimumab", drug_class="immunotherapy")
    chemo_score, _, _ = risk_service.score(patient, "Docetaxel", drug_class="chemotherapy")

    # Chemotherapy should score higher than targeted for same patient
    assert chemo_score > targeted_score, (
        f"Chemotherapy ({chemo_score}) should score higher than targeted ({targeted_score})"
    )
    # Dual checkpoint should score higher than targeted
    assert immuno_score > targeted_score, (
        f"Dual checkpoint immuno ({immuno_score}) should score higher than targeted ({targeted_score})"
    )


def test_risk_analysis_service_uses_article_evidence():
    """Articles mentioning adverse events for a treatment should increase its risk score."""
    risk_service = RiskAnalysisService()
    patient = _patient()

    article_with_aes = PubMedArticle(
        pmid="99999",
        title="Pembrolizumab severe adverse events grade 3-4",
        authors=["Smith A"],
        journal="JAMA Oncology",
        year=2024,
        abstract=(
            "Grade 3-4 immune-related adverse events including severe pneumonitis, colitis, "
            "and hepatitis led to treatment discontinuation in 28% of patients receiving pembrolizumab. "
            "Fatal toxicity was observed in 2% of cases. Hospitalization rates were higher than placebo."
        ),
    )
    article_no_aes = PubMedArticle(
        pmid="88888",
        title="Pembrolizumab efficacy overview",
        authors=["Jones B"],
        journal="Lancet Oncology",
        year=2024,
        abstract="Pembrolizumab improved progression-free survival significantly.",
    )

    score_with_ae_article, _, factors_with = risk_service.score(
        patient, "Pembrolizumab", drug_class="immunotherapy", articles=[article_with_aes]
    )
    score_without_ae_article, _, _ = risk_service.score(
        patient, "Pembrolizumab", drug_class="immunotherapy", articles=[article_no_aes]
    )

    assert score_with_ae_article >= score_without_ae_article, (
        "Articles with AE signals should yield equal or higher risk score"
    )
    # At least one factor should reference the evidence source
    assert any("PMID" in f or "evidence" in f.lower() for f in factors_with), (
        "Risk factors should cite the evidence source"
    )


def test_risk_analysis_ci_wider_without_evidence():
    """CI should be wider when no relevant articles are available."""
    risk_service = RiskAnalysisService()
    patient = _patient()

    _, ci_no_articles, _ = risk_service.score(patient, "Osimertinib", drug_class="targeted", articles=[])
    _, ci_with_articles, _ = risk_service.score(
        patient,
        "Osimertinib",
        drug_class="targeted",
        articles=[
            PubMedArticle(
                pmid="11111",
                title="Osimertinib safety profile in NSCLC",
                authors=["A B"],
                year=2024,
                abstract="Osimertinib was well tolerated with low grade 3-4 adverse event rates.",
            )
        ],
    )

    ci_width_no_articles = ci_no_articles[1] - ci_no_articles[0]
    ci_width_with_articles = ci_with_articles[1] - ci_with_articles[0]
    assert ci_width_no_articles >= ci_width_with_articles, (
        "CI should be wider when no relevant evidence is available"
    )


def test_risk_article_filter_prioritizes_patient_matched_recent_ae_study():
    patient = _patient()
    filt = RiskArticleFilter()
    matched_recent_ae = PubMedArticle(
        pmid="20001",
        title="Pembrolizumab in stage IV NSCLC with ECOG 1-2: grade 3-4 neutropenia 18%",
        authors=["A B"],
        year=2025,
        abstract="Median age 68 years; discontinuation 22% due to severe adverse events.",
    )
    mechanism_only = PubMedArticle(
        pmid="20002",
        title="PD-1 signaling mechanism in murine xenograft models",
        authors=["C D"],
        year=2025,
        abstract="Preclinical pathway-focused mechanism paper without adverse event outcomes.",
    )
    ranked = filt.rank_articles(patient, "Pembrolizumab", [mechanism_only, matched_recent_ae])
    assert ranked[0].pmid == "20001"


def test_pmc_ae_parser_extracts_grade34_discontinuation_and_sae():
    parser = PMCAEParser()
    article = PMCArticle(
        pmc_id="PMC123",
        title="KEYNOTE-style toxicity table",
        abstract="",
        methodology="",
        results=(
            "Grade 3-4 neutropenia occurred in 18%. Serious adverse events were 12%. "
            "Treatment discontinuation was 22%. ECOG 2 subgroup had diarrhea 28%."
        ),
        conclusions="",
    )
    parsed = parser.parse(article)
    assert parsed is not None
    assert parsed["discontinuation_rate"] == 22.0
    assert parsed["sae_rate"] == 12.0
    assert parsed["grade3_4_events"]


# ---------------------------------------------------------------------------
# LLMRiskAnalysisService tests
# ---------------------------------------------------------------------------


class _StubLLMAvailable:
    """Stub LLMService that returns a valid risk analysis JSON."""

    is_available = True

    async def generate(self, prompt: str, max_tokens: int = 800) -> str:
        return (
            '{"risk_score": 6.5, "confidence_interval": [5.5, 7.5], '
            '"risk_factors": [{"factor": "EGFR mutation aligns well with osimertinib", "contribution": -0.5, "type": "risk-mitigating"}, '
            '{"factor": "Stage IV disease elevates overall risk", "contribution": 1.5, "type": "risk-elevating"}], '
            '"reasoning": "Patient has EGFR mutation which is well-matched to osimertinib; stage IV increases risk.", '
            '"layer_breakdown": [{"layer": 1, "layer_name": "Patient", "factor": "Stage IV", "contribution": 1.5, "impact_type": "risk-elevating"}]}'
        )


class _StubLLMUnavailable:
    """Stub LLMService that is unavailable."""

    is_available = False

    async def generate(self, prompt: str, max_tokens: int = 800) -> str:
        raise RuntimeError("LLM unavailable")


def test_llm_risk_analysis_service_returns_valid_score():
    """LLMRiskAnalysisService produces valid 1.0–10.0 risk scores and CI."""
    service = LLMRiskAnalysisService(llm_service=_StubLLMAvailable())
    result = asyncio.run(
        service.analyze_risk_factors(_patient(), "Osimertinib", drug_class="targeted")
    )
    assert 1.0 <= result["score"] <= 10.0
    low, high = result["ci"]
    assert 1.0 <= low <= high <= 10.0
    assert isinstance(result["factors"], list)
    assert isinstance(result["reasoning"], str)
    assert isinstance(result["breakdown"], list)


def test_llm_risk_analysis_service_includes_llm_attribution():
    """LLM-derived risk factors include an attribution note."""
    service = LLMRiskAnalysisService(llm_service=_StubLLMAvailable())
    result = asyncio.run(
        service.analyze_risk_factors(_patient(), "Osimertinib", drug_class="targeted")
    )
    assert any("LLM" in f or "synthesised" in f.lower() for f in result["factors"]), (
        "Expected an LLM attribution note in risk factors"
    )


def test_llm_risk_analysis_service_falls_back_when_llm_unavailable():
    """LLMRiskAnalysisService falls back to rule-based scoring when LLM is unavailable."""
    service = LLMRiskAnalysisService(llm_service=_StubLLMUnavailable())
    result = asyncio.run(
        service.analyze_risk_factors(_patient(), "Osimertinib", drug_class="targeted")
    )
    assert 1.0 <= result["score"] <= 10.0
    assert "Rule-based" in result["reasoning"]


def test_llm_risk_analysis_service_falls_back_on_bad_json():
    """LLMRiskAnalysisService falls back gracefully when LLM returns unparseable output."""

    class _StubBadJSON:
        is_available = True

        async def generate(self, prompt: str, max_tokens: int = 800) -> str:
            return "this is not json at all"

    service = LLMRiskAnalysisService(llm_service=_StubBadJSON())
    result = asyncio.run(
        service.analyze_risk_factors(_patient(), "Osimertinib", drug_class="targeted")
    )
    assert 1.0 <= result["score"] <= 10.0
    assert isinstance(result["factors"], list)


def test_llm_risk_scores_differ_by_patient_treatment_combination():
    """LLM risk analysis produces different scores for different patient-treatment combos."""
    service = LLMRiskAnalysisService(llm_service=_StubLLMUnavailable())

    patient_young = PatientEHR(
        patient_id="young",
        cancer_type=CancerType.nsclc,
        stage=Stage.i,
        biomarkers=[Biomarker(name="EGFR", value="positive")],
        genetics=[Genetics(mutation="EGFR", status="mutated")],
        age=45,
        ecog=0,
        comorbidities=[],
        metastases=[],
        organ_function=OrganFunction(renal="normal", hepatic="normal", cardiac="normal"),
    )
    patient_old = PatientEHR(
        patient_id="old",
        cancer_type=CancerType.nsclc,
        stage=Stage.iv,
        biomarkers=[],
        genetics=[],
        age=80,
        ecog=3,
        comorbidities=["autoimmune disease", "hypertension"],
        metastases=["liver", "bone", "brain"],
        organ_function=OrganFunction(renal="poor", hepatic="poor", cardiac="poor"),
    )

    result_young = asyncio.run(service.analyze_risk_factors(patient_young, "Osimertinib", "targeted"))
    result_old = asyncio.run(service.analyze_risk_factors(patient_old, "Pembrolizumab", "immunotherapy"))

    assert result_old["score"] > result_young["score"], (
        "High-risk patient with poor function should score higher than low-risk young patient"
    )


# ---------------------------------------------------------------------------
# Flexible recommendation count tests
# ---------------------------------------------------------------------------


def test_flexible_recommendation_count_respects_max():
    """Recommendation service never exceeds max_recommendations."""
    service = RecommendationService(llm_backend="onnx", llm_model="mock", max_recommendations=8)
    result = asyncio.run(service.generate(_patient(), [_article()], [_guideline()]))
    assert len(result) <= 8


def test_flexible_recommendation_count_respects_min():
    """Recommendation service returns at least min_recommendations when data is available."""
    service = RecommendationService(llm_backend="onnx", llm_model="mock", min_recommendations=3)
    result = asyncio.run(service.generate(_patient(), [_article()], [_guideline()]))
    assert len(result) >= 3


def test_recommendations_can_exceed_five():
    """Recommendations are no longer hard-capped at 5."""
    service = RecommendationService(
        llm_backend="onnx", llm_model="mock", min_recommendations=3, max_recommendations=15
    )
    result = asyncio.run(service.generate(_patient(), [_article()], [_guideline()]))
    # For an NSCLC patient with a guideline, fallback produces 6 candidates (1 guideline + 5 NSCLC).
    # With max=15 we should return all of them (>5).
    assert len(result) > 5, (
        f"Expected >5 recommendations with max_recommendations=15, got {len(result)}"
    )


def test_llm_recommendations_exceed_five_with_high_max():
    """LLM path returns more than 5 recommendations when LLM supplies enough candidates."""

    class _StubLLMMany:
        is_available = True

        async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
            treatments = [
                {"treatment_name": f"Drug_{i}", "mechanism": "mechanism", "drug_class": "targeted", "indication": "ind"}
                for i in range(10)
            ]
            import json
            return json.dumps({"recommendations": treatments})

    service = RecommendationService(
        llm_backend="onnx", llm_model="mock", min_recommendations=3, max_recommendations=15
    )
    service.llm_service = _StubLLMMany()
    result = asyncio.run(service.generate(_patient(), [_article()], [_guideline()]))
    assert len(result) > 5
    assert len(result) <= 15
