type BreakdownItem = {
  layer: number;
  layer_name: string;
  factor: string;
  contribution: number;
  impact_type: string;
};

type Props = {
  score: number;
  baseScore?: number;
  ci?: [number, number];
  details?: string[];
  breakdown?: BreakdownItem[];
};

function riskColor(score: number): string {
  if (score <= 3) return "border-emerald-300 bg-emerald-50 text-emerald-900";
  if (score <= 6) return "border-amber-300 bg-amber-50 text-amber-900";
  if (score <= 8) return "border-orange-300 bg-orange-50 text-orange-900";
  return "border-rose-300 bg-rose-50 text-rose-900";
}

function scoreBarColor(score: number): string {
  if (score <= 3) return "bg-emerald-500";
  if (score <= 6) return "bg-amber-500";
  if (score <= 8) return "bg-orange-500";
  return "bg-rose-600";
}

function interpretation(score: number): string {
  if (score <= 3) return "Lower risk";
  if (score <= 6) return "Moderate risk";
  if (score <= 8) return "High risk";
  return "Very high risk";
}

function chipColor(impactType: string): string {
  if (impactType === "risk-mitigating") return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (impactType === "evidence-based") return "bg-sky-100 text-sky-800 border-sky-200";
  return "bg-rose-100 text-rose-800 border-rose-200";
}

function normalizeFallback(details: string[]): BreakdownItem[] {
  return details.map((factor) => {
    const lower = factor.toLowerCase();
    const evidenceBased = lower.includes("evidence") || lower.includes("trial") || lower.includes("pmid");
    const mitigating = lower.includes("indicated") || lower.includes("match") || lower.includes("lowers");
    const impactType = evidenceBased ? "evidence-based" : (mitigating ? "risk-mitigating" : "risk-elevating");
    return {
      layer: evidenceBased ? 5 : 1,
      layer_name: evidenceBased ? "Evidence" : "Patient",
      factor,
      contribution: 0,
      impact_type: impactType,
    };
  });
}

const MAX_FACTOR_DISPLAY_LENGTH = 70;
const TRUNCATED_FACTOR_LENGTH = 67;

export default function RiskVisualization({ score, baseScore = 1.5, ci, details = [], breakdown = [] }: Props) {
  const barWidth = `${Math.round((score / 10) * 100)}%`;
  const entries = breakdown.length > 0 ? breakdown : normalizeFallback(details);
  const elevating = entries.filter((item) => item.impact_type === "risk-elevating");
  const mitigating = entries.filter((item) => item.impact_type === "risk-mitigating");
  const evidence = entries.filter((item) => item.impact_type === "evidence-based");
  const plusTotal = entries.filter((item) => item.contribution > 0).reduce((sum, item) => sum + item.contribution, 0);
  const minusTotal = entries.filter((item) => item.contribution < 0).reduce((sum, item) => sum + item.contribution, 0);
  const modeledScore = Math.max(1, Math.min(10, baseScore + plusTotal + minusTotal));

  return (
    <div className={`rounded-lg border p-3 ${riskColor(score)} min-w-[260px]`}>
      <div className="text-xs font-medium uppercase tracking-wide opacity-70">Risk score</div>
      <div className="mt-0.5 flex items-end gap-1">
        <span className="text-2xl font-bold leading-none">{score.toFixed(1)}</span>
        <span className="pb-0.5 text-sm font-medium opacity-60">/ 10</span>
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-black/10">
        <div className={`h-1.5 rounded-full transition-all ${scoreBarColor(score)}`} style={{ width: barWidth }} />
      </div>
      <div className="mt-1 text-xs font-semibold">{interpretation(score)}</div>
      {ci && <div className="mt-0.5 text-xs opacity-60">95% CI: {ci[0].toFixed(1)}–{ci[1].toFixed(1)}</div>}

      {entries.length > 0 && (
        <>
          <div className="mt-2 rounded border border-slate-200/70 bg-white/70 p-2 text-xs text-slate-700">
            Base {baseScore.toFixed(1)} +{plusTotal.toFixed(1)} {minusTotal.toFixed(1)} = {modeledScore.toFixed(1)}
          </div>
          <div className="mt-2 space-y-2 text-xs">
            {[
              { label: "Risk-elevating", items: elevating },
              { label: "Risk-mitigating", items: mitigating },
              { label: "Evidence signals", items: evidence },
            ].map(({ label, items }) =>
              items.length > 0 ? (
                <div key={label}>
                  <div className="mb-1 font-semibold text-slate-700">{label}</div>
                  <div className="flex flex-wrap gap-1">
                    {items.map((item, i) => (
                      <span
                        key={`${label}-${i}-${item.factor}`}
                        className={`rounded border px-1.5 py-0.5 leading-tight ${chipColor(item.impact_type)}`}
                        title={`${item.layer_name} (Layer ${item.layer}) • ${item.contribution >= 0 ? "+" : ""}${item.contribution.toFixed(1)} • ${item.factor}`}
                      >
                        L{item.layer} {item.contribution >= 0 ? "+" : ""}
                        {item.contribution.toFixed(1)} ·{" "}
                        {item.factor.length > MAX_FACTOR_DISPLAY_LENGTH
                          ? item.factor.slice(0, TRUNCATED_FACTOR_LENGTH) + "…"
                          : item.factor}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null,
            )}
          </div>
          <details className="mt-2 rounded border border-slate-200/70 bg-white/70 p-2 text-xs text-slate-700">
            <summary className="cursor-pointer font-semibold">5-layer methodology</summary>
            <ol className="mt-2 list-decimal pl-4">
              <li>Layer 1: patient factors (age, stage, ECOG, comorbidities, organ dysfunction)</li>
              <li>Layer 2: treatment-class baseline toxicity profile</li>
              <li>Layer 3: drug-specific toxicity signals from landmark data</li>
              <li>Layer 4: patient-treatment interactions (including biomarker-guided mitigation)</li>
              <li>Layer 5: evidence signals from retrieved publications</li>
            </ol>
            <a
              className="mt-2 inline-block text-sky-700 underline"
              href="https://github.com/spencerriddell/secondopinion#risk-assessment-methodology"
              target="_blank"
              rel="noreferrer"
            >
              Risk assessment documentation
            </a>
          </details>
        </>
      )}
    </div>
  );
}
