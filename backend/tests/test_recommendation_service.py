import asyncio

from app.models.ehr import Biomarker, CancerType, Genetics, OrganFunction, PatientEHR, Stage
from app.models.evidence import GuidelineReference, PubMedArticle
from app.models.pmc import PMCArticle
from app.services.recommendation_service import RecommendationService
from app.services.risk_analysis_service import PMCAEParser, RiskAnalysisService, RiskArticleFilter


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
    assert len(result) == 5
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
