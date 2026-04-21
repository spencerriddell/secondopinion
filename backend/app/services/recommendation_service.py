import json
from uuid import uuid4

from app.models.ehr import PatientEHR
from app.models.evidence import GuidelineReference, PubMedArticle
from app.models.pmc import PMCArticle
from app.models.recommendation import (
    Citation,
    Contraindication,
    EfficacyEvidence,
    Indication,
    Recommendation,
    Treatment,
)
from app.services.citation_service import CitationService
from app.services.llm_service import LLMService
from app.services.risk_analysis_service import RiskAnalysisService

class RecommendationService:
    _target_recommendation_count = 5

    def __init__(self, llm_backend: str = "ollama", llm_model: str = "mistral", llm_endpoint: str | None = None) -> None:
        self.risk_service = RiskAnalysisService()
        self.citation_service = CitationService()
        self.llm_service = LLMService(backend=llm_backend, model=llm_model, endpoint=llm_endpoint)

    async def generate(
        self,
        patient: PatientEHR,
        articles: list[PubMedArticle],
        guidelines: list[GuidelineReference],
        pmc_articles: list[PMCArticle] | None = None,
    ) -> list[Recommendation]:
        pmc_articles = pmc_articles or []
        if self.llm_service.is_available:
            return await self._generate_with_native_llm(patient, articles, guidelines, pmc_articles)
        return self._fallback_recommendations(patient, articles, guidelines)

    async def _generate_with_native_llm(
        self,
        patient: PatientEHR,
        articles: list[PubMedArticle],
        guidelines: list[GuidelineReference],
        pmc_articles: list[PMCArticle],
    ) -> list[Recommendation]:
        prompt = {
            "patient": patient.model_dump(),
            "articles": [a.model_dump() for a in articles[:3]],
            "guidelines": [g.model_dump() for g in guidelines[:3]],
            "pmc_articles": [a.model_dump() for a in pmc_articles[:3]],
            "schema": {
                "recommendations": [
                    {
                        "treatment_name": "str",
                        "mechanism": "str",
                        "drug_class": "str",
                        "indication": "str",
                    }
                ]
            },
            "instructions": "Return strict JSON only and include recommendation fields matching schema.",
        }

        try:
            text = await self.llm_service.generate(json.dumps(prompt), max_tokens=1000)
        except Exception:
            return self._fallback_recommendations(patient, articles, guidelines)

        payload = self._extract_json_payload(text)
        if payload:
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError("Native LLM response parsing failed: invalid JSON payload") from exc
        else:
            parsed = {"recommendations": []}
        recommendations = parsed.get("recommendations", [])

        result: list[Recommendation] = []
        for rec in recommendations:
            result.extend(
                self._build_recommendations(
                    patient,
                    rec.get("treatment_name", "Guideline-directed therapy"),
                    rec.get("mechanism", "Context-dependent mechanism"),
                    rec.get("drug_class", "systemic"),
                    rec.get("indication", "Generated from multimodal evidence"),
                    articles,
                )
            )
        if not result:
            return self._fallback_recommendations(patient, articles, guidelines)

        fallback = self._fallback_recommendations(patient, articles, guidelines)
        seen_treatments = {item.treatment.name for item in result}
        for item in fallback:
            if item.treatment.name in seen_treatments:
                continue
            result.append(item)
            seen_treatments.add(item.treatment.name)
            if len(result) >= self._target_recommendation_count:
                break
        return result[: self._target_recommendation_count]

    def _extract_json_payload(self, text: str) -> str | None:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            return stripped[start : end + 1]
        return None

    def _fallback_recommendations(
        self,
        patient: PatientEHR,
        articles: list[PubMedArticle],
        guidelines: list[GuidelineReference],
    ) -> list[Recommendation]:
        base_recommendations: list[tuple[str, str, str, str]] = []
        if guidelines:
            top = guidelines[0]
            base_recommendations.append(
                (
                    top.treatment,
                    "Guideline-concordant multimodal anti-cancer strategy",
                    "multimodal",
                    f"{top.organization} {top.version} recommends this approach for {top.cancer_type}.",
                )
            )

        cancer_type_recommendations: dict[str, list[tuple[str, str, str, str]]] = {
            "NSCLC": [
                ("Osimertinib", "Third-generation EGFR inhibition", "targeted", "Preferred in EGFR-altered advanced NSCLC."),
                ("Pembrolizumab + platinum doublet", "PD-1 blockade plus cytotoxic backbone", "immunotherapy", "Appropriate for metastatic disease when biomarker and clinical context support immunotherapy."),
                ("Alectinib", "ALK inhibition", "targeted", "Option when ALK rearrangement is present."),
                ("Docetaxel + ramucirumab", "Anti-VEGFR2 plus cytotoxic therapy", "chemotherapy", "Consider for progression after prior systemic treatment."),
                ("Clinical trial enrollment", "Novel targeted or immunotherapy protocols", "investigational", "Recommended when standard options are exhausted or biomarker-directed trials are available."),
            ],
            "breast": [
                ("Trastuzumab + pertuzumab + taxane", "HER2 dual blockade with chemotherapy", "targeted", "Standard frontline approach in HER2-positive advanced breast cancer."),
                ("Endocrine therapy + CDK4/6 inhibitor", "Cell-cycle arrest with hormonal suppression", "targeted", "Preferred for HR-positive disease in appropriate settings."),
                ("Sacituzumab govitecan", "TROP-2 antibody-drug conjugate", "targeted", "Option in pretreated metastatic disease."),
                ("Capecitabine", "Antimetabolite chemotherapy", "chemotherapy", "Useful in sequential treatment planning."),
                ("Clinical trial enrollment", "Precision therapy expansion", "investigational", "Encouraged for biomarker-matched therapeutic strategies."),
            ],
            "colorectal": [
                ("Pembrolizumab", "PD-1 inhibition", "immunotherapy", "Preferred in MSI-H/dMMR metastatic colorectal cancer."),
                ("FOLFOX", "Cytotoxic combination chemotherapy", "chemotherapy", "Standard option for metastatic colorectal disease."),
                ("FOLFIRI + bevacizumab", "Cytotoxic therapy with anti-VEGF inhibition", "chemotherapy", "Common sequence strategy after progression."),
                ("Cetuximab (RAS wild-type)", "EGFR blockade", "targeted", "Appropriate in RAS wild-type tumors."),
                ("Clinical trial enrollment", "Novel pathway-directed therapy", "investigational", "Strongly considered for refractory disease."),
            ],
            "melanoma": [
                ("Nivolumab + ipilimumab", "Dual checkpoint inhibition", "immunotherapy", "High-activity option in advanced melanoma."),
                ("Pembrolizumab", "PD-1 inhibition", "immunotherapy", "Common first-line single-agent approach."),
                ("Dabrafenib + trametinib", "BRAF/MEK inhibition", "targeted", "Preferred in BRAF-mutant melanoma."),
                ("Relatlimab + nivolumab", "LAG-3/PD-1 checkpoint blockade", "immunotherapy", "Alternative immunotherapy combination."),
                ("Clinical trial enrollment", "Emerging cellular and checkpoint strategies", "investigational", "Recommended where available."),
            ],
            "prostate": [
                ("Androgen deprivation therapy + ARPI", "Androgen-axis suppression", "hormonal", "Backbone strategy in advanced prostate cancer."),
                ("Docetaxel", "Microtubule inhibition chemotherapy", "chemotherapy", "Systemic intensification option in fit patients."),
                ("Abiraterone + prednisone", "CYP17 inhibition", "hormonal", "Useful for metastatic hormone-sensitive or castration-resistant disease."),
                ("PARP inhibitor (BRCA-altered)", "Synthetic lethality in DNA repair deficiency", "targeted", "Recommended with qualifying homologous recombination alterations."),
                ("Clinical trial enrollment", "Novel AR and radioligand strategies", "investigational", "Encouraged for personalized escalation."),
            ],
        }
        base_recommendations.extend(cancer_type_recommendations.get(patient.cancer_type.value, []))

        if not base_recommendations:
            base_recommendations = [
                (
                    "Tumor board review and guideline-concordant systemic therapy",
                    "Evidence-guided precision treatment selection",
                    "systemic",
                    "Insufficient guideline match; recommendation based on available evidence and risk profile.",
                )
            ]

        recommendations: list[Recommendation] = []
        for name, mechanism, drug_class, indication in base_recommendations[: self._target_recommendation_count]:
            recommendations.extend(
                self._build_recommendations(patient, name, mechanism, drug_class, indication, articles)
            )
        return recommendations[: self._target_recommendation_count]

    def _build_recommendations(
        self,
        patient: PatientEHR,
        treatment_name: str,
        mechanism: str,
        drug_class: str,
        indication_text: str,
        articles: list[PubMedArticle],
    ) -> list[Recommendation]:
        risk, ci, factors = self.risk_service.score(patient, treatment_name)
        contraindications = [
            Contraindication(**item)
            for item in self.risk_service.identify_contraindications(patient, treatment_name)
        ]

        citation_models: list[Citation] = []
        for article in articles[:3]:
            citation = Citation(
                pmid=article.pmid,
                doi=article.doi,
                title=article.title,
                authors=article.authors,
                year=article.year,
                journal=article.journal,
            )
            citation.formatted = self.citation_service.format_citation(citation, style="Vancouver")
            citation_models.append(citation)

        efficacy = [
            EfficacyEvidence(
                trial_name=f"Evidence from PMID {article.pmid}",
                pmid=article.pmid,
                response_rate="See abstract",
                survival_data="See published outcomes",
            )
            for article in articles[:2]
        ]

        recommendation = Recommendation(
            recommendation_id=str(uuid4()),
            patient_id=patient.patient_id or "anonymous",
            treatment=Treatment(name=treatment_name, mechanism=mechanism, drug_class=drug_class),
            indication=Indication(clinical_rationale=indication_text),
            contraindication=contraindications,
            risk_score=risk,
            risk_confidence_interval=ci,
            risk_factors=factors,
            efficacy_evidence=efficacy,
            citations=citation_models,
            explanation=(
                "Recommendation generated from patient-specific EHR factors, guideline context, and literature evidence."
            ),
        )
        return [recommendation]
