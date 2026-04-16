type Props = { score: number; details?: string[] };

function riskColor(score: number): string {
  if (score <= 3) return "bg-green-200 text-green-900";
  if (score <= 6) return "bg-yellow-200 text-yellow-900";
  if (score <= 8) return "bg-orange-200 text-orange-900";
  return "bg-red-200 text-red-900";
}

function interpretation(score: number): string {
  if (score <= 3) return "Lower risk";
  if (score <= 6) return "Moderate risk";
  if (score <= 8) return "High risk";
  return "Very high risk";
}

export default function RiskVisualization({ score, details = [] }: Props) {
  return (
    <div className={`rounded-md p-3 ${riskColor(score)}`} title={details.join(" | ")}>
      <div className="text-sm">Risk score</div>
      <div className="text-2xl font-bold">{score.toFixed(1)} / 10</div>
      <div className="text-sm">{interpretation(score)}</div>
    </div>
  );
}
