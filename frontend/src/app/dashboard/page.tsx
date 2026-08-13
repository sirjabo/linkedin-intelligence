"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { listJobs, createJob, type Job } from "@/lib/api-v2";
import { BriefcaseIcon, PlusIcon, LogOutIcon } from "lucide-react";

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  analyzing: "Analizando…",
  analyzed: "Analizado",
  error: "Error",
};

export default function DashboardPage() {
  const { token, logout, isLoading } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [jd, setJd] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    if (!isLoading && !token) {
      router.replace("/login");
    }
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token) return;
    listJobs(token)
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function handleCreateJob(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !jd.trim()) return;
    setCreating(true);
    setCreateError("");
    try {
      const job = await createJob(token, jd.trim());
      setJobs((prev) => [job, ...prev]);
      setJd("");
      setShowCreate(false);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Error al crear");
    } finally {
      setCreating(false);
    }
  }

  if (isLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-lg font-bold text-white">LinkedIn Intelligence</h1>
          <div className="flex items-center gap-4">
            <Link href="/profile" className="text-sm text-slate-400 hover:text-white transition-colors">
              Mi Perfil
            </Link>
            <Link href="/recommendations" className="text-sm text-slate-400 hover:text-white transition-colors">
              Recomendados
            </Link>
            <Link href="/applications" className="text-sm text-slate-400 hover:text-white transition-colors">
              Postulaciones
            </Link>
            <Link href="/analytics" className="text-sm text-slate-400 hover:text-white transition-colors">
              Analytics
            </Link>
            <button
              onClick={() => { logout(); router.push("/login"); }}
              className="text-slate-400 hover:text-white transition-colors"
              aria-label="Cerrar sesión"
            >
              <LogOutIcon size={18} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold">Mis Trabajos</h2>
            <p className="text-slate-400 text-sm mt-1">{jobs.length} oferta{jobs.length !== 1 ? "s" : ""} agregada{jobs.length !== 1 ? "s" : ""}</p>
          </div>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            <PlusIcon size={16} />
            Agregar trabajo
          </button>
        </div>

        {showCreate && (
          <form onSubmit={handleCreateJob} className="mb-6 bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3">Pegá la descripción del trabajo</h3>
            {createError && (
              <div className="mb-3 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
                {createError}
              </div>
            )}
            <textarea
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              rows={8}
              required
              placeholder="Pegá aquí la descripción completa del trabajo…"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-600 resize-none mb-3"
            />
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={creating || !jd.trim()}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm font-semibold rounded-lg transition-colors"
              >
                {creating ? "Analizando…" : "Analizar trabajo"}
              </button>
            </div>
          </form>
        )}

        {jobs.length === 0 ? (
          <div className="text-center py-20">
            <BriefcaseIcon size={48} className="mx-auto text-slate-700 mb-4" />
            <p className="text-slate-400">No tenés trabajos agregados todavía.</p>
            <p className="text-slate-500 text-sm mt-1">Hacé click en "Agregar trabajo" para empezar.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <Link
                key={job.id}
                href={`/jobs/${job.id}`}
                className="block bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-white">
                      {job.title ?? "Trabajo sin título"}
                    </h3>
                    <p className="text-sm text-slate-400 mt-0.5">
                      {job.company ?? "Empresa desconocida"}
                      {job.location ? ` · ${job.location}` : ""}
                      {job.remote_type ? ` · ${job.remote_type}` : ""}
                    </p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    job.status === "analyzed"
                      ? "bg-emerald-900/40 text-emerald-400"
                      : job.status === "error"
                      ? "bg-red-900/40 text-red-400"
                      : "bg-slate-800 text-slate-400"
                  }`}>
                    {STATUS_LABEL[job.status] ?? job.status}
                  </span>
                </div>
                {job.tech_stack && job.tech_stack.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {job.tech_stack.slice(0, 6).map((t) => (
                      <span key={t} className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                        {t}
                      </span>
                    ))}
                    {job.tech_stack.length > 6 && (
                      <span className="text-xs text-slate-500">+{job.tech_stack.length - 6}</span>
                    )}
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
