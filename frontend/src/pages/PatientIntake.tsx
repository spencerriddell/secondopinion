import { useState } from "react";
import { useNavigate } from "react-router-dom";
import EHRForm from "../components/EHRForm";
import { postRecommendations } from "../services/api";
import type { PatientEHR, RecommendationResponse } from "../types";

type Props = { setResult: (value: RecommendationResponse) => void };

export default function PatientIntake({ setResult }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function onSubmit(payload: PatientEHR) {
    setError("");
    setLoading(true);
    try {
      const data = await postRecommendations(payload);
      setResult(data);
      navigate("/results");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      {error && <div className="bg-red-100 text-red-700 p-2 rounded">{error}</div>}
      <EHRForm onSubmit={onSubmit} loading={loading} />
    </div>
  );
}
