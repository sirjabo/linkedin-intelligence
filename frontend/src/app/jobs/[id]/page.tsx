"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { getJob, runMatch, getMatch, createApplication, recordMatchOutcome, type Job, type MatchResult } from "@/lib/api-v2";
import MatchScoreCard from "@/components/MatchScoreCard";
import { ArrowLeftIcon, ZapIcon, FileTextIcon, TrendingUpIcon } from "lucide-react";

const OUTCOME_OPTIONS = [
  { value: "offer", label: "Recibí oferta" },
  { value: "interview", label: "Llegué a entrevista" },
  { value: "phone_screen", label: "Entrevista inicial" },
  { value: "rejected", label: "Rechazado" },
  { value: "no_response", label: "Sin respuesta" },
];

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [job, setJob] = useState<Job | null>(null);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningMatch, setRunningMatch] = useState(false);
  const [creatingApp, setCreatingApp] = useState(false);
  const [recordingOutcome, setRecordingOutcome] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token || !id) return;
    Promise.all([
      getJob(token, id),
      getMatch(token, id).catch(() => null),
    ]).then(([j, m]) => {
      setJob(j);
      setMatch(m);
    }).catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, id]);

  async function handleRunMatch() {
    if (!token || !id) return;
    setRunningMatch(true);
    setError("");
    try {
      const m = await runMatch(token, id);
      setMatch(m);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al analizar");
    } finally {
      setRunningMatch(false);
    }
  }

  async function handleCreateApplication() {
    if (!token || !id) return;
    setCreatingApp(true);
    setError("");
    try {
      const app = await createApplication(token, id);
      router.push(`/applications/${app.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al crear postulación");
      setCreatingApp(false);
    }
  }

  async function handleRecordOutcome(outcome: string) {
    if (!token || !id || !match) return;
    setRecordingOutcome(true);
    setError("");
    try {
      const updated = await recordMatchOutcome(token, id, outcome);
      setMatch(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al registrar resultado");
    } finally {
      setRecordingOutcome(false);
    }
  }

  if (isLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando…</div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-red-400">{error || "Trabajo no encontrado"}</div>
      </div>
    );
  }

  const currentOutcome = (match as Record<string, unknown> | null)?.outcome as string | null ?? null;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeftIcon size={20} />
          </Link>
          <h1 className="font-bold text-white truncate">{job.title ?? "Trabajo"}</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {error && (
          <div className="mb-4 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Job info */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h2 className="text-xl font-bold text-white mb-1">{job.title ?? "—"}</h2>
              <p className="text-slate-400">
                {job.company ?? "Empresa desconocida"}
                {job.location ? ` · ${job.location}` : ""}
                {job.remote_type ? ` · ${job.remote_type}` : ""}
              </p>
              {job.seniority && (
                <span className="inline-block mt-2 text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                  {job.seniority}
                </span>
              )}
              {job.tech_stack && job.tech_stack.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Tech Stack</p>
                  <div className="flex flex-wrap gap-1.5">
                    {job.tech_stack.map((t) => (
                      <span key={t} className="text-xs bg-blue-900/40 text-blue-300 border border-blue-800 px-2 py-0.5 rounded">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleRunMatch}
                disabled={runningMatch}
                className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              >
                <ZapIcon size={15} />
                {runningMatch ? "Analizando…" : match ? "Reanalizar match" : "Analizar match"}
              </button>

              <button
                onClick={handleCreateApplication}
                disabled={creatingApp}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              >
                <FileTextIcon size={15} />
                {creatingApp ? "Creando…" : "Crear postulación"}
              </button>
            </div>

            {/* Learning loop: outcome feedback */}
            {match && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
                  <TrendingUpIcon size={16} className="text-blue-400" />
                  ¿Cómo resultó esta postulación?
                </h3>
                <p className="text-xs text-slate-500 mb-3">
                  Registrar el resultado real ayuda a mejorar el algoritmo de matching.
                </p>
                <div className="flex flex-wrap gap-2">
                  {OUTCOME_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => handleRecordOutcome(opt.value)}
                      disabled={recordingOutcome}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        currentOutcome === opt.value
                          ? "bg-blue-600 text-white"
                          : "bg-slate-800 hover:bg-slate-700 text-slate-300"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {currentOutcome && (
                  <p className="text-xs text-emerald-400 mt-3">
                    Resultado registrado: {OUTCOME_OPTIONS.find(o => o.value === currentOutcome)?.label ?? currentOutcome}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Match score */}
          <div>
            {match ? (
              <MatchScoreCard match={match} />
            ) : (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-center">
                <ZapIcon size={32} className="mx-auto text-slate-700 mb-3" />
                <p className="text-sm text-slate-400">
                  Hacé click en "Analizar match" para ver qué tan bien aplica tu perfil.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
