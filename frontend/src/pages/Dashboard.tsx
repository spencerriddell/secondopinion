import { Link } from "react-router-dom";

export default function Dashboard() {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Second Opinion CDS</h1>
      <p className="text-slate-700">Evidence-backed oncology treatment recommendations with risk analysis and citation tracking.</p>
      <Link to="/intake" className="inline-block bg-blue-600 text-white px-4 py-2 rounded">Start New Analysis</Link>
      <div className="text-sm text-slate-600">
        Supports NSCLC, breast, and colorectal examples with PubMed and guideline retrieval.
      </div>
    </div>
  );
}
