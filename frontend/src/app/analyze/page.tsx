"use client";

import { FormEvent, useState } from "react";
import Navbar from "@/components/Navbar";
import ATSResult from "@/components/ATSResult";
import { analyzeCV, analyzeCVFile } from "@/lib/api";
import { CVAnalysisResult, ROLE_LABELS, TargetRole } from "@/types/analysis";
import Link from "next/link";

const ROLES = Object.keys(ROLE_LABELS) as TargetRole[];

export default function AnalyzePage() {
  const [role, setRole] = useState<TargetRole>("ai_engineer");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CVAnalysisResult | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const analysis = file
        ? await analyzeCVFile(file, role)
        : await analyzeCV({ cv_text: text, target_role: role });
      setResult(analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo analizar el CV");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 pt-12 pb-24">
        <p className="text-sm text-blue-400 mb-2">Sprint 001 · CV Analyzer</p>
        <h1 className="text-3xl font-bold mb-2">Analizá tu CV contra filtros ATS</h1>
        <p className="text-slate-400 mb-8 max-w-2xl">
          Pegá el texto de tu CV o subí un PDF. Calculamos un ATS Score 0–100, keywords
          faltantes y las 5 recomendaciones de mayor impacto para{" "}
          {ROLE_LABELS[role]}.
        </p>

        <form onSubmit={onSubmit} className="space-y-4 mb-10">
          <div className="flex flex-wrap gap-2">
            {ROLES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  role === r
                    ? "bg-blue-600 border-blue-500 text-white"
                    : "border-white/10 text-slate-400 hover:text-white"
                }`}
              >
                {ROLE_LABELS[r]}
              </button>
            ))}
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Pegá acá tu CV (mínimo 100 caracteres)..."
            className="w-full min-h-48 rounded-2xl bg-white/[0.03] border border-white/10 p-4 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50"
          />

          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <label className="text-sm text-slate-400">
              O subí un PDF
              <input
                type="file"
                accept="application/pdf"
                className="block mt-1 text-sm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <button
              type="submit"
              disabled={loading || (!file && text.trim().length < 100)}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed px-6 py-2.5 rounded-xl font-medium"
            >
              {loading ? "Analizando..." : "Calcular ATS Score"}
            </button>
            <Link href="/profile" className="text-sm text-slate-500 hover:text-blue-400">
              Prefiero el coach de CV →
            </Link>
          </div>
          {error && <p className="text-sm text-rose-400">{error}</p>}
        </form>

        {result && <ATSResult result={result} />}
      </div>
    </div>
  );
}
