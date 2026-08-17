"use client";

import { CVAnalysisResult, ROLE_LABELS } from "@/types/analysis";

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-400";
  if (score >= 60) return "text-blue-400";
  if (score >= 40) return "text-amber-400";
  return "text-rose-400";
}

function scoreLabel(score: number): string {
  if (score >= 90) return "Excelente";
  if (score >= 75) return "Bueno";
  if (score >= 60) return "Aceptable";
  if (score >= 40) return "Bajo";
  return "Crítico";
}

export default function ATSResult({ result }: { result: CVAnalysisResult }) {
  const sections = Object.entries(result.section_scores);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 flex flex-col sm:flex-row sm:items-center gap-6">
        <div className="text-center sm:text-left">
          <p className={`text-6xl font-bold tabular-nums ${scoreColor(result.ats_score)}`}>
            {result.ats_score}
          </p>
          <p className="text-sm text-slate-400 mt-1">
            ATS Score · {scoreLabel(result.ats_score)} · {ROLE_LABELS[result.target_role]}
          </p>
        </div>
        <p className="text-slate-300 leading-relaxed flex-1">{result.summary}</p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        {sections.map(([name, score]) => (
          <div key={name} className="rounded-xl border border-white/8 bg-white/[0.02] px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm capitalize text-slate-300">{name}</span>
              <span className={`text-sm font-medium ${scoreColor(score)}`}>{score}</span>
            </div>
            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${score}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="grid sm:grid-cols-2 gap-6">
        <div>
          <h3 className="font-semibold mb-3">Keywords encontradas</h3>
          <div className="flex flex-wrap gap-2">
            {result.keyword_analysis.found.map((k) => (
              <span
                key={k.keyword}
                className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
              >
                {k.keyword} ×{k.count}
              </span>
            ))}
            {result.keyword_analysis.found.length === 0 && (
              <p className="text-sm text-slate-500">Ninguna keyword del rol aparece en el CV.</p>
            )}
          </div>
        </div>
        <div>
          <h3 className="font-semibold mb-3">Keywords faltantes</h3>
          <div className="flex flex-wrap gap-2">
            {result.keyword_analysis.missing.map((k) => (
              <span
                key={k.keyword}
                className="text-xs px-2.5 py-1 rounded-full bg-rose-500/10 text-rose-300 border border-rose-500/20"
              >
                {k.keyword}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h3 className="font-semibold mb-3">Recomendaciones</h3>
        <ol className="space-y-3">
          {result.recommendations.map((rec) => (
            <li
              key={`${rec.priority}-${rec.message}`}
              className="rounded-xl border border-white/8 bg-white/[0.02] p-4"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-blue-400 font-medium">#{rec.priority}</span>
                <span className="text-xs text-slate-500 capitalize">{rec.section}</span>
                <span className="text-xs text-slate-600">· {rec.impact}</span>
              </div>
              <p className="text-sm text-slate-200">{rec.message}</p>
              {rec.original && rec.suggested && (
                <div className="mt-3 grid gap-2 text-xs">
                  <p className="text-slate-500">
                    <span className="text-slate-400">Original: </span>
                    {rec.original}
                  </p>
                  <p className="text-emerald-300/90">
                    <span className="text-emerald-400">Sugerido: </span>
                    {rec.suggested}
                  </p>
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
