import json
from dataclasses import dataclass
from datetime import UTC, datetime
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
from app.services.risk_analysis_service import PMCAEParser, RiskAnalysisService, RiskArticleFilter


@dataclass
class RiskOverride:
    risk_score: float
    risk_base_score: float
    risk_confidence_interval: tuple[float, float]
    risk_factors: list[str]
    risk_factor_breakdown: list[dict[str, int | float | str]]
    risk_mitigation_strategies: list[str]
    risk_confidence_grade: str
    comparative_risk_narrative: str
    evidence_quality_score: float

class RecommendationService:
    _target_recommendation_count = 5
    _MAX_RISK_ARTICLES = 8
    _MAX_LLM_FACTOR_INPUT = 10
    _MAX_LLM_FACTOR_OUTPUT = 8
    _RISK_COMPARISON_THRESHOLD = 0.8
    _COMPARATIVE_INSTRUCTION = (
        "State whether this treatment appears lower/equal/higher risk versus alternatives."
    )

    def __init__(self, llm_backend: str = "ollama", llm_model: str = "mistral", llm_endpoint: str | None = None) -> None:
        self.risk_service = RiskAnalysisService()
        self.risk_article_filter = RiskArticleFilter()
        self.pmc_ae_parser = PMCAEParser()
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
        candidate_treatments = [
            r.get("treatment_name", "Guideline-directed therapy")
            for r in recommendations[: self._target_recommendation_count]
            if isinstance(r, dict)
        ]
        comparative_base_scores = [
            self.risk_service.score(patient, name, articles=articles)[0]
            for name in candidate_treatments
        ]
        comparative_mean_risk = None
        if len(comparative_base_scores) > 0:
            comparative_mean_risk = round(sum(comparative_base_scores) / len(comparative_base_scores), 1)

        result: list[Recommendation] = []
        for rec in recommendations:
            built = await self._build_recommendations_with_llm_risk(
                patient,
                rec.get("treatment_name", "Guideline-directed therapy"),
                rec.get("mechanism", "Context-dependent mechanism"),
                rec.get("drug_class", "systemic"),
                rec.get("indication", "Generated from multimodal evidence"),
                articles,
                guidelines,
                pmc_articles,
                comparative_mean_risk,
            )
            result.extend(built)
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

    async def _estimate_risk_with_llm(
        self,
        patient: PatientEHR,
        treatment_name: str,
        drug_class: str,
        articles: list[PubMedArticle],
        guidelines: list[GuidelineReference],
        pmc_articles: list[PMCArticle],
        comparative_mean_risk: float | None = None,
    ) -> RiskOverride | None:
        if not self.llm_service.is_available:
            return None

        ranked_articles = self.risk_article_filter.rank_articles(
            patient, treatment_name, articles
        )[: self._MAX_RISK_ARTICLES]
        parsed_pmc_ae = self.pmc_ae_parser.parse_many(pmc_articles)[:3]
        prompt = {
            "task": "Estimate treatment-specific clinical risk from source evidence",
            "patient": patient.model_dump(),
            "treatment": {"name": treatment_name, "drug_class": drug_class},
            "articles": [
                {
                    "pmid": article.pmid,
                    "title": article.title,
                    "year": article.year,
                    "abstract": article.abstract,
                    "patient_relevance_score": round(
                        self.risk_article_filter.score_article(patient, treatment_name, article), 2
                    ),
                }
                for article in ranked_articles
            ],
            "guidelines": [g.model_dump() for g in guidelines[:3]],
            "pmc_adverse_event_tables": parsed_pmc_ae,
            "comparative_context": {
                "mean_risk_score_of_alternatives": comparative_mean_risk,
                "instruction": self._COMPARATIVE_INSTRUCTION,
            },
            "schema": {
                "risk_score": "float 1.0-10.0",
                "risk_confidence_interval": ["float", "float"],
                "risk_factors": ["str"],
                "risk_mitigation_strategies": ["str"],
                "risk_confidence_grade": "str low|moderate|high",
                "comparative_risk_narrative": "str",
                "evidence_quality_score": "float 1.0-10.0",
            },
            "instructions": (
                "Use source evidence heavily. Extract specific adverse-event rates (grade 3-4+, SAE, discontinuation) "
                "from studies and PMC full text context. Perform patient-matching analysis (age/ECOG/stage/comorbidities), "
                "compare risk vs alternatives, provide trial-cited toxicity narrative, and include practical mitigation "
                "strategies (e.g., prophylaxis, dose modification, monitoring). Output strict JSON only."
            ),
        }

        try:
            text = await self.llm_service.generate(json.dumps(prompt), max_tokens=700)
        except Exception:
            return None
        payload = self._extract_json_payload(text)
        if not payload:
            return None
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None

        risk_score = parsed.get("risk_score")
        risk_ci = parsed.get("risk_confidence_interval")
        risk_factors = parsed.get("risk_factors")
        mitigation_strategies = parsed.get("risk_mitigation_strategies")
        confidence_grade = parsed.get("risk_confidence_grade")
        comparative_narrative = parsed.get("comparative_risk_narrative")
        evidence_quality = parsed.get("evidence_quality_score")
        if not isinstance(risk_score, (int, float)):
            return None
        if not isinstance(risk_ci, list) or len(risk_ci) != 2 or not all(isinstance(v, (int, float)) for v in risk_ci):
            return None
        if not isinstance(risk_factors, list) or not all(isinstance(v, str) for v in risk_factors):
            return None
        if mitigation_strategies is not None and (
            not isinstance(mitigation_strategies, list) or not all(isinstance(v, str) for v in mitigation_strategies)
        ):
            return None
        if confidence_grade is not None and not isinstance(confidence_grade, str):
            return None
        if comparative_narrative is not None and not isinstance(comparative_narrative, str):
            return None
        if evidence_quality is not None and not isinstance(evidence_quality, (int, float)):
            return None

        bounded_score = round(max(1.0, min(10.0, float(risk_score))), 1)
        low = round(max(1.0, min(10.0, float(risk_ci[0]))), 1)
        high = round(max(1.0, min(10.0, float(risk_ci[1]))), 1)
        if low > high:
            low, high = high, low
        ranked_factors = self.risk_service.rank_risk_factors(
            patient, risk_factors[: self._MAX_LLM_FACTOR_INPUT]
        )
        return RiskOverride(
            risk_score=bounded_score,
            risk_base_score=1.5,
            risk_confidence_interval=(low, high),
            risk_factors=ranked_factors[: self._MAX_LLM_FACTOR_OUTPUT],
            risk_factor_breakdown=[],
            risk_mitigation_strategies=(mitigation_strategies or [])[:5],
            risk_confidence_grade=(confidence_grade or "moderate").lower(),
            comparative_risk_narrative=comparative_narrative or "",
            evidence_quality_score=round(max(1.0, min(10.0, float(evidence_quality or 5.0))), 1),
        )

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

    async def _build_recommendations_with_llm_risk(
        self,
        patient: PatientEHR,
        treatment_name: str,
        mechanism: str,
        drug_class: str,
        indication_text: str,
        articles: list[PubMedArticle],
        guidelines: list[GuidelineReference],
        pmc_articles: list[PMCArticle],
        comparative_mean_risk: float | None = None,
    ) -> list[Recommendation]:
        base_risk, base_ci, base_factors, base_breakdown = self.risk_service.score_with_breakdown(
            patient, treatment_name, drug_class=drug_class, articles=articles
        )
        llm_risk = await self._estimate_risk_with_llm(
            patient=patient,
            treatment_name=treatment_name,
            drug_class=drug_class,
            articles=articles,
            guidelines=guidelines,
            pmc_articles=pmc_articles,
            comparative_mean_risk=comparative_mean_risk,
        )
        if llm_risk:
            risk = llm_risk.risk_score
            ci = llm_risk.risk_confidence_interval
            factors = llm_risk.risk_factors
            mitigation = llm_risk.risk_mitigation_strategies
            confidence_grade = llm_risk.risk_confidence_grade
            comparative_narrative = llm_risk.comparative_risk_narrative
            evidence_quality_score = llm_risk.evidence_quality_score
            factors = [*factors, "Risk synthesized by LLM from provided literature and guideline context."]
        else:
            risk, ci, factors = base_risk, base_ci, base_factors
            mitigation = self._build_default_mitigation(factors)
            confidence_grade = "moderate"
            comparative_narrative = self._build_comparative_narrative(risk, comparative_mean_risk)
            evidence_quality_score = self._estimate_evidence_quality_score(articles, guidelines)

        return self._build_recommendations(
            patient=patient,
            treatment_name=treatment_name,
            mechanism=mechanism,
            drug_class=drug_class,
            indication_text=indication_text,
            articles=articles,
            risk_override=RiskOverride(
                risk_score=risk,
                risk_base_score=1.5,
                risk_confidence_interval=ci,
                risk_factors=factors,
                risk_factor_breakdown=base_breakdown,
                risk_mitigation_strategies=mitigation,
                risk_confidence_grade=confidence_grade,
                comparative_risk_narrative=comparative_narrative,
                evidence_quality_score=evidence_quality_score,
            ),
        )

    def _build_default_mitigation(self, factors: list[str]) -> list[str]:
        text = " ".join(factors).lower()
        mitigations: list[str] = []
        if "neutropenia" in text:
            mitigations.append("Consider primary G-CSF prophylaxis and early CBC monitoring.")
        if "diarrhea" in text:
            mitigations.append("Start early anti-diarrheal plan and hydration monitoring.")
        if "pneumonitis" in text or "colitis" in text or "hepatitis" in text:
            mitigations.append("Use structured irAE surveillance with rapid steroid pathway when indicated.")
        if "discontinuation" in text or "severe" in text:
            mitigations.append("Plan proactive dose-adjustment and early toxicity follow-up.")
        return mitigations[:4]

    def _build_comparative_narrative(self, risk: float, comparative_mean_risk: float | None) -> str:
        if comparative_mean_risk is None:
            return ""
        if risk >= comparative_mean_risk + self._RISK_COMPARISON_THRESHOLD:
            return f"Higher toxicity burden than cohort alternatives (risk {risk} vs mean {comparative_mean_risk})."
        if risk <= comparative_mean_risk - self._RISK_COMPARISON_THRESHOLD:
            return f"Lower toxicity burden than cohort alternatives (risk {risk} vs mean {comparative_mean_risk})."
        return f"Comparable toxicity burden to cohort alternatives (risk {risk} vs mean {comparative_mean_risk})."

    def _estimate_evidence_quality_score(
        self,
        articles: list[PubMedArticle],
        guidelines: list[GuidelineReference],
    ) -> float:
        score = 4.0
        if articles:
            score += min(3.0, 0.6 * len(articles[:5]))
        recent_threshold = datetime.now(UTC).year - 5
        if any(a.year and a.year >= recent_threshold for a in articles):
            score += 1.0
        if guidelines:
            score += 1.0
        return round(max(1.0, min(10.0, score)), 1)

    def _build_recommendations(
        self,
        patient: PatientEHR,
        treatment_name: str,
        mechanism: str,
        drug_class: str,
        indication_text: str,
        articles: list[PubMedArticle],
        risk_override: RiskOverride | None = None,
    ) -> list[Recommendation]:
        if risk_override is not None:
            risk = risk_override.risk_score
            risk_base_score = risk_override.risk_base_score
            ci = risk_override.risk_confidence_interval
            factors = risk_override.risk_factors
            factor_breakdown = risk_override.risk_factor_breakdown
            mitigation = risk_override.risk_mitigation_strategies
            confidence_grade = risk_override.risk_confidence_grade
            comparative_narrative = risk_override.comparative_risk_narrative
            evidence_quality_score = risk_override.evidence_quality_score
        else:
            risk, ci, factors, factor_breakdown = self.risk_service.score_with_breakdown(
                patient, treatment_name, drug_class=drug_class, articles=articles
            )
            risk_base_score = 1.5
            factors = self.risk_service.rank_risk_factors(patient, factors)
            mitigation = self._build_default_mitigation(factors)
            confidence_grade = "moderate"
            comparative_narrative = ""
            evidence_quality_score = self._estimate_evidence_quality_score(articles, [])
        contraindications = [
            Contraindication(**item)
            for item in self.risk_service.identify_contraindications(
                patient, treatment_name, drug_class=drug_class
            )
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
            risk_base_score=risk_base_score,
            risk_confidence_interval=ci,
            risk_factors=factors,
            risk_factor_breakdown=factor_breakdown,
            risk_mitigation_strategies=mitigation,
            risk_confidence_grade=confidence_grade,
            comparative_risk_narrative=comparative_narrative,
            evidence_quality_score=evidence_quality_score,
            efficacy_evidence=efficacy,
            citations=citation_models,
            explanation=(
                f"Risk score {risk} derived from: patient factors (age, ECOG, stage, comorbidities), "
                f"{drug_class or 'systemic'} treatment-class toxicity profile, landmark trial AE data, "
                f"patient-treatment interactions, and {len(articles)} retrieved PubMed source(s). "
                f"CI {ci[0]}–{ci[1]} reflects evidence density for this therapy."
            ),
        )
        return [recommendation]
