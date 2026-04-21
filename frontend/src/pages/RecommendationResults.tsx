import { Link } from "react-router-dom";
import RecommendationList from "../components/RecommendationList";
import type { RecommendationResponse } from "../types";

type Props = { result: RecommendationResponse | null };

export default function RecommendationResults({ result }: Props) {
  if (!result) {
    return (
      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
        <p>No recommendation result found.</p>
        <Link to="/intake" className="font-medium text-sky-700 underline">Go to intake</Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-sky-100 bg-white p-5 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-900">Recommendation Results</h2>
        <div className="mt-1 text-sm text-slate-600">Patient ID: {result.patient_id}</div>
        <div className="mt-2 text-sm text-slate-600">Showing {result.recommendations.length} recommendations</div>
      </div>
      <RecommendationList recommendations={result.recommendations} />
      <Link to="/intake" className="inline-block font-medium text-sky-700 underline">Back to intake</Link>
    </div>
  );
}
