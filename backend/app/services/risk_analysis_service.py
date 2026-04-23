from __future__ import annotations

from datetime import UTC, datetime
import re

from app.models.ehr import PatientEHR
from app.models.evidence import GuidelineReference, PubMedArticle
from app.models.pmc import PMCArticle

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
    r"\b(grade\s*[3-5]|severe|fatal|life[-\s]?threatening|hospitali[sz]|discontinu)\b",
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

_BASE_SCORE = 1.5
_LAYER_LABELS: dict[int, str] = {
    1: "Patient",
    2: "Treatment class",
    3: "Drug-specific",
    4: "Interactions",
    5: "Evidence",
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
    breakdown: list[dict[str, int | float | str]] | None = None,
) -> float:
    """
    Apply patient-treatment interaction adjustments.
    Mutates factors list in-place; returns updated score.
    """
    lowered = treatment_name.lower()

    def add(delta: float, factor: str) -> None:
        nonlocal score
        score += delta
        factors.append(factor)
        if breakdown is not None:
            breakdown.append(
                {
                    "layer": 4,
                    "layer_name": _LAYER_LABELS[4],
                    "factor": factor,
                    "contribution": round(delta, 2),
                    "impact_type": "risk-mitigating" if delta < 0 else "risk-elevating",
                }
            )

    # --- Immunotherapy interactions ---
    if resolved_class == "immunotherapy":
        if any("autoimmune" in c.lower() for c in patient.comorbidities):
            add(1.0, "Active autoimmune condition: increased irAE risk with checkpoint inhibition")
        if any("transplant" in c.lower() for c in patient.comorbidities):
            add(1.5, "Organ transplant history: high risk of graft rejection with checkpoint inhibitors")
        if any("ibd" in c.lower() or "colitis" in c.lower() or "crohn" in c.lower()
               for c in patient.comorbidities):
            add(0.8, "Inflammatory bowel disease: elevated immune-related colitis risk")
        if patient.age >= 75:
            add(0.4, "Advanced age increases severity of immune-related adverse events")

    # --- Chemotherapy interactions ---
    if resolved_class == "chemotherapy":
        if patient.organ_function and patient.organ_function.renal == "poor":
            if any(kw in lowered for kw in ("cisplatin", "carboplatin", "platinum")):
                add(1.5, "Renal impairment: platinum compound nephrotoxicity risk is high")
            else:
                add(0.5, "Renal impairment: reduced clearance may potentiate chemotherapy exposure")
        if patient.organ_function and patient.organ_function.hepatic == "poor":
            if any(kw in lowered for kw in ("docetaxel", "paclitaxel", "taxane")):
                add(1.3, "Hepatic impairment: taxane clearance impaired; elevated AUC and toxicity")
            else:
                add(0.6, "Hepatic impairment: reduced chemotherapy metabolism increases toxicity risk")
        if patient.organ_function and patient.organ_function.cardiac == "poor":
            if any(kw in lowered for kw in ("doxorubicin", "anthracycline", "epirubicin")):
                add(1.4, "Cardiac dysfunction: anthracycline cardiotoxicity risk is substantially elevated")
        if patient.ecog >= 2:
            add(0.5, "ECOG ≥2: higher grade 3-4 toxicity and early discontinuation risk with chemotherapy")

    # --- Targeted therapy interactions ---
    if resolved_class == "targeted":
        if organ_function_poor_any(patient):
            add(0.4, "Organ dysfunction may impair targeted agent metabolism/clearance")
        # Biomarker match bonus (reduces risk when treatment aligns with biomarker)
        biomarker_names = {b.name.upper() for b in patient.biomarkers}
        genetics_muts = {g.mutation.upper() for g in patient.genetics}
        if "osimertinib" in lowered or "egfr" in lowered:
            if "EGFR" in biomarker_names or "EGFR" in genetics_muts:
                add(-0.5, "EGFR biomarker match: treatment is precisely indicated — lowers relative risk")
        if "alectinib" in lowered or "alk" in lowered:
            if "ALK" in biomarker_names or "ALK" in genetics_muts:
                add(-0.4, "ALK rearrangement confirmed: alectinib is first-line indicated")
        if "trastuzumab" in lowered or "her2" in lowered:
            if "HER2" in biomarker_names:
                add(-0.4, "HER2-positive status: trastuzumab-based therapy is guideline-indicated")
        if ("parp" in lowered or "brca" in lowered) and (
            "BRCA1" in biomarker_names or "BRCA2" in biomarker_names
            or "BRCA2" in genetics_muts or "BRCA1" in genetics_muts
        ):
            add(-0.4, "BRCA alteration confirmed: PARP inhibitor is precisely indicated")

    # --- Hormonal therapy interactions ---
    if resolved_class == "hormonal":
        if any("cardiovascular" in c.lower() or "heart" in c.lower() or "hypertension" in c.lower()
               for c in patient.comorbidities):
            add(0.4, "Cardiovascular comorbidity: ADT/ARPI metabolic effects increase cardiac risk")
        if any("osteoporosis" in c.lower() or "fracture" in c.lower() for c in patient.comorbidities):
            add(0.3, "Bone fragility: hormonal therapy accelerates bone loss risk")

    # --- Prior treatment interactions ---
    if patient.prior_treatments:
        prior_lower = [t.lower() for t in patient.prior_treatments]
        if resolved_class == "chemotherapy" and any("chemo" in t or "platin" in t for t in prior_lower):
            add(0.4, "Prior chemotherapy: cumulative toxicity and reduced marrow reserve")
        if resolved_class == "immunotherapy" and any("immuno" in t or "pembrolizumab" in t
                                                       or "nivolumab" in t for t in prior_lower):
            add(0.5, "Prior immunotherapy: re-challenge increases risk of severe irAE recurrence")
        if patient.progression:
            add(0.3, "Active disease progression: systemic burden raises treatment risk")

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
    _SEVERITY_RANK_PATTERNS: list[tuple[int, re.Pattern[str]]] = [
        (4, re.compile(r"\b(grade\s*5|fatal|death|mortality)\b", re.IGNORECASE)),
        (3, _SEVERITY_KEYWORDS),
        (2, re.compile(r"\b(grade\s*[1-2]|mild|moderate)\b", re.IGNORECASE)),
    ]

    def _rank_risk_factors(self, patient: PatientEHR, factors: list[str]) -> list[str]:
        def _patient_relevance(text: str) -> int:
            lowered = text.lower()
            relevance = 0
            if str(patient.age) in lowered or "age" in lowered:
                relevance += 1
            if "ecog" in lowered:
                relevance += 1
            if patient.stage.value.lower() in lowered:
                relevance += 1
            if any(c.lower() in lowered for c in patient.comorbidities):
                relevance += 1
            if patient.organ_function and any(
                f"{organ}" in lowered and getattr(patient.organ_function, organ) == "poor"
                for organ in ("renal", "hepatic", "cardiac")
            ):
                relevance += 1
            return relevance

        def _severity_rank(text: str) -> int:
            for rank, pattern in self._SEVERITY_RANK_PATTERNS:
                if pattern.search(text):
                    return rank
            return 1

        scored = [(_severity_rank(f), _patient_relevance(f), idx, f) for idx, f in enumerate(factors)]
        # Use original order as a stable tiebreaker when severity/relevance are equal.
        scored.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
        return [item[3] for item in scored]

    def rank_risk_factors(self, patient: PatientEHR, factors: list[str]) -> list[str]:
        return self._rank_risk_factors(patient, factors)

    def score(
        self,
        patient: PatientEHR,
        treatment_name: str,
        drug_class: str = "",
        articles: list[PubMedArticle] | None = None,
        guidelines: list[GuidelineReference] | None = None,
    ) -> tuple[float, tuple[float, float], list[str]]:
        score, ci, factors, _ = self.score_with_breakdown(
            patient=patient,
            treatment_name=treatment_name,
            drug_class=drug_class,
            articles=articles,
            guidelines=guidelines,
        )
        return score, ci, factors

    def score_with_breakdown(
        self,
        patient: PatientEHR,
        treatment_name: str,
        drug_class: str = "",
        articles: list[PubMedArticle] | None = None,
        guidelines: list[GuidelineReference] | None = None,
    ) -> tuple[float, tuple[float, float], list[str], list[dict[str, int | float | str]]]:
        """
        Return (risk_score, confidence_interval, risk_factors).

        Scoring layers:
        1. Patient-level factors (age, ECOG, stage, metastases, comorbidities)
        2. Treatment-class baseline offset (immunotherapy / chemo / targeted / hormonal)
        3. Per-treatment landmark-trial toxicity adjustment
        4. Patient-treatment interaction checks (organ function, biomarkers/genetics, prior tx)
        5. Evidence-signal scan from retrieved PubMed articles (real patient experience)
        """
        del guidelines
        articles = articles or []
        score = _BASE_SCORE
        factors: list[str] = []
        breakdown: list[dict[str, int | float | str]] = []

        def add(layer: int, delta: float, factor: str, impact_type: str | None = None) -> None:
            nonlocal score
            score += delta
            factors.append(factor)
            inferred_impact = impact_type
            if inferred_impact is None:
                inferred_impact = "risk-mitigating" if delta < 0 else "risk-elevating"
            breakdown.append(
                {
                    "layer": layer,
                    "layer_name": _LAYER_LABELS[layer],
                    "factor": factor,
                    "contribution": round(delta, 2),
                    "impact_type": inferred_impact,
                }
            )

        # --- Layer 1: patient factors ---
        if patient.age >= 75:
            add(1, 1.5, "Advanced age (≥75): increased vulnerability to most therapies")
        elif patient.age >= 65:
            add(1, 0.8, "Older age (65–74): moderate age-related risk increment")

        if patient.ecog >= 3:
            add(1, 2.2, "Poor ECOG performance status (≥3): limits treatment tolerance")
        elif patient.ecog == 2:
            add(1, 1.0, "Intermediate ECOG performance status (2)")

        if patient.stage.value == "IV":
            add(1, 1.8, "Metastatic stage IV disease: complex management, higher overall risk")
        elif patient.stage.value == "III":
            add(1, 0.9, "Locally advanced disease (stage III)")

        if patient.metastases:
            delta = min(1.5, 0.4 * len(patient.metastases))
            sites = ", ".join(patient.metastases[:3])
            add(1, delta, f"Metastatic burden ({len(patient.metastases)} site(s): {sites})")

        if patient.comorbidities:
            delta = min(1.2, 0.25 * len(patient.comorbidities))
            conds = ", ".join(patient.comorbidities[:3])
            add(1, delta, f"Comorbidities ({len(patient.comorbidities)}: {conds})")

        # --- Layer 2: treatment-class baseline ---
        resolved_class = _detect_drug_class(treatment_name, drug_class)
        class_offset = _CLASS_BASELINE.get(resolved_class, 1.2)
        add(
            2,
            class_offset,
            f"{resolved_class.title()} class: published AE profile offset {class_offset:+.1f}",
        )

        # --- Layer 3: per-treatment landmark adjustment ---
        lowered_tx = treatment_name.lower()
        for tx_key, (adj, rationale) in _TREATMENT_ADJUSTMENTS.items():
            if tx_key in lowered_tx:
                add(3, adj, rationale)
                break

        # --- Layer 4: patient-treatment interactions ---
        score = _apply_interaction_score(
            patient, treatment_name, resolved_class, score, factors, breakdown=breakdown
        )

        # --- Layer 5: evidence signal from PubMed articles ---
        evidence_delta, evidence_factors = _evidence_adverse_signal(treatment_name, articles)
        score += evidence_delta
        factors.extend(evidence_factors)
        if evidence_delta and evidence_factors:
            breakdown.append(
                {
                    "layer": 5,
                    "layer_name": _LAYER_LABELS[5],
                    "factor": evidence_factors[0],
                    "contribution": round(evidence_delta, 2),
                    "impact_type": "evidence-based",
                }
            )

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
        ranked_factors = self._rank_risk_factors(patient, factors)
        return bounded, ci, ranked_factors, breakdown

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


class RiskArticleFilter:
    def __init__(self, recent_year_window: int = 5) -> None:
        self.recent_year_window = recent_year_window
        self.current_year = datetime.now(UTC).year

    @staticmethod
    def _treatment_tokens(treatment_name: str) -> set[str]:
        tokens = {t for t in re.findall(r"\w+", treatment_name.lower()) if len(t) > 3}
        return tokens - {"with", "plus", "therapy", "based", "combination"}

    @staticmethod
    def _article_text(article: PubMedArticle) -> str:
        parts = [article.title, article.abstract or "", " ".join(article.mesh_terms or [])]
        return " ".join(parts).lower()

    def score_article(self, patient: PatientEHR, treatment_name: str, article: PubMedArticle) -> float:
        text = self._article_text(article)
        score = 0.0
        tx_tokens = self._treatment_tokens(treatment_name)
        token_hits = sum(1 for t in tx_tokens if t in text)
        score += min(2.5, 0.7 * token_hits)

        ae_hits = len(_AE_KEYWORDS.findall(text))
        score += min(2.0, 0.4 * ae_hits)

        age_range_matches = re.findall(r"(\d{2})\s*[-–]\s*(\d{2})\s*(?:years?|yrs?)", text)
        for lo, hi in age_range_matches:
            low, high = int(lo), int(hi)
            if low - 10 <= patient.age <= high + 10:
                score += 1.6
                break
        else:
            age_matches = re.findall(r"(?:median|mean)\s+age\s*(?:of|=|:)?\s*(\d{2})", text)
            if any(abs(int(v) - patient.age) <= 10 for v in age_matches):
                score += 1.3

        if "ecog" in text and str(patient.ecog) in text:
            score += 1.0
        if f"stage {patient.stage.value.lower()}" in text:
            score += 0.8
        if any(c.lower() in text for c in patient.comorbidities):
            score += 0.8

        if article.year and article.year >= (self.current_year - self.recent_year_window) and ae_hits > 0:
            score += 0.6

        if re.search(r"\b(mechanism|pathway|in vitro|preclinical|murine|xenograft)\b", text) and ae_hits == 0:
            score -= 0.8
        return score

    def rank_articles(
        self,
        patient: PatientEHR,
        treatment_name: str,
        articles: list[PubMedArticle],
    ) -> list[PubMedArticle]:
        return sorted(
            articles,
            key=lambda article: self.score_article(patient, treatment_name, article),
            reverse=True,
        )


class PMCAEParser:
    _PERCENT_PATTERN = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
    _DISCONT_PATTERN = re.compile(
        r"(?:discontinu(?:ation|ed)[^.%]{0,60}?(\d{1,2}(?:\.\d+)?)\s*%)",
        re.IGNORECASE,
    )
    _SAE_PATTERN = re.compile(
        r"(?:serious adverse event[s]?|sae[s]?)[^.%]{0,60}?(\d{1,2}(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    )

    def parse(self, article: PMCArticle) -> dict[str, object] | None:
        text = " ".join(
            filter(
                None,
                [article.abstract or "", article.methodology or "", article.results or "", article.conclusions or ""],
            )
        )
        if not text:
            return None
        lowered = text.lower()

        grade_events: list[str] = []
        subgroup_signals: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence_lower = sentence.lower()
            if not sentence_lower:
                continue
            if re.search(r"\b(grade\s*[3-5])\b", sentence_lower) and (
                "neutropenia" in sentence_lower
                or "pneumonitis" in sentence_lower
                or "diarrhea" in sentence_lower
                or "toxicity" in sentence_lower
                or "adverse" in sentence_lower
            ):
                grade_events.append(sentence.strip())
            if (
                "ecog" in sentence_lower
                or "elderly" in sentence_lower
                or "renal" in sentence_lower
                or "hepatic" in sentence_lower
                or "prior" in sentence_lower
                or "comorbid" in sentence_lower
            ) and self._PERCENT_PATTERN.search(sentence_lower):
                subgroup_signals.append(sentence.strip())

        discontinuation_match = self._DISCONT_PATTERN.search(lowered)
        sae_match = self._SAE_PATTERN.search(lowered)
        discontinuation_rate = float(discontinuation_match.group(1)) if discontinuation_match else None
        sae_rate = float(sae_match.group(1)) if sae_match else None
        if discontinuation_rate is not None and discontinuation_rate > 100:
            discontinuation_rate = None
        if sae_rate is not None and sae_rate > 100:
            sae_rate = None
        payload = {
            "pmc_id": article.pmc_id,
            "title": article.title,
            "grade3_4_events": grade_events[:5],
            "discontinuation_rate": discontinuation_rate,
            "sae_rate": sae_rate,
            "subgroup_signals": subgroup_signals[:4],
        }
        if not payload["grade3_4_events"] and payload["discontinuation_rate"] is None and payload["sae_rate"] is None:
            return None
        return payload

    def parse_many(self, pmc_articles: list[PMCArticle]) -> list[dict[str, object]]:
        parsed: list[dict[str, object]] = []
        for article in pmc_articles:
            row = self.parse(article)
            if row:
                parsed.append(row)
        return parsed
