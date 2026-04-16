import pytest

from app.services.ehr_service import EHRService


def test_ehr_service_accepts_supported_biomarker():
    service = EHRService()
    patient = service.parse_and_validate(
        {
            "patient_id": "p1",
            "cancer_type": "NSCLC",
            "stage": "IV",
            "biomarkers": [{"name": "EGFR", "value": "L858R"}],
            "genetics": [],
            "age": 62,
            "ecog": 1,
            "comorbidities": ["hypertension"],
            "metastases": ["brain"],
            "progression": True,
            "prior_treatments": ["osimertinib"],
            "organ_function": {"renal": "normal", "hepatic": "normal", "cardiac": "normal"},
        }
    )
    assert patient.cancer_type.value == "NSCLC"


def test_ehr_service_rejects_unknown_biomarker():
    service = EHRService()
    with pytest.raises(ValueError):
        service.parse_and_validate(
            {
                "cancer_type": "NSCLC",
                "stage": "IV",
                "biomarkers": [{"name": "HER2", "value": "positive"}],
                "genetics": [],
                "age": 62,
                "ecog": 1,
            }
        )
