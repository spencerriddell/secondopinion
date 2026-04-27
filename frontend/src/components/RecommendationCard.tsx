import { useState } from "react";
import type { Recommendation } from "../types";
import CitationViewer from "./CitationViewer";
import RiskVisualization from "./RiskVisualization";

type CardProps = { recommendation: Recommendation; rank?: number };

function riskLabel(score: number): string {
  if (score <= 3) return "Lower risk";
  if (score <= 6) return "Moderate risk";
  if (score <= 8) return "High risk";
  return "Very high risk";
}

function riskBadgeColor(score: number): string {
  if (score <= 3) return "border-emerald-300 bg-emerald-50 text-emerald-800";
  if (score <= 6) return "border-amber-300 bg-amber-50 text-amber-800";
  if (score <= 8) return "border-orange-300 bg-orange-50 text-orange-800";
  return "border-rose-300 bg-rose-50 text-rose-800";
}

export default function RecommendationCard({ recommendation, rank }: CardProps) {
  const [open, setOpen] = useState(false);
  const score = recommendation.risk_score;

  return (
    <article className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">
      {/* Header row */}
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-700">
            Recommendation {rank ?? "-"}
          </div>
          <h3 className="text-lg font-semibold leading-snug">{recommendation.treatment.name}</h3>
          <p className="mt-0.5 text-sm text-slate-500">{recommendation.treatment.mechanism}</p>
          <span className="mt-1 inline-block rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
            {recommendation.treatment.drug_class}
          </span>
        </div>
        {/* Compact risk badge */}
        <div className={`shrink-0 rounded-lg border px-3 py-2 text-center ${riskBadgeColor(score)}`}>
          <div className="text-xs font-medium uppercase tracking-wide opacity-70">Risk</div>
          <div className="text-xl font-bold leading-none">{score.toFixed(1)}<span className="text-xs font-normal opacity-60"> /10</span></div>
          <div className="mt-0.5 text-xs font-semibold">{riskLabel(score)}</div>
          {recommendation.risk_confidence_interval && (
            <div className="mt-0.5 text-xs opacity-60">
              CI: {recommendation.risk_confidence_interval[0].toFixed(1)}–{recommendation.risk_confidence_interval[1].toFixed(1)}
            </div>
          )}
        </div>
      </div>

      {/* Indication */}
      <p className="text-sm text-slate-700">
        <span className="font-semibold text-slate-900">Indication: </span>
        {recommendation.indication.clinical_rationale}
      </p>

      {/* Contraindications */}
      {recommendation.contraindication.length > 0 && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-rose-700">
            Contraindications / Cautions
          </div>
          <ul className="space-y-1">
            {recommendation.contraindication.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-rose-800">
                <span className="mt-0.5 shrink-0 rounded border border-rose-300 bg-rose-100 px-1 py-0.5 text-xs font-medium">
                  {c.severity}
                </span>
                <span>{c.risk}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <button
        className="text-sm font-medium text-sky-700 underline"
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        {open ? "Hide details" : "Show details (evidence, citations & risk breakdown)"}
      </button>

      {open && (
        <div className="space-y-4 border-t border-slate-100 pt-3">
          <p className="text-sm text-slate-600">{recommendation.explanation}</p>
          <RiskVisualization
            score={recommendation.risk_score}
            baseScore={recommendation.risk_base_score}
            ci={recommendation.risk_confidence_interval}
            details={recommendation.risk_factors}
            breakdown={recommendation.risk_factor_breakdown}
          />
          <CitationViewer citations={recommendation.citations} />
        </div>
      )}
    </article>
  );
}
