import { Link } from "react-router-dom";

export default function Dashboard() {
  return (
    <div className="space-y-6 rounded-2xl border border-sky-100 bg-white/95 p-6 shadow-sm">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-slate-900">Second Opinion CDS</h1>
        <p className="text-slate-600">Evidence-backed oncology treatment recommendations with risk analysis and citation tracking.</p>
      </div>
      <Link to="/intake" className="inline-block rounded-xl bg-gradient-to-r from-sky-700 to-indigo-700 px-5 py-2.5 font-medium text-white shadow-md transition hover:opacity-95">
        Start New Analysis
      </Link>
      <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
        Supports NSCLC, breast, and colorectal examples with PubMed and guideline retrieval.
      </div>
    </div>
  );
}
