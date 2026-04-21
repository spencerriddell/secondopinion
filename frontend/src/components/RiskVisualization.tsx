type Props = { score: number; details?: string[] };

function riskColor(score: number): string {
  if (score <= 3) return "bg-emerald-100 text-emerald-900";
  if (score <= 6) return "bg-amber-100 text-amber-900";
  if (score <= 8) return "bg-orange-100 text-orange-900";
  return "bg-rose-100 text-rose-900";
}

function interpretation(score: number): string {
  if (score <= 3) return "Lower risk";
  if (score <= 6) return "Moderate risk";
  if (score <= 8) return "High risk";
  return "Very high risk";
}

export default function RiskVisualization({ score, details = [] }: Props) {
  return (
    <div className={`rounded-lg p-3 ${riskColor(score)}`} title={details.join(" | ")}>
      <div className="text-sm">Risk score</div>
      <div className="text-2xl font-bold">{score.toFixed(1)} / 10</div>
      <div className="text-sm">{interpretation(score)}</div>
    </div>
  );
}
