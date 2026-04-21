type Props = {
  score: number;
  ci?: [number, number];
  details?: string[];
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

function factorChipColor(factor: string): string {
  const lower = factor.toLowerCase();
  if (lower.includes("high") || lower.includes("severe") || lower.includes("fatal")) {
    return "bg-rose-100 text-rose-800 border-rose-200";
  }
  if (lower.includes("evidence") || lower.includes("pmid") || lower.includes("trial")) {
    return "bg-sky-100 text-sky-800 border-sky-200";
  }
  if (lower.includes("match") || lower.includes("indicated") || lower.includes("reduces")) {
    return "bg-emerald-100 text-emerald-800 border-emerald-200";
  }
  return "bg-slate-100 text-slate-700 border-slate-200";
}

const MAX_FACTOR_DISPLAY_LENGTH = 55;
const TRUNCATED_FACTOR_LENGTH = 52;

export default function RiskVisualization({ score, ci, details = [] }: Props) {
  const barWidth = `${Math.round((score / 10) * 100)}%`;

  return (
    <div className={`rounded-lg border p-3 ${riskColor(score)} min-w-[160px]`}>
      <div className="text-xs font-medium uppercase tracking-wide opacity-70">Risk score</div>
      <div className="mt-0.5 flex items-end gap-1">
        <span className="text-2xl font-bold leading-none">{score.toFixed(1)}</span>
        <span className="pb-0.5 text-sm font-medium opacity-60">/ 10</span>
      </div>
      {/* Score bar */}
      <div className="mt-2 h-1.5 w-full rounded-full bg-black/10">
        <div
          className={`h-1.5 rounded-full transition-all ${scoreBarColor(score)}`}
          style={{ width: barWidth }}
        />
      </div>
      <div className="mt-1 text-xs font-semibold">{interpretation(score)}</div>
      {ci && (
        <div className="mt-0.5 text-xs opacity-60">
          95% CI: {ci[0].toFixed(1)}–{ci[1].toFixed(1)}
        </div>
      )}
      {details.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {details.map((factor, i) => (
            <span
              key={i}
              className={`rounded border px-1.5 py-0.5 text-xs leading-tight ${factorChipColor(factor)}`}
              title={factor}
            >
              {factor.length > MAX_FACTOR_DISPLAY_LENGTH ? factor.slice(0, TRUNCATED_FACTOR_LENGTH) + "…" : factor}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
