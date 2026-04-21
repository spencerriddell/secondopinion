import { useMemo, useState } from "react";
import type { Recommendation } from "../types";
import RecommendationCard from "./RecommendationCard";

type Props = { recommendations: Recommendation[] };

export default function RecommendationList({ recommendations }: Props) {
  const [typeFilter, setTypeFilter] = useState("all");

  const list = useMemo(() => {
    const sorted = [...recommendations].sort((a, b) => a.risk_score - b.risk_score);
    if (typeFilter === "all") return sorted;
    return sorted.filter((r) => r.treatment.drug_class.toLowerCase().includes(typeFilter));
  }, [recommendations, typeFilter]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
        <span className="text-sm font-medium text-slate-700">Filter:</span>
        <select className="rounded-md border border-slate-200 px-2 py-1 text-sm" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">All</option>
          <option value="chemo">Chemotherapy</option>
          <option value="immuno">Immunotherapy</option>
          <option value="target">Targeted</option>
          <option value="radi">Radiation</option>
          <option value="surg">Surgery</option>
        </select>
        <span className="ml-auto text-xs text-slate-500">{list.length} shown</span>
      </div>
      {list.map((rec, index) => (
        <RecommendationCard key={rec.recommendation_id} recommendation={rec} rank={index + 1} />
      ))}
    </div>
  );
}
