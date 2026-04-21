import { useState } from "react";
import type { Recommendation } from "../types";
import CitationViewer from "./CitationViewer";
import RiskVisualization from "./RiskVisualization";

type Props = { recommendation: Recommendation };
type CardProps = Props & { rank?: number };

export default function RecommendationCard({ recommendation, rank }: CardProps) {
  const [open, setOpen] = useState(false);

  return (
    <article className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-700">
            Recommendation {rank ?? "-"}
          </div>
          <h3 className="text-lg font-semibold">{recommendation.treatment.name}</h3>
          <p className="text-sm text-slate-600">{recommendation.treatment.mechanism}</p>
        </div>
        <RiskVisualization score={recommendation.risk_score} details={recommendation.risk_factors} />
      </div>

      <p className="text-sm"><strong>Indication:</strong> {recommendation.indication.clinical_rationale}</p>

      {recommendation.contraindication.length > 0 && (
        <ul className="text-sm list-disc pl-5 text-red-700">
          {recommendation.contraindication.map((c, i) => (
            <li key={i}>{c.risk} ({c.severity})</li>
          ))}
        </ul>
      )}

      <button className="text-sm font-medium text-sky-700 underline" onClick={() => setOpen((v) => !v)} type="button">
        {open ? "Hide details" : "Show details"}
      </button>

      {open && (
        <div className="space-y-3">
          <p className="text-sm">{recommendation.explanation}</p>
          <CitationViewer citations={recommendation.citations} />
        </div>
      )}
    </article>
  );
}
