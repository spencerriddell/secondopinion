import { useState } from "react";
import type { FormEvent } from "react";
import type { PatientEHR } from "../types";

type Props = {
  onSubmit: (payload: PatientEHR) => Promise<void>;
  loading?: boolean;
};

const initial: PatientEHR = {
  cancer_type: "NSCLC",
  stage: "IV",
  biomarkers: [{ name: "PD-L1", value: "50", unit: "%" }],
  genetics: [{ mutation: "EGFR", status: "wildtype" }],
  age: 65,
  ecog: 1,
  comorbidities: [],
  metastases: [],
  progression: true,
  prior_treatments: [],
  organ_function: { renal: "normal", hepatic: "normal", cardiac: "normal" },
};

export default function EHRForm({ onSubmit, loading }: Props) {
  const [form, setForm] = useState<PatientEHR>(initial);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await onSubmit(form);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 bg-white rounded border p-4">
      <h2 className="text-xl font-semibold">Patient Intake</h2>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-sm">Cancer Type
          <select className="w-full border rounded p-2" value={form.cancer_type} onChange={(e) => setForm({ ...form, cancer_type: e.target.value })}>
            <option>NSCLC</option><option>breast</option><option>colorectal</option><option>melanoma</option><option>prostate</option>
          </select>
        </label>
        <label className="text-sm">Stage
          <select className="w-full border rounded p-2" value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}>
            <option>I</option><option>II</option><option>III</option><option>IV</option>
          </select>
        </label>
        <label className="text-sm">Age
          <input type="number" className="w-full border rounded p-2" value={form.age} onChange={(e) => setForm({ ...form, age: Number(e.target.value) })} />
        </label>
        <label className="text-sm">ECOG
          <select className="w-full border rounded p-2" value={form.ecog} onChange={(e) => setForm({ ...form, ecog: Number(e.target.value) })}>
            {[0,1,2,3,4,5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label className="text-sm">Biomarker (name)
          <input className="w-full border rounded p-2" value={form.biomarkers[0]?.name || ""} onChange={(e) => setForm({ ...form, biomarkers: [{ ...form.biomarkers[0], name: e.target.value }] })} />
        </label>
        <label className="text-sm">Biomarker (value)
          <input className="w-full border rounded p-2" value={form.biomarkers[0]?.value || ""} onChange={(e) => setForm({ ...form, biomarkers: [{ ...form.biomarkers[0], value: e.target.value }] })} />
        </label>
      </div>

      <label className="text-sm block">Comorbidities (comma-separated)
        <input className="w-full border rounded p-2" onChange={(e) => setForm({ ...form, comorbidities: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} />
      </label>

      <label className="text-sm block">Metastasis sites (comma-separated)
        <input className="w-full border rounded p-2" onChange={(e) => setForm({ ...form, metastases: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} />
      </label>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.progression} onChange={(e) => setForm({ ...form, progression: e.target.checked })} />
        Disease progression
      </label>

      <button type="submit" className="bg-slate-900 text-white px-4 py-2 rounded disabled:opacity-50" disabled={loading}>
        {loading ? "Analyzing..." : "Generate Recommendations"}
      </button>
    </form>
  );
}
