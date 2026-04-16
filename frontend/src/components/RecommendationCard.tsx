import { useState } from "react";
import type { Recommendation } from "../types";
import CitationViewer from "./CitationViewer";
import RiskVisualization from "./RiskVisualization";

type Props = { recommendation: Recommendation };

export default function RecommendationCard({ recommendation }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <article className="border rounded-lg p-4 space-y-3 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-lg">{recommendation.treatment.name}</h3>
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

      <button className="text-sm underline" onClick={() => setOpen((v) => !v)} type="button">
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
