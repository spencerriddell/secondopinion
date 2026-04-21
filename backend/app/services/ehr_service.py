from app.models.ehr import PatientEHR


class EHRService:
    _supported_biomarkers = {
        "NSCLC": {"PD-L1": "%", "EGFR": "variant", "ALK": "status", "KRAS": "variant", "TP53": "variant"},
        "breast": {"HER2": "score", "ER": "%", "PR": "%", "PIK3CA": "variant", "BRCA1": "variant", "BRCA2": "variant"},
        "colorectal": {"MSI": "status", "KRAS": "variant", "NRAS": "variant", "BRAF": "variant"},
        "melanoma": {"BRAF": "variant", "NRAS": "variant", "KIT": "variant"},
        "prostate": {"AR": "status", "BRCA2": "variant", "MSI": "status"},
    }

    def parse_and_validate(self, payload: dict) -> PatientEHR:
        ehr = PatientEHR.model_validate(payload)
        allowed = self._supported_biomarkers.get(ehr.cancer_type.value, {})
        unknown = [b.name for b in ehr.biomarkers if b.name not in allowed]
        if unknown:
            raise ValueError(
                f"Unsupported biomarkers for {ehr.cancer_type.value}: {', '.join(unknown)}"
            )
        return ehr

    def supported_biomarkers(self, cancer_type: str) -> dict[str, str]:
        return self._supported_biomarkers.get(cancer_type, {}).copy()
