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
      <div className="flex gap-2 items-center">
        <span className="text-sm">Filter:</span>
        <select className="border rounded px-2 py-1 text-sm" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">All</option>
          <option value="chemo">Chemotherapy</option>
          <option value="immuno">Immunotherapy</option>
          <option value="target">Targeted</option>
          <option value="radi">Radiation</option>
          <option value="surg">Surgery</option>
        </select>
      </div>
      {list.map((rec) => (
        <RecommendationCard key={rec.recommendation_id} recommendation={rec} />
      ))}
    </div>
  );
}
