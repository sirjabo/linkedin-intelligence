import type { MatchResult } from "@/lib/api-v2";

const TIER_COLOR: Record<string, string> = {
  excellent: "text-emerald-400",
  strong: "text-blue-400",
  moderate: "text-yellow-400",
  weak: "text-orange-400",
  poor: "text-red-400",
};

const TIER_LABEL: Record<string, string> = {
  excellent: "Excelente",
  strong: "Fuerte",
  moderate: "Moderado",
  weak: "Débil",
  poor: "Bajo",
};

export default function MatchScoreCard({ match }: { match: MatchResult }) {
  const pct = Math.round(match.overall_score * 100);
  const color = TIER_COLOR[match.tier] ?? "text-slate-400";
  const label = TIER_LABEL[match.tier] ?? match.tier;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Match Score
        </h3>
        <span className={`text-3xl font-bold ${color}`}>{pct}%</span>
      </div>

      <div className="w-full bg-slate-800 rounded-full h-2 mb-3">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>

      <p className={`text-sm font-medium mb-4 ${color}`}>{label}</p>

      {match.reasoning && (
        <p className="text-sm text-slate-400 mb-4 leading-relaxed">{match.reasoning}</p>
      )}

      {match.strengths.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-semibold text-emerald-500 uppercase mb-1.5">Fortalezas</p>
          <ul className="space-y-1">
            {match.strengths.map((s, i) => (
              <li key={i} className="text-sm text-slate-300 flex gap-2">
                <span className="text-emerald-500 mt-0.5">✓</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {match.gaps.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-yellow-500 uppercase mb-1.5">Gaps</p>
          <ul className="space-y-1">
            {match.gaps.map((g, i) => (
              <li key={i} className="text-sm text-slate-300 flex gap-2">
                <span className="text-yellow-500 mt-0.5">△</span>
                {g}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
