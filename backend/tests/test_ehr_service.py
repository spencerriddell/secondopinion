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


def test_ehr_service_accepts_supported_genetics():
    service = EHRService()
    patient = service.parse_and_validate(
        {
            "cancer_type": "NSCLC",
            "stage": "IV",
            "biomarkers": [{"name": "EGFR", "value": "L858R"}],
            "genetics": [{"mutation": "EGFR", "status": "mutant"}],
            "age": 62,
            "ecog": 1,
        }
    )
    assert patient.genetics[0].mutation == "EGFR"


def test_ehr_service_rejects_unknown_genetics():
    service = EHRService()
    with pytest.raises(ValueError):
        service.parse_and_validate(
            {
                "cancer_type": "NSCLC",
                "stage": "IV",
                "biomarkers": [{"name": "EGFR", "value": "L858R"}],
                "genetics": [{"mutation": "BRCA1", "status": "mutant"}],
                "age": 62,
                "ecog": 1,
            }
        )


def test_ehr_service_exposes_gene_specific_variants():
    service = EHRService()
    variants = service.supported_genetic_variants("NSCLC")
    assert "KRAS" in variants
    assert "G12C mutant" in variants["KRAS"]


def test_ehr_service_accepts_new_cancer_type_inputs():
    service = EHRService()
    patient = service.parse_and_validate(
        {
            "cancer_type": "ovarian",
            "stage": "III",
            "biomarkers": [{"name": "BRCA1", "value": "Pathogenic truncating variant"}],
            "genetics": [{"mutation": "TP53", "status": "mutant"}],
            "age": 58,
            "ecog": 1,
        }
    )
    assert patient.cancer_type.value == "ovarian"
    assert patient.genetics[0].mutation == "TP53"


def test_ehr_service_exposes_expanded_existing_variants():
    service = EHRService()
    variants = service.supported_genetic_variants("NSCLC")
    assert "G12A mutant" in variants["KRAS"]
    assert "A146T mutant" in variants["KRAS"]
    assert "G719X mutant" in variants["EGFR"]
    assert "L861Q mutant" in variants["EGFR"]
    assert "S768I mutant" in variants["EGFR"]
    assert "R248Q mutant" in variants["TP53"]


def test_ehr_service_exposes_new_cancer_type_variants():
    service = EHRService()
    variants = service.supported_genetic_variants("pancreatic")
    assert "KRAS" in variants
    assert "G12R mutant" in variants["KRAS"]
    assert "BRCA2" in variants
    assert "Pathogenic missense variant" in variants["BRCA2"]
