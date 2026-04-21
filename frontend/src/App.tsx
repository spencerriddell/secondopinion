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
        <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-slate-100 text-slate-900">
          <header className="sticky top-0 z-10 border-b border-sky-100 bg-white/90 backdrop-blur">
            <div className="mx-auto flex max-w-6xl items-center justify-between p-4">
              <Link to="/" className="text-lg font-semibold text-sky-900">Second Opinion CDS</Link>
              <nav className="flex gap-4 text-sm font-medium text-slate-600">
                <Link className="transition hover:text-sky-700" to="/">Dashboard</Link>
                <Link className="transition hover:text-sky-700" to="/intake">Patient Intake</Link>
                <Link className="transition hover:text-sky-700" to="/results">Results</Link>
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-6xl p-4 sm:p-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/intake" element={<PatientIntake setResult={setResult} />} />
              <Route path="/results" element={<RecommendationResults result={result} />} />
            </Routes>
          </main>
          <footer className="border-t border-sky-100 bg-white/80 p-3 text-center text-xs text-slate-500">
            Clinical decision support prototype for oncology treatment planning
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
