from app.models.ehr import PatientEHR


class RiskAnalysisService:
    def score(self, patient: PatientEHR, treatment_name: str) -> tuple[float, tuple[float, float], list[str]]:
        score = 2.5
        factors: list[str] = []

        if patient.age >= 75:
            score += 1.5
            factors.append("Advanced age")
        elif patient.age >= 65:
            score += 0.8
            factors.append("Older age")

        if patient.ecog >= 3:
            score += 2.2
            factors.append("Poor ECOG performance")
        elif patient.ecog == 2:
            score += 1.0
            factors.append("Intermediate ECOG performance")

        if patient.stage.value == "IV":
            score += 1.8
            factors.append("Metastatic stage IV disease")
        elif patient.stage.value == "III":
            score += 0.9
            factors.append("Locally advanced disease")

        if patient.metastases:
            score += min(1.5, 0.4 * len(patient.metastases))
            factors.append("Documented metastatic burden")

        if patient.comorbidities:
            score += min(1.2, 0.25 * len(patient.comorbidities))
            factors.append("Comorbidity complexity")

        if "immunotherapy" in treatment_name.lower() and any(
            "autoimmune" in comorbidity.lower() for comorbidity in patient.comorbidities
        ):
            score += 1.0
            factors.append("Autoimmune condition with immunotherapy risk")

        bounded = round(max(1.0, min(10.0, score)), 1)
        ci = (round(max(1.0, bounded - 0.8), 1), round(min(10.0, bounded + 0.8), 1))
        return bounded, ci, factors

    def identify_contraindications(self, patient: PatientEHR, treatment_name: str) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        lowered = treatment_name.lower()

        if "cisplatin" in lowered and patient.organ_function and patient.organ_function.renal == "poor":
            issues.append({"risk": "Renal toxicity concern", "severity": "high"})

        if "immunotherapy" in lowered and any(
            "transplant" in comorbidity.lower() for comorbidity in patient.comorbidities
        ):
            issues.append({"risk": "Potential graft rejection", "severity": "high"})

        return issues
