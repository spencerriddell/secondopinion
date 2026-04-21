import { Link } from "react-router-dom";
import RecommendationList from "../components/RecommendationList";
import type { RecommendationResponse } from "../types";

type Props = { result: RecommendationResponse | null };

export default function RecommendationResults({ result }: Props) {
  if (!result) {
    return (
      <div className="space-y-3">
        <p>No recommendation result found.</p>
        <Link to="/intake" className="underline">Go to intake</Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Recommendation Results</h2>
      <div className="text-sm text-slate-600">Patient ID: {result.patient_id}</div>
      <RecommendationList recommendations={result.recommendations} />
      <Link to="/intake" className="underline">Back to intake</Link>
    </div>
  );
}
