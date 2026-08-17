"use client";

import { FormEvent, useState } from "react";
import Navbar from "@/components/Navbar";
import { analyzeLinkedIn } from "@/lib/api";
import { LinkedInAnalysisResult, ROLE_LABELS, TargetRole } from "@/types/analysis";

const ROLES = Object.keys(ROLE_LABELS) as TargetRole[];

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-400";
  if (score >= 60) return "text-blue-400";
  if (score >= 40) return "text-amber-400";
  return "text-rose-400";
}

export default function LinkedInPage() {
  const [role, setRole] = useState<TargetRole>("ai_engineer");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<LinkedInAnalysisResult | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      setResult(await analyzeLinkedIn({ profile_text: text, target_role: role }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo analizar el perfil");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 pt-12 pb-24">
        <p className="text-sm text-blue-400 mb-2">Sprint 002 · LinkedIn Engine</p>
        <h1 className="text-3xl font-bold mb-2">Analizá tu perfil de LinkedIn</h1>
        <p className="text-slate-400 mb-8 max-w-2xl">
          Pegá título, About, experiencia y skills. Evaluamos visibilidad para recruiters
          y te damos variantes de headline.
        </p>

        <form onSubmit={onSubmit} className="space-y-4 mb-10">
          <div className="flex flex-wrap gap-2">
            {ROLES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`px-3 py-1.5 rounded-full text-sm border ${
                  role === r
                    ? "bg-blue-600 border-blue-500 text-white"
                    : "border-white/10 text-slate-400"
                }`}
              >
                {ROLE_LABELS[r]}
              </button>
            ))}
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Título\n\nAbout\n...\n\nExperience\n...\n\nSkills\nPython, SQL, ..."}
            className="w-full min-h-56 rounded-2xl bg-white/[0.03] border border-white/10 p-4 text-sm focus:outline-none focus:border-blue-500/50"
          />
          <button
            type="submit"
            disabled={loading || text.trim().length < 50}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 px-6 py-2.5 rounded-xl font-medium"
          >
            {loading ? "Analizando..." : "Calcular Profile Score"}
          </button>
          {error && <p className="text-sm text-rose-400">{error}</p>}
        </form>

        {result && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 p-6">
              <p className={`text-6xl font-bold ${scoreColor(result.overall_score)}`}>
                {Math.round(result.overall_score)}
              </p>
              <p className="text-sm text-slate-400 mt-1">Profile Score</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              {Object.entries(result.section_scores).map(([name, score]) => (
                <div key={name} className="rounded-xl border border-white/8 px-4 py-3 flex justify-between">
                  <span className="capitalize text-sm text-slate-300">{name}</span>
                  <span className={`text-sm font-medium ${scoreColor(score)}`}>
                    {Math.round(score)}
                  </span>
                </div>
              ))}
            </div>
            {result.title_analysis.current && (
              <div className="rounded-2xl border border-white/8 p-5">
                <p className="text-xs text-slate-500 mb-1">Título actual</p>
                <p className="font-medium mb-3">{result.title_analysis.current}</p>
                {result.title_analysis.issues.length > 0 && (
                  <ul className="text-sm text-amber-300/90 space-y-1 mb-4">
                    {result.title_analysis.issues.map((issue) => (
                      <li key={issue}>· {issue}</li>
                    ))}
                  </ul>
                )}
                <p className="text-xs text-slate-500 mb-2">Variantes sugeridas</p>
                <ul className="space-y-2">
                  {result.title_analysis.suggested_variants.map((variant) => (
                    <li
                      key={variant}
                      className="text-sm text-slate-200 bg-white/[0.03] rounded-lg px-3 py-2"
                    >
                      {variant}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <ol className="space-y-3">
              {result.recommendations.map((rec) => (
                <li key={`${rec.priority}-${rec.message}`} className="rounded-xl border border-white/8 p-4">
                  <p className="text-xs text-blue-400 mb-1">
                    #{rec.priority} · {rec.section} · {rec.impact}
                  </p>
                  <p className="text-sm">{rec.message}</p>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}
