import type { PatientEHR, RecommendationResponse } from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit, retries = 1): Promise<T> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Request failed: ${res.status}`);
    }
    return (await res.json()) as T;
  } catch (error) {
    if (retries > 0) {
      return request<T>(path, options, retries - 1);
    }
    throw error;
  }
}

export const postRecommendations = (payload: PatientEHR) =>
  request<RecommendationResponse>("/api/recommendations", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getSupportedBiomarkers = (cancerType: string) =>
  request<Record<string, string>>(`/api/biomarkers/${encodeURIComponent(cancerType)}`);

export const getSupportedGenetics = (cancerType: string) =>
  request<string[]>(`/api/genetics/${encodeURIComponent(cancerType)}`);

export const getRecommendation = (id: string) => request(`/api/recommendations/${id}`);
export const searchEvidence = (query: string) =>
  request(`/api/evidence/search?query=${encodeURIComponent(query)}`);
