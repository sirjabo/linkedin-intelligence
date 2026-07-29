import type { CVAnalysisResponse } from "@/lib/api";
import { scoreColor, scoreLabel } from "@/lib/utils";

interface AnalysisResultProps {
  data: CVAnalysisResponse;
}

export function AnalysisResult({ data }: AnalysisResultProps) {
  const topRecs = data.recommendations.slice(0, 3);
  const topMissing = data.keyword_analysis.missing.slice(0, 8);
  const topFound = data.keyword_analysis.found.slice(0, 8);

  return (
    <div className="space-y-8">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-wide text-slate-500">
          ATS Score · {data.target_role.replaceAll("_", " ")}
        </p>
        <div className="mt-2 flex items-end gap-4">
          <span className={`text-6xl font-bold tabular-nums ${scoreColor(data.ats_score)}`}>
            {data.ats_score}
          </span>
          <span className="mb-2 text-lg text-slate-600">{scoreLabel(data.ats_score)}</span>
        </div>
        <p className="mt-4 max-w-2xl text-slate-700">{data.summary}</p>
        <p className="mt-2 text-xs text-slate-400">
          Procesado en {data.processing_time_ms} ms
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-slate-900">Keywords encontradas</h2>
          <ul className="mt-4 space-y-2">
            {topFound.length === 0 && (
              <li className="text-sm text-slate-500">Ninguna keyword detectada</li>
            )}
            {topFound.map((kw) => (
              <li
                key={kw.keyword}
                className="flex items-center justify-between text-sm text-slate-700"
              >
                <span>{kw.keyword}</span>
                <span className="text-slate-400">
                  ×{kw.count} · w{kw.weight.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-slate-900">Keywords faltantes</h2>
          <ul className="mt-4 space-y-2">
            {topMissing.map((kw) => (
              <li
                key={kw.keyword}
                className="flex items-center justify-between text-sm text-slate-700"
              >
                <span>{kw.keyword}</span>
                <span className="text-slate-400">
                  {kw.suggested_section} · w{kw.weight.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-900">Top recomendaciones</h2>
        <ol className="mt-4 space-y-4">
          {topRecs.map((rec) => (
            <li key={`${rec.priority}-${rec.message}`} className="text-sm text-slate-700">
              <div className="flex items-start gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-50 text-xs font-semibold text-blue-700">
                  {rec.priority}
                </span>
                <div>
                  <p className="font-medium">{rec.message}</p>
                  <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">
                    {rec.section} · {rec.impact}
                  </p>
                  {rec.suggested && (
                    <p className="mt-2 rounded-md bg-slate-50 p-2 text-xs text-slate-600">
                      Sugerido: {rec.suggested}
                    </p>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
