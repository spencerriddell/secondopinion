export type Biomarker = { name: string; value: string; unit?: string };
export type Genetics = { mutation: string; status: string };

export type PatientEHR = {
  patient_id?: string;
  cancer_type: string;
  stage: string;
  biomarkers: Biomarker[];
  genetics: Genetics[];
  age: number;
  ecog: number;
  comorbidities: string[];
  concurrent_medications: string[];
  metastases: string[];
  progression: boolean;
  prior_treatments: string[];
  organ_function?: { renal?: string; hepatic?: string; cardiac?: string };
};

export type Recommendation = {
  recommendation_id: string;
  patient_id: string;
  treatment: { name: string; mechanism: string; drug_class: string };
  indication: { clinical_rationale: string };
  contraindication: { risk: string; severity: string }[];
  risk_score: number;
  risk_base_score?: number;
  risk_confidence_interval: [number, number];
  risk_factors: string[];
  risk_factor_breakdown?: {
    layer: number;
    layer_name: string;
    factor: string;
    contribution: number;
    impact_type: string;
  }[];
  efficacy_evidence: { trial_name: string; pmid?: string }[];
  citations: { pmid: string; doi?: string; title: string; authors: string[]; formatted?: string }[];
  explanation: string;
};

export type RecommendationResponse = {
  patient_id: string;
  recommendations: Recommendation[];
};
