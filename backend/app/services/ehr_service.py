from app.models.ehr import PatientEHR


class EHRService:
    _supported_biomarkers = {
        "NSCLC": {"PD-L1": "%", "EGFR": "variant", "ALK": "status", "KRAS": "variant", "TP53": "variant"},
        "breast": {"HER2": "score", "ER": "%", "PR": "%", "PIK3CA": "variant", "BRCA1": "variant", "BRCA2": "variant"},
        "colorectal": {"MSI": "status", "KRAS": "variant", "NRAS": "variant", "BRAF": "variant"},
        "melanoma": {"BRAF": "variant", "NRAS": "variant", "KIT": "variant"},
        "prostate": {"AR": "status", "BRCA2": "variant", "MSI": "status"},
    }
    _supported_genetics = {
        "NSCLC": ["EGFR", "ALK", "KRAS", "ROS1", "MET", "RET", "BRAF", "ERBB2", "TP53"],
        "breast": ["BRCA1", "BRCA2", "PIK3CA", "ESR1", "ERBB2", "AKT1", "TP53"],
        "colorectal": ["KRAS", "NRAS", "BRAF", "PIK3CA", "TP53", "APC"],
        "melanoma": ["BRAF", "NRAS", "KIT", "NF1", "GNAQ", "GNA11"],
        "prostate": ["BRCA1", "BRCA2", "ATM", "PALB2", "CHEK2", "MSH2", "MSH6", "AR", "TP53"],
    }

    def parse_and_validate(self, payload: dict) -> PatientEHR:
        ehr = PatientEHR.model_validate(payload)
        allowed_biomarkers = self._supported_biomarkers.get(ehr.cancer_type.value, {})
        unknown_biomarkers = [b.name for b in ehr.biomarkers if b.name not in allowed_biomarkers]
        if unknown_biomarkers:
            raise ValueError(
                f"Unsupported biomarkers for {ehr.cancer_type.value}: {', '.join(unknown_biomarkers)}"
            )

        allowed_genetics = set(self._supported_genetics.get(ehr.cancer_type.value, []))
        unknown_genetics = [g.mutation for g in ehr.genetics if g.mutation not in allowed_genetics]
        if unknown_genetics:
            raise ValueError(
                f"Unsupported genetics for {ehr.cancer_type.value}: {', '.join(unknown_genetics)}"
            )
        return ehr

    def supported_biomarkers(self, cancer_type: str) -> dict[str, str]:
        return self._supported_biomarkers.get(cancer_type, {}).copy()

    def supported_genetics(self, cancer_type: str) -> list[str]:
        return self._supported_genetics.get(cancer_type, []).copy()
