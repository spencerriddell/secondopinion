import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import type { PatientEHR } from "../types";
import { getSupportedBiomarkers, getSupportedGeneticVariants, getSupportedGenetics } from "../services/api";

type Props = {
  onSubmit: (payload: PatientEHR) => Promise<void>;
  loading?: boolean;
};

const initial: PatientEHR = {
  cancer_type: "NSCLC",
  stage: "IV",
  biomarkers: [],
  genetics: [],
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
  const [supportedBiomarkers, setSupportedBiomarkers] = useState<Record<string, string>>({});
  const [supportedGenetics, setSupportedGenetics] = useState<string[]>([]);
  const [supportedGeneticVariants, setSupportedGeneticVariants] = useState<Record<string, string[]>>({});
  const defaultGeneticsStatus = "mutant";
  const defaultGeneticsStatusOptions = ["mutant", "WT"];

  useEffect(() => {
    let alive = true;
    Promise.all([
      getSupportedBiomarkers(form.cancer_type),
      getSupportedGenetics(form.cancer_type),
      getSupportedGeneticVariants(form.cancer_type),
    ])
      .then(([biomarkers, genetics, variants]) => {
        if (!alive) return;
        setSupportedBiomarkers(biomarkers);
        setSupportedGenetics(genetics);
        setSupportedGeneticVariants(variants);
      })
      .catch(() => {
        if (!alive) return;
        setSupportedBiomarkers({});
        setSupportedGenetics([]);
        setSupportedGeneticVariants({});
      });
    return () => {
      alive = false;
    };
  }, [form.cancer_type]);

  const biomarkerOptions = useMemo(() => Object.entries(supportedBiomarkers), [supportedBiomarkers]);

  function addBiomarker() {
    setForm((current) => ({
      ...current,
      biomarkers: [...current.biomarkers, { name: "", value: "", unit: "" }],
    }));
  }

  function updateBiomarker(index: number, patch: { name?: string; value?: string; unit?: string }) {
    setForm((current) => ({
      ...current,
      biomarkers: current.biomarkers.map((item, currentIndex) =>
        currentIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function removeBiomarker(index: number) {
    setForm((current) => ({
      ...current,
      biomarkers: current.biomarkers.filter((_, currentIndex) => currentIndex !== index),
    }));
  }

  function addGenetic() {
    setForm((current) => ({
      ...current,
      genetics: [...current.genetics, { mutation: "", status: defaultGeneticsStatus }],
    }));
  }

  function updateGenetic(index: number, patch: { mutation?: string; status?: string }) {
    setForm((current) => ({
      ...current,
      genetics: current.genetics.map((item, currentIndex) =>
        currentIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function removeGenetic(index: number) {
    setForm((current) => ({
      ...current,
      genetics: current.genetics.filter((_, currentIndex) => currentIndex !== index),
    }));
  }

  function statusOptionsForMutation(mutation: string): string[] {
    return supportedGeneticVariants[mutation] || defaultGeneticsStatusOptions;
  }

  function biomarkerPlaceholder(name: string, fallbackUnit?: string): string {
    if (!name) return "Level / result";
    const resolvedUnit = supportedBiomarkers[name] || fallbackUnit;
    return resolvedUnit ? `Level / result (${resolvedUnit})` : "Level / result";
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await onSubmit({
      ...form,
      biomarkers: form.biomarkers
        .filter((item) => item.name.trim() && item.value.trim())
        .map((item) => ({
          ...item,
          name: item.name.trim(),
          value: item.value.trim(),
          unit: item.name ? supportedBiomarkers[item.name.trim()] || item.unit : item.unit,
        })),
      genetics: form.genetics
        .filter((item) => item.mutation.trim())
        .map((item) => ({
          mutation: item.mutation.trim(),
          status: item.status.trim(),
        })),
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-6 rounded-2xl border border-sky-100 bg-white/95 p-6 shadow-sm backdrop-blur"
    >
      <h2 className="text-2xl font-semibold text-slate-900">Patient Intake</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">Cancer Type
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm focus:border-sky-400 focus:outline-none"
            value={form.cancer_type}
            onChange={(e) => setForm({ ...form, cancer_type: e.target.value, biomarkers: [], genetics: [] })}
          >
            <option value="NSCLC">NSCLC</option>
            <option value="breast">Breast</option>
            <option value="colorectal">Colorectal</option>
            <option value="melanoma">Melanoma</option>
            <option value="prostate">Prostate</option>
            <option value="ovarian">Ovarian</option>
            <option value="pancreatic">Pancreatic</option>
            <option value="gastric">Gastric/GEJ</option>
            <option value="endometrial">Endometrial</option>
            <option value="rcc">Renal cell carcinoma</option>
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">Stage
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm focus:border-sky-400 focus:outline-none"
            value={form.stage}
            onChange={(e) => setForm({ ...form, stage: e.target.value })}
          >
            <option>I</option><option>II</option><option>III</option><option>IV</option>
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">Age
          <input
            type="number"
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm focus:border-sky-400 focus:outline-none"
            value={form.age}
            onChange={(e) => setForm({ ...form, age: Number(e.target.value) })}
          />
        </label>
        <label className="text-sm font-medium text-slate-700">ECOG
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm focus:border-sky-400 focus:outline-none"
            value={form.ecog}
            onChange={(e) => setForm({ ...form, ecog: Number(e.target.value) })}
          >
            {[0,1,2,3,4,5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>

      <section className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-800">Biomarkers (optional)</h3>
          <button
            type="button"
            onClick={addBiomarker}
            className="rounded-md border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-700 transition hover:bg-sky-100"
          >
            + Add biomarker
          </button>
        </div>
        {form.biomarkers.length === 0 && (
          <p className="text-sm text-slate-500">No biomarkers selected.</p>
        )}
        <div className="space-y-2">
          {form.biomarkers.map((biomarker, index) => (
            <div key={index} className="grid gap-2 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[1.3fr_1fr_auto_auto]">
              <select
                className="rounded-lg border border-slate-200 p-2 text-sm focus:border-sky-400 focus:outline-none"
                value={biomarker.name}
                onChange={(e) => {
                  const name = e.target.value;
                  updateBiomarker(index, { name, unit: supportedBiomarkers[name] || "" });
                }}
              >
                <option value="">Select biomarker</option>
                {biomarkerOptions.map(([name]) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              <input
                className="rounded-lg border border-slate-200 p-2 text-sm focus:border-sky-400 focus:outline-none"
                placeholder={biomarkerPlaceholder(biomarker.name, biomarker.unit)}
                value={biomarker.value}
                onChange={(e) => updateBiomarker(index, { value: e.target.value })}
              />
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-center text-sm text-slate-600">
                {biomarker.name ? (supportedBiomarkers[biomarker.name] || biomarker.unit || "-") : "-"}
              </div>
              <button
                type="button"
                onClick={() => removeBiomarker(index)}
                className="rounded-lg border border-red-200 px-2 py-2 text-sm text-red-600 transition hover:bg-red-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-800">Genetics (optional)</h3>
          <button
            type="button"
            onClick={addGenetic}
            className="rounded-md border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-700 transition hover:bg-sky-100"
          >
            + Add genetic mutation
          </button>
        </div>
        {form.genetics.length === 0 && (
          <p className="text-sm text-slate-500">No genetics selected.</p>
        )}
        <div className="space-y-2">
          {form.genetics.map((genetic, index) => (
            <div key={index} className="grid gap-2 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[1.4fr_1fr_auto]">
              <select
                className="rounded-lg border border-slate-200 p-2 text-sm focus:border-sky-400 focus:outline-none"
                value={genetic.mutation}
                onChange={(e) => {
                  const mutation = e.target.value;
                  const options = statusOptionsForMutation(mutation);
                  setForm((current) => ({
                    ...current,
                    genetics: current.genetics.map((item, currentIndex) =>
                      currentIndex === index
                        ? {
                            mutation,
                            status: options.includes(item.status) ? item.status : (options[0] || defaultGeneticsStatus),
                          }
                        : item,
                    ),
                  }));
                }}
              >
                <option value="">Select mutation</option>
                {supportedGenetics.map((mutation) => (
                  <option key={mutation} value={mutation}>{mutation}</option>
                ))}
              </select>
              <select
                className="rounded-lg border border-slate-200 p-2 text-sm focus:border-sky-400 focus:outline-none"
                value={genetic.status}
                onChange={(e) => updateGenetic(index, { status: e.target.value })}
              >
                {statusOptionsForMutation(genetic.mutation).map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => removeGenetic(index)}
                className="rounded-lg border border-red-200 px-2 py-2 text-sm text-red-600 transition hover:bg-red-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>

      <label className="block text-sm font-medium text-slate-700">Comorbidities (comma-separated)
        <input
          className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm focus:border-sky-400 focus:outline-none"
          onChange={(e) => setForm({ ...form, comorbidities: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })}
        />
      </label>

      <label className="block text-sm font-medium text-slate-700">Metastasis sites (comma-separated)
        <input
          className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm focus:border-sky-400 focus:outline-none"
          onChange={(e) => setForm({ ...form, metastases: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })}
        />
      </label>

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={form.progression} onChange={(e) => setForm({ ...form, progression: e.target.checked })} />
        Disease progression
      </label>

      <button
        type="submit"
        className="w-full rounded-xl bg-gradient-to-r from-sky-700 to-indigo-700 px-4 py-3 font-medium text-white shadow-md transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={loading}
      >
        {loading ? "Analyzing and generating 5 recommendations..." : "Generate Recommendations"}
      </button>
    </form>
  );
}
