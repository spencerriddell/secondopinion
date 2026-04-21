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
    assert patient.biomarkers[0].unit is None


def test_ehr_service_accepts_multiple_biomarkers_and_optional_empty_list():
    service = EHRService()
    patient_with_multiple = service.parse_and_validate(
        {
            "cancer_type": "NSCLC",
            "stage": "IV",
            "biomarkers": [{"name": "EGFR", "value": "L858R"}, {"name": "PD-L1", "value": "55", "unit": "%"}],
            "genetics": [],
            "age": 62,
            "ecog": 1,
        }
    )
    assert len(patient_with_multiple.biomarkers) == 2

    patient_without_biomarkers = service.parse_and_validate(
        {
            "cancer_type": "NSCLC",
            "stage": "IV",
            "biomarkers": [],
            "genetics": [],
            "age": 62,
            "ecog": 1,
        }
    )
    assert patient_without_biomarkers.biomarkers == []


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
