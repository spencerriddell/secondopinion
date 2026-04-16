import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import PatientIntake from "./pages/PatientIntake";
import RecommendationResults from "./pages/RecommendationResults";
import type { RecommendationResponse } from "./types";
import "./index.css";

const queryClient = new QueryClient();

export default function App() {
  const [result, setResult] = useState<RecommendationResponse | null>(null);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-100 text-slate-900">
          <header className="bg-white border-b p-4 flex items-center justify-between">
            <Link to="/" className="font-bold">Second Opinion</Link>
            <nav className="flex gap-3 text-sm">
              <Link to="/">Dashboard</Link>
              <Link to="/intake">Patient Intake</Link>
              <Link to="/results">Results</Link>
            </nav>
          </header>
          <main className="max-w-5xl mx-auto p-4">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/intake" element={<PatientIntake setResult={setResult} />} />
              <Route path="/results" element={<RecommendationResults result={result} />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
