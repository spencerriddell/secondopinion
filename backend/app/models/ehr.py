from enum import Enum

from pydantic import BaseModel, Field, field_validator


class CancerType(str, Enum):
    nsclc = "NSCLC"
    breast = "breast"
    colorectal = "colorectal"
    melanoma = "melanoma"
    prostate = "prostate"
    ovarian = "ovarian"
    pancreatic = "pancreatic"
    gastric = "gastric"
    hcc = "hcc"
    rcc = "rcc"


class Stage(str, Enum):
    i = "I"
    ii = "II"
    iii = "III"
    iv = "IV"


class Biomarker(BaseModel):
    name: str
    value: str
    unit: str | None = None


class Genetics(BaseModel):
    mutation: str
    status: str


class OrganFunction(BaseModel):
    renal: str | None = None
    hepatic: str | None = None
    cardiac: str | None = None


class PatientEHR(BaseModel):
    patient_id: str | None = None
    cancer_type: CancerType
    stage: Stage
    biomarkers: list[Biomarker] = Field(default_factory=list)
    genetics: list[Genetics] = Field(default_factory=list)
    age: int = Field(ge=18, le=120)
    ecog: int = Field(ge=0, le=5)
    comorbidities: list[str] = Field(default_factory=list)
    metastases: list[str] = Field(default_factory=list)
    progression: bool = False
    prior_treatments: list[str] = Field(default_factory=list)
    organ_function: OrganFunction | None = None

    @field_validator("comorbidities", "metastases", "prior_treatments")
    @classmethod
    def normalize_list_values(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]
