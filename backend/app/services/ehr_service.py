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
    _supported_genetic_variants = {
        "NSCLC": {
            "EGFR": ["Ex19del mutant", "L858R mutant", "T790M mutant", "Ex20ins mutant", "WT"],
            "ALK": ["EML4-ALK fusion", "ALK rearrangement", "WT"],
            "KRAS": ["G12C mutant", "G12D mutant", "G12V mutant", "Q61H mutant", "WT"],
            "ROS1": ["ROS1 fusion", "WT"],
            "MET": ["MET exon14 skipping", "MET amplification", "WT"],
            "RET": ["RET fusion", "WT"],
            "BRAF": ["V600E mutant", "Non-V600 mutant", "WT"],
            "ERBB2": ["ERBB2 exon20 insertion", "ERBB2 amplification", "WT"],
            "TP53": ["Missense mutant", "Truncating mutant", "WT"],
        },
        "breast": {
            "BRCA1": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "BRCA2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "PIK3CA": ["H1047R mutant", "E545K mutant", "E542K mutant", "WT"],
            "ESR1": ["Y537S mutant", "D538G mutant", "WT"],
            "ERBB2": ["Amplified", "Activating mutant", "WT"],
            "AKT1": ["E17K mutant", "WT"],
            "TP53": ["Missense mutant", "Truncating mutant", "WT"],
        },
        "colorectal": {
            "KRAS": ["G12D mutant", "G12V mutant", "G13D mutant", "G12C mutant", "WT"],
            "NRAS": ["Q61K mutant", "Q61R mutant", "G12D mutant", "WT"],
            "BRAF": ["V600E mutant", "Non-V600 mutant", "WT"],
            "PIK3CA": ["H1047R mutant", "E545K mutant", "E542K mutant", "WT"],
            "TP53": ["Missense mutant", "Truncating mutant", "WT"],
            "APC": ["Truncating mutant", "Missense mutant", "WT"],
        },
        "melanoma": {
            "BRAF": ["V600E mutant", "V600K mutant", "Non-V600 mutant", "WT"],
            "NRAS": ["Q61R mutant", "Q61K mutant", "Q61L mutant", "WT"],
            "KIT": ["L576P mutant", "K642E mutant", "WT"],
            "NF1": ["Loss-of-function mutant", "WT"],
            "GNAQ": ["Q209L mutant", "Q209P mutant", "WT"],
            "GNA11": ["Q209L mutant", "Q209P mutant", "WT"],
        },
        "prostate": {
            "BRCA1": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "BRCA2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "ATM": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "PALB2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "CHEK2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "MSH2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "MSH6": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "AR": ["Amplification", "T878A mutant", "L702H mutant", "WT"],
            "TP53": ["Missense mutant", "Truncating mutant", "WT"],
        },
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

    def supported_genetic_variants(self, cancer_type: str) -> dict[str, list[str]]:
        variants = self._supported_genetic_variants.get(cancer_type, {})
        return {gene: values.copy() for gene, values in variants.items()}
