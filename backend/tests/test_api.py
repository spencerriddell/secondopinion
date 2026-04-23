import os

from fastapi.testclient import TestClient

os.environ.setdefault("NCBI_EMAIL", "test@example.com")
from app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_recommendation():
    payload = {
        "patient_id": "patient-123",
        "cancer_type": "NSCLC",
        "stage": "IV",
        "biomarkers": [{"name": "EGFR", "value": "positive"}],
        "genetics": [{"mutation": "EGFR", "status": "mutated"}],
        "age": 66,
        "ecog": 1,
        "comorbidities": ["hypertension"],
        "metastases": ["bone"],
        "progression": True,
        "prior_treatments": ["erlotinib"],
        "organ_function": {"renal": "normal", "hepatic": "normal", "cardiac": "normal"},
    }

    response = client.post("/api/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "patient-123"
    assert data["recommendations"]
    assert len(data["recommendations"]) == 5

    rec_id = data["recommendations"][0]["recommendation_id"]
    rec = client.get(f"/api/recommendations/{rec_id}")
    assert rec.status_code == 200
    assert rec.json()["recommendation_id"] == rec_id


def test_get_supported_biomarkers():
    response = client.get("/api/biomarkers/NSCLC")
    assert response.status_code == 200
    data = response.json()
    assert "EGFR" in data
    assert data["PD-L1"] == "%"


def test_get_supported_genetics():
    response = client.get("/api/genetics/NSCLC")
    assert response.status_code == 200
    data = response.json()
    assert "EGFR" in data
    assert "ALK" in data


def test_get_supported_genetic_variants():
    response = client.get("/api/genetics/NSCLC/variants")
    assert response.status_code == 200
    data = response.json()
    assert "KRAS" in data
    assert "G12C mutant" in data["KRAS"]


def test_get_supported_biomarkers_for_new_cancer_type():
    response = client.get("/api/biomarkers/gastric")
    assert response.status_code == 200
    data = response.json()
    assert data["PD-L1"] == "%"
    assert data["MSI"] == "status"
    assert data["TMB"] == "mut/Mb"


def test_get_supported_genetics_for_new_cancer_type():
    response = client.get("/api/genetics/pancreatic")
    assert response.status_code == 200
    data = response.json()
    assert "KRAS" in data
    assert "SMAD4" in data
    assert "BRCA2" in data


def test_get_supported_genetic_variants_expansion():
    response = client.get("/api/genetics/NSCLC/variants")
    assert response.status_code == 200
    data = response.json()
    assert "G12A mutant" in data["KRAS"]
    assert "A146T mutant" in data["KRAS"]
    assert "G719X mutant" in data["EGFR"]


def test_get_supported_genetic_variants_for_new_cancer_type():
    response = client.get("/api/genetics/ovarian/variants")
    assert response.status_code == 200
    data = response.json()
    assert "BRCA1" in data
    assert "Pathogenic truncating variant" in data["BRCA1"]
    assert "CCNE1" in data
