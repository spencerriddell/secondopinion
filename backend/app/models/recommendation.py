from pydantic import BaseModel, Field


class Treatment(BaseModel):
    name: str
    mechanism: str
    drug_class: str


class Indication(BaseModel):
    clinical_rationale: str


class Contraindication(BaseModel):
    risk: str
    severity: str


class EfficacyEvidence(BaseModel):
    trial_name: str
    pmid: str | None = None
    response_rate: str | None = None
    survival_data: str | None = None


class Citation(BaseModel):
    pmid: str
    doi: str | None = None
    title: str
    authors: list[str]
    year: int | None = None
    journal: str | None = None
    format: str = "Vancouver"
    formatted: str | None = None


class RiskFactorContribution(BaseModel):
    layer: int
    layer_name: str
    factor: str
    contribution: float
    impact_type: str


class Recommendation(BaseModel):
    recommendation_id: str
    patient_id: str
    treatment: Treatment
    indication: Indication
    contraindication: list[Contraindication] = Field(default_factory=list)
    risk_score: float
    risk_base_score: float = 1.5
    risk_confidence_interval: tuple[float, float]
    risk_factors: list[str] = Field(default_factory=list)
    risk_factor_breakdown: list[RiskFactorContribution] = Field(default_factory=list)
    risk_mitigation_strategies: list[str] = Field(default_factory=list)
    risk_confidence_grade: str = "moderate"
    comparative_risk_narrative: str = ""
    evidence_quality_score: float = 5.0
    efficacy_evidence: list[EfficacyEvidence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    explanation: str


class RecommendationResponse(BaseModel):
    patient_id: str
    recommendations: list[Recommendation]
