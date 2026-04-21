import { useMemo, useState } from "react";

type Citation = {
  pmid: string;
  doi?: string;
  title: string;
  authors: string[];
  formatted?: string;
};

type Props = { citations: Citation[] };

export default function CitationViewer({ citations }: Props) {
  const [format, setFormat] = useState("Vancouver");
  const text = useMemo(
    () => citations.map((c) => c.formatted || `${c.authors.join(", ")}. ${c.title}. PMID:${c.pmid}.`).join("\n"),
    [citations],
  );

  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold">Citations ({citations.length})</h4>
        <select value={format} onChange={(e) => setFormat(e.target.value)} className="rounded border border-slate-200 px-2 py-1 text-sm">
          <option>Vancouver</option>
          <option>APA</option>
          <option>MLA</option>
          <option>BibTeX</option>
        </select>
      </div>
      <pre className="whitespace-pre-wrap rounded bg-white p-2 text-xs">{text}</pre>
      <button
        className="text-sm font-medium text-sky-700 underline"
        onClick={() => navigator.clipboard.writeText(text)}
        type="button"
      >
        Copy {format}
      </button>
    </div>
  );
}
