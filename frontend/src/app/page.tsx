"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { AnalysisResult } from "@/components/AnalysisResult";
import { api, type TargetRole } from "@/lib/api";

const ROLES: { value: TargetRole; label: string }[] = [
  { value: "ai_engineer", label: "AI Engineer" },
  { value: "data_engineer", label: "Data Engineer" },
  { value: "analytics_engineer", label: "Analytics Engineer" },
];

export default function HomePage() {
  const [cvText, setCvText] = useState("");
  const [targetRole, setTargetRole] = useState<TargetRole>("ai_engineer");
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.analyze.cv({
        cvText: cvText.trim() || undefined,
        file: file ?? undefined,
        targetRole,
      }),
  });

  const canSubmit = Boolean(file || cvText.trim().length >= 100);

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#dbeafe_0%,_#f8fafc_45%,_#f1f5f9_100%)]">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <div className="text-lg font-semibold tracking-tight text-slate-900">
          LinkedIn Intelligence
        </div>
        <span className="text-sm text-slate-500">Sprint 001 · CV Analyzer</span>
      </header>

      <section className="mx-auto max-w-5xl px-6 pb-16 pt-4">
        <div className="max-w-2xl">
          <h1 className="text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
            LinkedIn Intelligence
          </h1>
          <p className="mt-4 text-lg text-slate-600">
            Pegá tu CV o subí un PDF y obtené un ATS Score real basado en keywords del mercado.
          </p>
        </div>

        <form
          className="mt-10 space-y-6"
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) mutation.mutate();
          }}
        >
          <div>
            <label htmlFor="role" className="mb-2 block text-sm font-medium text-slate-700">
              Rol objetivo
            </label>
            <select
              id="role"
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value as TargetRole)}
              className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none ring-blue-500 focus:ring-2"
            >
              {ROLES.map((role) => (
                <option key={role.value} value={role.value}>
                  {role.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="cv" className="mb-2 block text-sm font-medium text-slate-700">
              Texto del CV
            </label>
            <textarea
              id="cv"
              rows={12}
              value={cvText}
              onChange={(e) => setCvText(e.target.value)}
              placeholder="Pegá acá el contenido de tu CV (mínimo 100 caracteres)…"
              className="w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none ring-blue-500 focus:ring-2"
            />
            <p className="mt-1 text-xs text-slate-500">{cvText.length} caracteres</p>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              O subí un PDF
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Elegir archivo
              </button>
              <span className="text-sm text-slate-500">
                {file ? file.name : "Ningún archivo seleccionado"}
              </span>
              {file && (
                <button
                  type="button"
                  className="text-sm text-red-600 hover:underline"
                  onClick={() => {
                    setFile(null);
                    if (fileRef.current) fileRef.current.value = "";
                  }}
                >
                  Quitar
                </button>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={!canSubmit || mutation.isPending}
            className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending ? "Analizando…" : "Analizar CV"}
          </button>

          {mutation.isError && (
            <p className="text-sm text-red-600">
              {(mutation.error as Error).message || "Error al analizar el CV"}
            </p>
          )}
        </form>

        {mutation.isPending && (
          <div className="mt-10 animate-pulse rounded-lg border border-slate-200 bg-white/70 p-8">
            <div className="h-4 w-40 rounded bg-slate-200" />
            <div className="mt-4 h-20 w-full rounded bg-slate-100" />
            <p className="mt-4 text-sm text-slate-500">Calculando ATS Score…</p>
          </div>
        )}

        {mutation.data && !mutation.isPending && (
          <div className="mt-10">
            <AnalysisResult data={mutation.data} />
          </div>
        )}
      </section>
    </main>
  );
}
