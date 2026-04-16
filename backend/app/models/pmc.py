from pydantic import BaseModel, Field


class PMCArticle(BaseModel):
    pmc_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    abstract: str | None = None
    methodology: str | None = None
    results: str | None = None
    conclusions: str | None = None
    relevance_score: float = 0.0
    impact_score: float = 0.0
