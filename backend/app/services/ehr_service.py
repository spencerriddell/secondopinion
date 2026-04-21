from app.models.ehr import PatientEHR


class EHRService:
    _supported_biomarkers = {
        "NSCLC": {"PD-L1", "EGFR", "ALK", "KRAS", "TP53"},
        "breast": {"HER2", "ER", "PR", "PIK3CA", "BRCA1", "BRCA2"},
        "colorectal": {"MSI", "KRAS", "NRAS", "BRAF"},
        "melanoma": {"BRAF", "NRAS", "KIT"},
        "prostate": {"AR", "BRCA2", "MSI"},
    }

    def parse_and_validate(self, payload: dict) -> PatientEHR:
        ehr = PatientEHR.model_validate(payload)
        allowed = self._supported_biomarkers.get(ehr.cancer_type.value, set())
        unknown = [b.name for b in ehr.biomarkers if b.name not in allowed]
        if unknown:
            raise ValueError(
                f"Unsupported biomarkers for {ehr.cancer_type.value}: {', '.join(unknown)}"
            )
        return ehr
