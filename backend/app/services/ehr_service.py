from app.models.ehr import PatientEHR


class EHRService:
    _supported_biomarkers = {
        "NSCLC": {
            "PD-L1": "%",
            "EGFR": "variant",
            "ALK": "status",
            "KRAS": "variant",
            "TP53": "variant",
            "TMB": "mut/Mb",
            "MSI": "status",
            "MMR": "status",
        },
        "breast": {
            "HER2": "score",
            "ER": "%",
            "PR": "%",
            "PIK3CA": "variant",
            "BRCA1": "variant",
            "BRCA2": "variant",
            "PD-L1": "%",
            "TMB": "mut/Mb",
        },
        "colorectal": {"MSI": "status", "MMR": "status", "KRAS": "variant", "NRAS": "variant", "BRAF": "variant", "TMB": "mut/Mb"},
        "melanoma": {"BRAF": "variant", "NRAS": "variant", "KIT": "variant"},
        "prostate": {"AR": "status", "BRCA2": "variant", "MSI": "status", "MMR": "status", "TMB": "mut/Mb"},
        "ovarian": {"BRCA1": "variant", "BRCA2": "variant", "TP53": "variant", "CCNE1": "status", "HRD": "status"},
        "pancreatic": {
            "KRAS": "variant",
            "TP53": "variant",
            "CDKN2A": "status",
            "SMAD4": "status",
            "BRCA1": "variant",
            "BRCA2": "variant",
            "MSI": "status",
            "MMR": "status",
            "TMB": "mut/Mb",
        },
        "gastric": {"HER2": "score", "PD-L1": "%", "MSI": "status", "MMR": "status", "TP53": "variant", "EGFR": "variant", "TMB": "mut/Mb"},
        "endometrial": {"MSI": "status", "MMR": "status", "POLE": "variant", "PTEN": "status", "PD-L1": "%", "TMB": "mut/Mb"},
        "hcc": {"TP53": "variant", "CTNNB1": "variant", "AFP": "ng/mL", "PD-L1": "%"},
        "rcc": {"VHL": "variant", "PBRM1": "variant", "BAP1": "variant", "PD-L1": "%", "TMB": "mut/Mb"},
    }
    _supported_genetics = {
        "NSCLC": ["EGFR", "ALK", "KRAS", "ROS1", "MET", "RET", "BRAF", "ERBB2", "TP53"],
        "breast": ["BRCA1", "BRCA2", "PIK3CA", "ESR1", "ERBB2", "AKT1", "TP53"],
        "colorectal": ["KRAS", "NRAS", "BRAF", "PIK3CA", "TP53", "APC"],
        "melanoma": ["BRAF", "NRAS", "KIT", "NF1", "GNAQ", "GNA11"],
        "prostate": ["BRCA1", "BRCA2", "ATM", "PALB2", "CHEK2", "MSH2", "MSH6", "AR", "TP53"],
        "ovarian": ["BRCA1", "BRCA2", "TP53", "CCNE1", "PALB2"],
        "pancreatic": ["KRAS", "TP53", "CDKN2A", "SMAD4", "BRCA1", "BRCA2", "ATM", "PALB2"],
        "gastric": ["HER2", "PD-L1", "MSI", "TP53", "EGFR", "CDH1"],
        "endometrial": ["MSI", "MMR", "POLE", "PTEN", "PIK3CA", "TP53", "ARID1A"],
        "hcc": ["TP53", "CTNNB1", "TERT", "AXIN1"],
        "rcc": ["VHL", "PBRM1", "BAP1", "SETD2", "MTOR"],
    }
    _supported_genetic_variants = {
        "NSCLC": {
            "EGFR": [
                "Ex19del mutant",
                "L858R mutant",
                "T790M mutant",
                "Ex20ins mutant",
                "G719X mutant",
                "L861Q mutant",
                "S768I mutant",
                "WT",
            ],
            "ALK": ["EML4-ALK fusion", "ALK rearrangement", "WT"],
            "KRAS": [
                "G12C mutant",
                "G12D mutant",
                "G12V mutant",
                "G12A mutant",
                "G12S mutant",
                "G12R mutant",
                "Q61H mutant",
                "Q61L mutant",
                "Q61R mutant",
                "A146T mutant",
                "G13D mutant",
                "WT",
            ],
            "ROS1": ["ROS1 fusion", "WT"],
            "MET": ["MET exon14 skipping", "MET amplification", "WT"],
            "RET": ["RET fusion", "WT"],
            "BRAF": ["V600E mutant", "V600K mutant", "V600R mutant", "Non-V600 mutant", "WT"],
            "ERBB2": ["ERBB2 exon20 insertion", "ERBB2 amplification", "WT"],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
        },
        "breast": {
            "BRCA1": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "BRCA2": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "PIK3CA": ["H1047R mutant", "E545K mutant", "E542K mutant", "WT"],
            "ESR1": ["Y537S mutant", "D538G mutant", "WT"],
            "ERBB2": ["Amplified", "Activating mutant", "WT"],
            "AKT1": ["E17K mutant", "WT"],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
        },
        "colorectal": {
            "KRAS": [
                "G12C mutant",
                "G12D mutant",
                "G12V mutant",
                "G12A mutant",
                "G12S mutant",
                "G12R mutant",
                "Q61H mutant",
                "Q61L mutant",
                "Q61R mutant",
                "A146T mutant",
                "G13D mutant",
                "WT",
            ],
            "NRAS": ["Q61K mutant", "Q61R mutant", "G12D mutant", "WT"],
            "BRAF": ["V600E mutant", "V600K mutant", "V600R mutant", "Non-V600 mutant", "WT"],
            "PIK3CA": ["H1047R mutant", "E545K mutant", "E542K mutant", "WT"],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
            "APC": ["Truncating mutant", "Missense mutant", "WT"],
        },
        "melanoma": {
            "BRAF": ["V600E mutant", "V600K mutant", "V600R mutant", "Non-V600 mutant", "WT"],
            "NRAS": ["Q61R mutant", "Q61K mutant", "Q61L mutant", "WT"],
            "KIT": ["L576P mutant", "K642E mutant", "WT"],
            "NF1": ["Loss-of-function mutant", "WT"],
            "GNAQ": ["Q209L mutant", "Q209P mutant", "WT"],
            "GNA11": ["Q209L mutant", "Q209P mutant", "WT"],
        },
        "prostate": {
            "BRCA1": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "BRCA2": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "ATM": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "PALB2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "CHEK2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "MSH2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "MSH6": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "AR": ["Amplification", "T878A mutant", "L702H mutant", "WT"],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
        },
        "ovarian": {
            "BRCA1": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "BRCA2": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
            "CCNE1": ["Amplified", "Copy-number gain", "WT"],
            "PALB2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
        },
        "pancreatic": {
            "KRAS": [
                "G12C mutant",
                "G12D mutant",
                "G12V mutant",
                "G12A mutant",
                "G12S mutant",
                "G12R mutant",
                "Q61H mutant",
                "Q61L mutant",
                "Q61R mutant",
                "A146T mutant",
                "G13D mutant",
                "WT",
            ],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
            "CDKN2A": ["Loss-of-function mutant", "Homozygous deletion", "WT"],
            "SMAD4": ["Loss-of-function mutant", "Deletion", "WT"],
            "BRCA1": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "BRCA2": [
                "Pathogenic truncating variant",
                "Pathogenic missense variant",
                "Likely pathogenic variant",
                "Rearrangement",
                "WT",
            ],
            "ATM": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
            "PALB2": ["Pathogenic variant", "Likely pathogenic variant", "WT"],
        },
        "gastric": {
            "HER2": ["Amplified", "IHC 3+", "IHC 2+/ISH+", "WT"],
            "PD-L1": ["CPS >=1", "CPS >=5", "CPS >=10", "CPS >=50", "Negative"],
            "MSI": ["MSI-High", "MSI-Low", "MSS"],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
            "EGFR": ["Amplified", "G719X mutant", "L861Q mutant", "S768I mutant", "WT"],
            "CDH1": ["Loss-of-function mutant", "Truncating mutant", "WT"],
        },
        "endometrial": {
            "MSI": ["MSI-High", "MSI-Low", "MSS"],
            "MMR": ["dMMR", "pMMR"],
            "POLE": ["Pathogenic exonuclease-domain mutant", "Likely pathogenic mutant", "WT"],
            "PTEN": ["Loss-of-function mutant", "Truncating mutant", "WT"],
            "PIK3CA": ["H1047R mutant", "E545K mutant", "E542K mutant", "WT"],
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
            "ARID1A": ["Loss-of-function mutant", "Truncating mutant", "WT"],
        },
        "hcc": {
            "TP53": [
                "R175H mutant",
                "R248Q mutant",
                "R273H mutant",
                "Missense mutant",
                "Truncating mutant",
                "Frameshift mutant",
                "Splice-site mutant",
                "WT",
            ],
            "CTNNB1": ["S45 mutant", "D32 mutant", "WT"],
            "TERT": ["Promoter mutant", "WT"],
            "AXIN1": ["Loss-of-function mutant", "WT"],
        },
        "rcc": {
            "VHL": ["Loss-of-function mutant", "Truncating mutant", "WT"],
            "PBRM1": ["Loss-of-function mutant", "Truncating mutant", "WT"],
            "BAP1": ["Loss-of-function mutant", "Truncating mutant", "WT"],
            "SETD2": ["Loss-of-function mutant", "Truncating mutant", "WT"],
            "MTOR": ["Activating mutant", "WT"],
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
