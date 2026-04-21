from __future__ import annotations

import re

from app.models.ehr import PatientEHR
from app.models.evidence import GuidelineReference, PubMedArticle

# ---------------------------------------------------------------------------
# Adverse-event keyword patterns used to scan article abstracts/titles.
# ---------------------------------------------------------------------------
_AE_KEYWORDS = re.compile(
    r"\b("
    r"adverse|toxicity|toxic|side.effect|irAE|immune.related|pneumonitis|colitis|hepatitis"
    r"|neutropenia|thrombocytopenia|neuropathy|cardiotoxicity|nephrotoxicity|diarrhea"
    r"|grade\s*[3-5]|severe|fatal|mortality|death|discontinuation|dose.reduction|hospitali[sz]"
    r")\b",
    re.IGNORECASE,
)

_SEVERITY_KEYWORDS = re.compile(
    r"\b(grade\s*[3-5]|severe|fatal|life.threatening|hospitali[sz]|discontinu)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Treatment-class baseline offsets grounded in published toxicity profiles.
# Sources: CTCAE rates from pivotal trials and NCCN/ASCO/ESMO guidelines.
# ---------------------------------------------------------------------------
_CLASS_BASELINE: dict[str, float] = {
    "targeted": 0.5,        # Lower severe-AE rates vs chemo (FLAURA, ALEX, COMBI-d)
    "immunotherapy": 1.2,   # irAE rates 20-40%; unpredictable spectrum (KEYNOTE, CheckMate)
    "chemotherapy": 1.8,    # Myelosuppression, GI, neuropathy common; highest acute toxicity
    "multimodal": 1.5,      # Combined modalities accumulate toxicity risks
    "hormonal": 0.3,        # Generally well-tolerated; lower acute toxicity (STAMPEDE, MONARCH)
    "investigational": 0.8, # Uncertain profile; treat conservatively
    "systemic": 1.2,        # Generic systemic; moderate assumption
}

# ---------------------------------------------------------------------------
# Per-treatment adjustments from landmark trial toxicity data.
# Each entry: (risk_delta, rationale_string)
# ---------------------------------------------------------------------------
_TREATMENT_ADJUSTMENTS: dict[str, tuple[float, str]] = {
    # Targeted
    "osimertinib": (0.2, "Generally well-tolerated; grade 3-4 AE ~15% in FLAURA/ADAURA"),
    "alectinib": (0.1, "Favorable safety vs crizotinib in ALEX trial; grade 3-4 ~41%"),
    "dabrafenib + trametinib": (0.4, "Pyrexia ~40%, skin AEs common; COMBI-d/v data"),
    "parp inhibitor (brca-altered)": (0.6, "Anemia, nausea common; GI/heme toxicity in PROFOUND"),
    "cetuximab (ras wild-type)": (0.5, "Grade 3-4 skin rash, hypomagnesemia; CRYSTAL/FIRE-3"),
    "endocrine therapy + cdk4/6 inhibitor": (0.5, "Neutropenia manageable; PALOMA-2/MONALEESA data"),
    # Immunotherapy
    "nivolumab + ipilimumab": (1.5, "Dual checkpoint: grade 3-4 irAE ~59% in CheckMate-067"),
    "pembrolizumab + platinum doublet": (0.9, "Chemo-IO: grade 3-4 ~67% in KEYNOTE-189"),
    "pembrolizumab": (0.5, "Single-agent: grade 3-4 irAE ~15-20% across KEYNOTE trials"),
    "relatlimab + nivolumab": (0.8, "LAG-3/PD-1 combo; grade 3-4 ~19% in RELATIVITY-047"),
    # Chemotherapy
    "folfox": (0.6, "Peripheral neuropathy 30-40%, myelosuppression; MOSAIC/OPTIMOX"),
    "folfiri + bevacizumab": (0.9, "Hypertension, bleeding added to FOLFIRI AEs; FIRE-3"),
    "docetaxel + ramucirumab": (1.4, "Compounded neutropenia, hypertension; REVEL grade 3-4 ~79%"),
    "docetaxel": (1.2, "Febrile neutropenia ~12%, fatigue, neuropathy; TAX 326"),
    "capecitabine": (0.4, "Hand-foot syndrome, diarrhea; generally manageable; XELODA data"),
    # Hormonal
    "abiraterone + prednisone": (0.3, "Fluid retention, hypertension; adrenal risk; COU-AA"),
    "androgen deprivation therapy + arpi": (0.4, "Metabolic, cardiovascular, bone effects; LATITUDE/TITAN"),
    # Combination targeted+chemo
    "trastuzumab + pertuzumab + taxane": (0.8, "Cardiac monitoring required; diarrhea ~67%; CLEOPATRA"),
    "sacituzumab govitecan": (0.9, "Severe neutropenia 51%, diarrhea 10%; ASCENT trial"),
}


def _detect_drug_class(treatment_name: str, drug_class: str) -> str:
    """Normalise to one of the keys in _CLASS_BASELINE."""
    if drug_class and drug_class in _CLASS_BASELINE:
        return drug_class
    lowered = treatment_name.lower()
    if any(kw in lowered for kw in ("pembrolizumab", "nivolumab", "ipilimumab",
                                     "atezolizumab", "durvalumab", "relatlimab")):
        return "immunotherapy"
    if any(kw in lowered for kw in ("docetaxel", "cisplatin", "carboplatin", "folfox", "folfiri",
                                     "capecitabine", "chemotherapy", "cytotoxic", "taxane")):
        return "chemotherapy"
    if any(kw in lowered for kw in ("osimertinib", "alectinib", "dabrafenib", "erlotinib",
                                     "gefitinib", "crizotinib", "parp", "trastuzumab",
                                     "cetuximab", "sacituzumab", "targeted")):
        return "targeted"
    if any(kw in lowered for kw in ("abiraterone", "enzalutamide", "hormonal", "arpi",
                                     "endocrine", "androgen", "cdk4", "letrozole",
                                     "fulvestrant")):
        return "hormonal"
    if "investigational" in lowered or "clinical trial" in lowered:
        return "investigational"
    return drug_class or "systemic"


def _evidence_adverse_signal(
    treatment_name: str,
    articles: list[PubMedArticle],
) -> tuple[float, list[str]]:
    """
    Scan PubMed article titles/abstracts for adverse-event mentions co-occurring
    with the treatment. Returns (score_delta, factor_strings).

    Scoring thresholds:
    - ae_hits >= 3 with severity keywords: +0.6 (strong evidence of grade 3-5 toxicity)
    - ae_hits >= 3 without severity keywords: +0.3 (moderate adverse event signals)
    - ae_hits >= 1 (mild signal): +0.15 (some AE mentions, low concern)
    - Delta is capped at 2.0 across all articles to avoid excessive compounding.
    """
    treatment_tokens = {t for t in re.findall(r"\w+", treatment_name.lower()) if len(t) > 3}
    treatment_tokens -= {"with", "plus", "therapy", "based", "combination"}

    evidence_delta = 0.0
    matched_pmids: list[str] = []
    severe_pmids: list[str] = []

    for article in articles:
        content = " ".join(filter(None, [article.title, article.abstract or ""]))
        content_lower = content.lower()

        token_hits = sum(1 for t in treatment_tokens if t in content_lower)
        if token_hits == 0:
            continue

        ae_hits = len(_AE_KEYWORDS.findall(content))
        severity_hits = len(_SEVERITY_KEYWORDS.findall(content))

        if ae_hits >= 3:
            delta = 0.6 if severity_hits >= 1 else 0.3
            evidence_delta += delta
            matched_pmids.append(article.pmid)
            if severity_hits >= 1:
                severe_pmids.append(article.pmid)
        elif ae_hits >= 1:
            evidence_delta += 0.15
            matched_pmids.append(article.pmid)

    factors: list[str] = []
    if severe_pmids:
        factors.append(
            f"Published evidence reports grade 3-4 toxicity for this therapy"
            f" (PMIDs: {', '.join(severe_pmids[:3])})"
        )
    elif matched_pmids:
        factors.append(
            f"Retrieved literature contains adverse-event mentions for this therapy"
            f" (PMIDs: {', '.join(matched_pmids[:3])})"
        )

    return round(min(2.0, evidence_delta), 2), factors


def _apply_interaction_score(
    patient: PatientEHR,
    treatment_name: str,
    resolved_class: str,
    score: float,
    factors: list[str],
) -> float:
    """
    Apply patient-treatment interaction adjustments.
    Mutates factors list in-place; returns updated score.
    """
    lowered = treatment_name.lower()

    # --- Immunotherapy interactions ---
    if resolved_class == "immunotherapy":
        if any("autoimmune" in c.lower() for c in patient.comorbidities):
            score += 1.0
            factors.append("Active autoimmune condition: increased irAE risk with checkpoint inhibition")
        if any("transplant" in c.lower() for c in patient.comorbidities):
            score += 1.5
            factors.append("Organ transplant history: high risk of graft rejection with checkpoint inhibitors")
        if any("ibd" in c.lower() or "colitis" in c.lower() or "crohn" in c.lower()
               for c in patient.comorbidities):
            score += 0.8
            factors.append("Inflammatory bowel disease: elevated immune-related colitis risk")
        if patient.age >= 75:
            score += 0.4
            factors.append("Advanced age increases severity of immune-related adverse events")

    # --- Chemotherapy interactions ---
    if resolved_class == "chemotherapy":
        if patient.organ_function and patient.organ_function.renal == "poor":
            if any(kw in lowered for kw in ("cisplatin", "carboplatin", "platinum")):
                score += 1.5
                factors.append("Renal impairment: platinum compound nephrotoxicity risk is high")
            else:
                score += 0.5
                factors.append("Renal impairment: reduced clearance may potentiate chemotherapy exposure")
        if patient.organ_function and patient.organ_function.hepatic == "poor":
            if any(kw in lowered for kw in ("docetaxel", "paclitaxel", "taxane")):
                score += 1.3
                factors.append("Hepatic impairment: taxane clearance impaired; elevated AUC and toxicity")
            else:
                score += 0.6
                factors.append("Hepatic impairment: reduced chemotherapy metabolism increases toxicity risk")
        if patient.organ_function and patient.organ_function.cardiac == "poor":
            if any(kw in lowered for kw in ("doxorubicin", "anthracycline", "epirubicin")):
                score += 1.4
                factors.append("Cardiac dysfunction: anthracycline cardiotoxicity risk is substantially elevated")
        if patient.ecog >= 2:
            score += 0.5
            factors.append("Reduced performance status limits chemotherapy tolerability")

    # --- Targeted therapy interactions ---
    if resolved_class == "targeted":
        if organ_function_poor_any(patient):
            score += 0.4
            factors.append("Organ dysfunction may impair targeted agent metabolism/clearance")
        # Biomarker match bonus (reduces risk when treatment aligns with biomarker)
        biomarker_names = {b.name.upper() for b in patient.biomarkers}
        genetics_muts = {g.mutation.upper() for g in patient.genetics}
        if "osimertinib" in lowered or "egfr" in lowered:
            if "EGFR" in biomarker_names or "EGFR" in genetics_muts:
                score -= 0.5
                factors.append("EGFR biomarker match: treatment is precisely indicated — lowers relative risk")
        if "alectinib" in lowered or "alk" in lowered:
            if "ALK" in biomarker_names or "ALK" in genetics_muts:
                score -= 0.4
                factors.append("ALK rearrangement confirmed: alectinib is first-line indicated")
        if "trastuzumab" in lowered or "her2" in lowered:
            if "HER2" in biomarker_names:
                score -= 0.4
                factors.append("HER2-positive status: trastuzumab-based therapy is guideline-indicated")
        if ("parp" in lowered or "brca" in lowered) and (
            "BRCA1" in biomarker_names or "BRCA2" in biomarker_names
            or "BRCA2" in genetics_muts or "BRCA1" in genetics_muts
        ):
            score -= 0.4
            factors.append("BRCA alteration confirmed: PARP inhibitor is precisely indicated")

    # --- Hormonal therapy interactions ---
    if resolved_class == "hormonal":
        if any("cardiovascular" in c.lower() or "heart" in c.lower() or "hypertension" in c.lower()
               for c in patient.comorbidities):
            score += 0.4
            factors.append("Cardiovascular comorbidity: ADT/ARPI metabolic effects increase cardiac risk")
        if any("osteoporosis" in c.lower() or "fracture" in c.lower() for c in patient.comorbidities):
            score += 0.3
            factors.append("Bone fragility: hormonal therapy accelerates bone loss risk")

    # --- Prior treatment interactions ---
    if patient.prior_treatments:
        prior_lower = [t.lower() for t in patient.prior_treatments]
        if resolved_class == "chemotherapy" and any("chemo" in t or "platin" in t for t in prior_lower):
            score += 0.4
            factors.append("Prior chemotherapy: cumulative toxicity and reduced marrow reserve")
        if resolved_class == "immunotherapy" and any("immuno" in t or "pembrolizumab" in t
                                                       or "nivolumab" in t for t in prior_lower):
            score += 0.5
            factors.append("Prior immunotherapy: re-challenge increases risk of severe irAE recurrence")
        if patient.progression:
            score += 0.3
            factors.append("Active disease progression: systemic burden raises treatment risk")

    return score


def organ_function_poor_any(patient: PatientEHR) -> bool:
    if not patient.organ_function:
        return False
    return any(
        v == "poor"
        for v in (
            patient.organ_function.renal,
            patient.organ_function.hepatic,
            patient.organ_function.cardiac,
        )
        if v is not None
    )


class RiskAnalysisService:
    def score(
        self,
        patient: PatientEHR,
        treatment_name: str,
        drug_class: str = "",
        articles: list[PubMedArticle] | None = None,
        guidelines: list[GuidelineReference] | None = None,
    ) -> tuple[float, tuple[float, float], list[str]]:
        """
        Return (risk_score, confidence_interval, risk_factors).

        Scoring layers:
        1. Patient-level factors (age, ECOG, stage, metastases, comorbidities)
        2. Treatment-class baseline offset (immunotherapy / chemo / targeted / hormonal)
        3. Per-treatment landmark-trial toxicity adjustment
        4. Patient-treatment interaction checks (organ function, biomarkers/genetics, prior tx)
        5. Evidence-signal scan from retrieved PubMed articles (real patient experience)
        """
        articles = articles or []
        score = 1.5
        factors: list[str] = []

        # --- Layer 1: patient factors ---
        if patient.age >= 75:
            score += 1.5
            factors.append("Advanced age (≥75): increased vulnerability to most therapies")
        elif patient.age >= 65:
            score += 0.8
            factors.append("Older age (65–74): moderate age-related risk increment")

        if patient.ecog >= 3:
            score += 2.2
            factors.append("Poor ECOG performance status (≥3): limits treatment tolerance")
        elif patient.ecog == 2:
            score += 1.0
            factors.append("Intermediate ECOG performance status (2)")

        if patient.stage.value == "IV":
            score += 1.8
            factors.append("Metastatic stage IV disease: complex management, higher overall risk")
        elif patient.stage.value == "III":
            score += 0.9
            factors.append("Locally advanced disease (stage III)")

        if patient.metastases:
            score += min(1.5, 0.4 * len(patient.metastases))
            sites = ", ".join(patient.metastases[:3])
            factors.append(f"Metastatic burden ({len(patient.metastases)} site(s): {sites})")

        if patient.comorbidities:
            score += min(1.2, 0.25 * len(patient.comorbidities))
            conds = ", ".join(patient.comorbidities[:3])
            factors.append(f"Comorbidities ({len(patient.comorbidities)}: {conds})")

        # --- Layer 2: treatment-class baseline ---
        resolved_class = _detect_drug_class(treatment_name, drug_class)
        class_offset = _CLASS_BASELINE.get(resolved_class, 1.2)
        score += class_offset
        factors.append(
            f"{resolved_class.title()} class: published AE profile offset {class_offset:+.1f}"
        )

        # --- Layer 3: per-treatment landmark adjustment ---
        lowered_tx = treatment_name.lower()
        for tx_key, (adj, rationale) in _TREATMENT_ADJUSTMENTS.items():
            if tx_key in lowered_tx:
                score += adj
                factors.append(rationale)
                break

        # --- Layer 4: patient-treatment interactions ---
        score = _apply_interaction_score(patient, treatment_name, resolved_class, score, factors)

        # --- Layer 5: evidence signal from PubMed articles ---
        evidence_delta, evidence_factors = _evidence_adverse_signal(treatment_name, articles)
        score += evidence_delta
        factors.extend(evidence_factors)

        # CI: wider when evidence base is sparse for this treatment
        # _CI_HALF_* constants reflect decreasing uncertainty as evidence volume grows.
        _CI_HALF_NO_EVIDENCE = 1.2    # No relevant articles retrieved — highest uncertainty
        _CI_HALF_FEW_ARTICLES = 0.9   # 1-2 relevant articles — moderate uncertainty
        _CI_HALF_ADEQUATE = 0.6       # 3+ relevant articles — lower uncertainty
        relevant_article_count = sum(
            1 for a in articles
            if any(
                t in (a.title or "").lower() or t in (a.abstract or "").lower()
                for t in re.findall(r"\w+", lowered_tx)
                if len(t) > 4
            )
        )
        if relevant_article_count == 0:
            ci_half = _CI_HALF_NO_EVIDENCE
        elif relevant_article_count <= 2:
            ci_half = _CI_HALF_FEW_ARTICLES
        else:
            ci_half = _CI_HALF_ADEQUATE

        bounded = round(max(1.0, min(10.0, score)), 1)
        ci = (
            round(max(1.0, bounded - ci_half), 1),
            round(min(10.0, bounded + ci_half), 1),
        )
        return bounded, ci, factors

    def identify_contraindications(
        self,
        patient: PatientEHR,
        treatment_name: str,
        drug_class: str = "",
    ) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        lowered = treatment_name.lower()
        resolved_class = _detect_drug_class(treatment_name, drug_class)

        # Renal function
        if patient.organ_function and patient.organ_function.renal == "poor":
            if any(kw in lowered for kw in ("cisplatin", "carboplatin", "platinum")):
                issues.append({"risk": "Platinum nephrotoxicity in setting of poor renal function", "severity": "high"})
            elif resolved_class == "chemotherapy":
                issues.append({"risk": "Reduced renal clearance may potentiate chemotherapy toxicity", "severity": "moderate"})

        # Hepatic function
        if patient.organ_function and patient.organ_function.hepatic == "poor":
            if any(kw in lowered for kw in ("docetaxel", "paclitaxel", "taxane")):
                issues.append({"risk": "Hepatic impairment increases taxane exposure and toxicity risk", "severity": "high"})
            elif resolved_class in ("targeted", "chemotherapy"):
                issues.append({"risk": "Hepatic impairment may impair drug metabolism and increase toxicity", "severity": "moderate"})

        # Cardiac function
        if patient.organ_function and patient.organ_function.cardiac == "poor":
            if any(kw in lowered for kw in ("doxorubicin", "anthracycline", "epirubicin", "trastuzumab")):
                issues.append({"risk": "Significant cardiotoxicity risk with cardiac dysfunction", "severity": "high"})

        # Immunotherapy-specific
        if resolved_class == "immunotherapy":
            if any("transplant" in c.lower() for c in patient.comorbidities):
                issues.append({"risk": "Checkpoint inhibition carries high risk of allograft rejection", "severity": "high"})
            if any("autoimmune" in c.lower() for c in patient.comorbidities):
                issues.append({"risk": "Autoimmune condition: risk of flare and severe irAE", "severity": "high"})

        return issues
