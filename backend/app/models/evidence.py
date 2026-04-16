from pydantic import BaseModel


class PubMedArticle(BaseModel):
    pmid: str
    doi: str | None = None
    title: str
    authors: list[str]
    journal: str | None = None
    year: int | None = None
    abstract: str | None = None
    mesh_terms: list[str] = []


class TrialData(BaseModel):
    trial_name: str
    phase: str
    n_patients: int
    primary_outcome: str
    efficacy_rate: float | None = None


class GuidelineReference(BaseModel):
    organization: str
    cancer_type: str
    treatment: str
    version: str
    last_updated: str
