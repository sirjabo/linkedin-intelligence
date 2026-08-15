"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import {
  getCandidate,
  updateCandidate,
  ingestTextSource,
  listSources,
  rebuildProfile,
  getProfile,
  getProfileHealth,
  getProfileOptimizer,
  getProfileBenchmark,
  type Candidate,
  type CandidateSource,
  type CandidateProfile,
  type ProfileHealth,
  type OptimizationReport,
  type BenchmarkResult,
} from "@/lib/api-v2";
import {
  ArrowLeftIcon, UserIcon, PlusIcon, RefreshCwIcon,
  ZapIcon, CheckCircleIcon, AlertCircleIcon, TrendingUpIcon,
  BarChart2Icon, ChevronDownIcon,
} from "lucide-react";

const ROLE_LABELS: Record<string, string> = {
  ai_engineer: "AI Engineer",
  data_engineer: "Data Engineer",
  analytics_engineer: "Analytics Engineer",
  ml_engineer: "ML Engineer",
  backend_engineer: "Backend Engineer",
  frontend_engineer: "Frontend Engineer",
  devops_engineer: "DevOps Engineer",
  data_scientist: "Data Scientist",
};

const TIER_STYLE: Record<string, string> = {
  Excelente: "text-emerald-400 bg-emerald-950/30 border-emerald-800/40",
  Bueno: "text-blue-400 bg-blue-950/30 border-blue-800/40",
  "En desarrollo": "text-yellow-400 bg-yellow-950/30 border-yellow-800/40",
  Inicial: "text-red-400 bg-red-950/30 border-red-800/40",
};

const IMPACT_COLOR: Record<string, string> = {
  high: "text-red-400",
  medium: "text-yellow-400",
  low: "text-slate-400",
};

const SOURCE_TYPES = [
  { value: "cv", label: "CV / Currículum" },
  { value: "linkedin", label: "LinkedIn (texto pegado)" },
  { value: "github", label: "GitHub bio" },
  { value: "portfolio", label: "Portfolio" },
  { value: "manual", label: "Manual" },
];

function SkillBadge({ skill }: { skill: Record<string, unknown> }) {
  const name = (skill.canonical_name ?? skill.name ?? "") as string;
  const level = (skill.proficiency_level ?? skill.level ?? "") as string;
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-blue-900/30 text-blue-300 border border-blue-800/50 px-2 py-0.5 rounded">
      {name}
      {level && <span className="text-blue-500">· {level}</span>}
    </span>
  );
}

export default function ProfilePage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [sources, setSources] = useState<CandidateSource[]>([]);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [health, setHealth] = useState<ProfileHealth | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState("");

  // Benchmark state
  const [benchmark, setBenchmark] = useState<BenchmarkResult | null>(null);
  const [benchmarkRole, setBenchmarkRole] = useState("");
  const [loadingBenchmark, setLoadingBenchmark] = useState(false);
  const [benchmarkError, setBenchmarkError] = useState("");

  // Profile Optimizer state
  const [optimizer, setOptimizer] = useState<OptimizationReport | null>(null);
  const [loadingOptimizer, setLoadingOptimizer] = useState(false);
  const [optimizerError, setOptimizerError] = useState("");

  // Source ingestion state
  const [sourceType, setSourceType] = useState("cv");
  const [rawText, setRawText] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestSuccess, setIngestSuccess] = useState(false);

  // Rebuild state
  const [rebuilding, setRebuilding] = useState(false);

  // Edit state
  const [editMode, setEditMode] = useState(false);
  const [editName, setEditName] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [editRoles, setEditRoles] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  const loadAll = useCallback(async () => {
    if (!token) return;
    setPageLoading(true);
    setError("");
    try {
      const [cand, srcs, h] = await Promise.all([
        getCandidate(token).catch(() => null),
        listSources(token).catch(() => [] as CandidateSource[]),
        getProfileHealth(token).catch(() => null),
      ]);
      setCandidate(cand);
      setSources(srcs);
      setHealth(h);
      if (cand) {
        const prof = await getProfile(token).catch(() => null);
        setProfile(prof);
      }
    } catch {
      setError("Error al cargar el perfil");
    } finally {
      setPageLoading(false);
    }
  }, [token]);

  useEffect(() => { loadAll(); }, [loadAll]);

  function startEdit() {
    if (!candidate) return;
    setEditName(candidate.name ?? "");
    setEditLocation(candidate.location ?? "");
    setEditRoles((candidate.target_roles ?? []).join(", "));
    setEditMode(true);
  }

  async function handleSave() {
    if (!token) return;
    setSaving(true);
    try {
      const updated = await updateCandidate(token, {
        name: editName || undefined,
        location: editLocation || undefined,
        target_roles: editRoles ? editRoles.split(",").map((r) => r.trim()).filter(Boolean) : [],
      });
      setCandidate(updated);
      setEditMode(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  async function handleIngest() {
    if (!token || !rawText.trim()) return;
    setIngesting(true);
    setIngestSuccess(false);
    setError("");
    try {
      const src = await ingestTextSource(token, sourceType, rawText.trim());
      setSources((prev) => [src, ...prev]);
      setRawText("");
      setIngestSuccess(true);
      setTimeout(() => setIngestSuccess(false), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al ingresar fuente");
    } finally {
      setIngesting(false);
    }
  }

  async function handleRebuild() {
    if (!token) return;
    setRebuilding(true);
    setError("");
    try {
      const prof = await rebuildProfile(token);
      setProfile(prof);
      const h = await getProfileHealth(token).catch(() => null);
      setHealth(h);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al reconstruir perfil");
    } finally {
      setRebuilding(false);
    }
  }

  async function handleLoadBenchmark(role: string) {
    if (!token) return;
    setLoadingBenchmark(true);
    setBenchmarkError("");
    try {
      const data = await getProfileBenchmark(token, role);
      setBenchmark(data);
      setBenchmarkRole(role);
    } catch (err: unknown) {
      setBenchmarkError(err instanceof Error ? err.message : "Error al cargar benchmark");
    } finally {
      setLoadingBenchmark(false);
    }
  }

  async function handleLoadOptimizer() {
    if (!token) return;
    setLoadingOptimizer(true);
    setOptimizerError("");
    try {
      const report = await getProfileOptimizer(token);
      setOptimizer(report);
    } catch (err: unknown) {
      setOptimizerError(err instanceof Error ? err.message : "Error al cargar recomendaciones");
    } finally {
      setLoadingOptimizer(false);
    }
  }

  if (isLoading || pageLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando…</div>
      </div>
    );
  }

  if (!candidate) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <AlertCircleIcon size={48} className="mx-auto text-slate-700 mb-4" />
          <p className="text-slate-400">No tenés un perfil de candidato todavía.</p>
          <p className="text-slate-500 text-sm mt-1">Subí tu CV para empezar.</p>
        </div>
      </div>
    );
  }

  const skills = (profile?.skills ?? []) as Record<string, unknown>[];
  const experience = (profile?.experience ?? []) as Record<string, unknown>[];

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeftIcon size={20} />
          </Link>
          <div className="flex-1">
            <h1 className="font-bold text-white">Mi Perfil</h1>
          </div>
          <button
            onClick={handleRebuild}
            disabled={rebuilding || sources.length === 0}
            title={sources.length === 0 ? "Agregá fuentes primero" : ""}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            {rebuilding ? (
              <RefreshCwIcon size={14} className="animate-spin" />
            ) : (
              <ZapIcon size={14} />
            )}
            {rebuilding ? "Reconstruyendo…" : "Reconstruir perfil"}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {/* Benchmark vs mercado */}
        {candidate?.target_roles && candidate.target_roles.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <BarChart2Icon size={16} className="text-cyan-400" />
                Benchmark vs mercado
              </h3>
              {!loadingBenchmark && (
                <div className="flex items-center gap-2">
                  {candidate.target_roles.length > 1 && (
                    <div className="relative">
                      <select
                        value={benchmarkRole || candidate.target_roles[0]}
                        onChange={(e) => handleLoadBenchmark(e.target.value)}
                        className="appearance-none bg-slate-800 border border-slate-700 text-xs text-slate-300 rounded-lg pl-3 pr-7 py-1.5 focus:outline-none focus:border-cyan-600 cursor-pointer"
                      >
                        {candidate.target_roles.map((r) => (
                          <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>
                        ))}
                      </select>
                      <ChevronDownIcon size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                    </div>
                  )}
                  <button
                    onClick={() => handleLoadBenchmark(benchmarkRole || candidate.target_roles![0])}
                    className="flex items-center gap-1.5 text-xs bg-cyan-900/30 hover:bg-cyan-900/50 text-cyan-300 border border-cyan-800/50 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    <BarChart2Icon size={12} />
                    {benchmark ? "Actualizar" : "Ver benchmark"}
                  </button>
                </div>
              )}
            </div>

            {loadingBenchmark && (
              <div className="flex items-center gap-2 text-xs text-slate-400 py-2">
                <RefreshCwIcon size={12} className="animate-spin" />
                Comparando tus skills con el mercado…
              </div>
            )}

            {benchmarkError && (
              <p className="text-xs text-red-400">{benchmarkError}</p>
            )}

            {!benchmark && !loadingBenchmark && !benchmarkError && (
              <p className="text-xs text-slate-500">
                Compará tus skills contra las más demandadas en el mercado para tu rol objetivo.
              </p>
            )}

            {benchmark && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <p className="text-3xl font-bold text-white tabular-nums">{benchmark.percentile}</p>
                    <p className="text-xs text-slate-500 mt-0.5">percentil</p>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-slate-500">
                        {ROLE_LABELS[benchmark.role] ?? benchmark.role}
                      </span>
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${TIER_STYLE[benchmark.tier] ?? "text-slate-400 bg-slate-800 border-slate-700"}`}>
                        {benchmark.tier}
                      </span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${
                          benchmark.percentile >= 75 ? "bg-emerald-500" :
                          benchmark.percentile >= 50 ? "bg-blue-500" :
                          benchmark.percentile >= 25 ? "bg-yellow-500" : "bg-red-500"
                        }`}
                        style={{ width: `${benchmark.percentile}%` }}
                      />
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{benchmark.message}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {benchmark.matched_skills.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-emerald-400 mb-1.5">
                        ✓ Skills que tenés ({benchmark.matched_skills.length})
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {benchmark.matched_skills.slice(0, 8).map((s) => (
                          <span key={s} className="text-xs bg-emerald-950/30 text-emerald-300 border border-emerald-800/40 px-2 py-0.5 rounded">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {benchmark.missing_skills.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-red-400 mb-1.5">
                        ✗ Skills faltantes ({benchmark.missing_skills.length})
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {benchmark.missing_skills.slice(0, 8).map((s) => (
                          <span key={s} className="text-xs bg-red-950/30 text-red-300 border border-red-800/40 px-2 py-0.5 rounded">
                            + {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <p className="text-xs text-slate-600">
                  {benchmark.matched_count} de {benchmark.total_checked} skills clave del mercado · Datos en tiempo real
                </p>
              </div>
            )}
          </div>
        )}

        {/* Profile health score */}
        {health && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <CheckCircleIcon size={16} className="text-blue-400" />
                Salud del perfil
              </h3>
              <span className={`text-sm font-bold ${health.score >= 0.8 ? "text-emerald-400" : health.score >= 0.5 ? "text-yellow-400" : "text-red-400"}`}>
                {Math.round(health.score * 100)}%
              </span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden mb-4">
              <div
                className={`h-full rounded-full transition-all ${health.score >= 0.8 ? "bg-emerald-500" : health.score >= 0.5 ? "bg-yellow-500" : "bg-red-500"}`}
                style={{ width: `${Math.round(health.score * 100)}%` }}
              />
            </div>
            {health.tips.length > 0 && (
              <ul className="space-y-1.5">
                {health.tips.map((tip, i) => (
                  <li key={i} className="text-xs text-slate-400 flex items-start gap-2">
                    <AlertCircleIcon size={12} className="text-yellow-500 mt-0.5 flex-shrink-0" />
                    {tip}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Profile Optimizer */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
              <TrendingUpIcon size={16} className="text-purple-400" />
              Optimizador de perfil
            </h3>
            {!optimizer && (
              <button
                onClick={handleLoadOptimizer}
                disabled={loadingOptimizer}
                className="flex items-center gap-1.5 text-xs bg-purple-900/30 hover:bg-purple-900/50 text-purple-300 border border-purple-800/50 disabled:opacity-50 px-3 py-1.5 rounded-lg transition-colors"
              >
                {loadingOptimizer ? (
                  <RefreshCwIcon size={12} className="animate-spin" />
                ) : (
                  <TrendingUpIcon size={12} />
                )}
                {loadingOptimizer ? "Analizando…" : "Ver recomendaciones"}
              </button>
            )}
            {optimizer && (
              <button
                onClick={handleLoadOptimizer}
                disabled={loadingOptimizer}
                className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
              >
                {loadingOptimizer ? "Actualizando…" : "Actualizar"}
              </button>
            )}
          </div>

          {optimizerError && (
            <p className="text-xs text-red-400">{optimizerError}</p>
          )}

          {!optimizer && !loadingOptimizer && !optimizerError && (
            <p className="text-xs text-slate-500">
              Analiza tus postulaciones anteriores para detectar qué skills necesitás agregar a tu perfil.
            </p>
          )}

          {optimizer && (
            <div className="space-y-4">
              <p className="text-xs text-slate-500">
                Basado en {optimizer.total_analyses_reviewed} análisis de postulaciones.
              </p>
              {optimizer.summary && (
                <p className="text-sm text-slate-300 leading-relaxed">{optimizer.summary}</p>
              )}

              {optimizer.top_skill_gaps.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-400 mb-2">Skills faltantes más frecuentes</p>
                  <div className="flex flex-wrap gap-2">
                    {optimizer.top_skill_gaps.slice(0, 10).map((gap) => (
                      <span
                        key={gap.skill}
                        className="inline-flex items-center gap-1.5 text-xs bg-red-900/20 text-red-300 border border-red-800/40 px-2 py-0.5 rounded"
                      >
                        {gap.skill}
                        <span className="text-red-500 font-medium">{gap.frequency}×</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {optimizer.tips.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-400 mb-2">Recomendaciones</p>
                  <div className="space-y-3">
                    {optimizer.tips.map((tip, i) => (
                      <div key={i} className="border-l-2 border-slate-700 pl-3">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={`text-xs font-semibold uppercase ${IMPACT_COLOR[tip.impact] ?? "text-slate-400"}`}>
                            {tip.impact}
                          </span>
                          <span className="text-xs text-slate-600">·</span>
                          <span className="text-xs text-slate-500 capitalize">{tip.category}</span>
                        </div>
                        <p className="text-sm text-slate-300">{tip.tip}</p>
                        {tip.evidence && (
                          <p className="text-xs text-slate-500 mt-0.5">{tip.evidence}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {optimizer.tips.length === 0 && optimizer.top_skill_gaps.length === 0 && (
                <p className="text-sm text-emerald-400 flex items-center gap-2">
                  <CheckCircleIcon size={14} />
                  Tu perfil está bien alineado con tus postulaciones recientes.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Candidate info */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-start justify-between mb-4">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
              <UserIcon size={16} className="text-blue-400" />
              Información personal
            </h3>
            {!editMode && (
              <button
                onClick={startEdit}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                Editar
              </button>
            )}
          </div>

          {editMode ? (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-500 block mb-1">Nombre</label>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Ubicación</label>
                <input
                  value={editLocation}
                  onChange={(e) => setEditLocation(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Roles objetivo (separados por coma)</label>
                <input
                  value={editRoles}
                  onChange={(e) => setEditRoles(e.target.value)}
                  placeholder="Data Engineer, ML Engineer"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
                />
              </div>
              <div className="flex gap-3 justify-end pt-1">
                <button
                  onClick={() => setEditMode(false)}
                  className="text-sm text-slate-400 hover:text-white transition-colors px-3 py-1.5"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors"
                >
                  {saving ? "Guardando…" : "Guardar"}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <div className="flex gap-2">
                <span className="text-slate-500 w-24">Nombre</span>
                <span className="text-slate-200">{candidate.name ?? "–"}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-slate-500 w-24">Email</span>
                <span className="text-slate-200">{candidate.email ?? "–"}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-slate-500 w-24">Ubicación</span>
                <span className="text-slate-200">{candidate.location ?? "–"}</span>
              </div>
              {candidate.target_roles && candidate.target_roles.length > 0 && (
                <div className="flex gap-2">
                  <span className="text-slate-500 w-24">Roles</span>
                  <span className="text-slate-200">{candidate.target_roles.join(", ")}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Add source */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <PlusIcon size={16} className="text-blue-400" />
            Agregar fuente
          </h3>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Tipo de fuente</label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-600"
              >
                {SOURCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Pegá el contenido</label>
              <textarea
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                rows={6}
                placeholder="Pegá tu CV, perfil de LinkedIn, bio de GitHub, etc."
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 resize-none"
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleIngest}
                disabled={ingesting || !rawText.trim()}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              >
                {ingesting ? (
                  <RefreshCwIcon size={14} className="animate-spin" />
                ) : (
                  <PlusIcon size={14} />
                )}
                {ingesting ? "Procesando…" : "Agregar fuente"}
              </button>
              {ingestSuccess && (
                <span className="flex items-center gap-1.5 text-sm text-emerald-400">
                  <CheckCircleIcon size={15} />
                  Fuente agregada
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Sources list */}
        {sources.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-4">
              Mis fuentes ({sources.length})
            </h3>
            <div className="space-y-3">
              {sources.map((src) => (
                <div key={src.id} className="flex items-start justify-between gap-4 py-2 border-b border-slate-800 last:border-0">
                  <div>
                    <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                      {SOURCE_TYPES.find((t) => t.value === src.source_type)?.label ?? src.source_type}
                    </span>
                    {src.extraction_confidence != null && (
                      <span className="ml-2 text-xs text-slate-500">
                        Confianza: {Math.round(src.extraction_confidence * 100)}%
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-slate-600 flex-shrink-0">
                    {new Date(src.created_at).toLocaleDateString("es-AR")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Consolidated profile */}
        {profile && (
          <>
            {profile.summary && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h3 className="font-semibold text-slate-200 mb-3">Resumen profesional</h3>
                <p className="text-sm text-slate-300 leading-relaxed">{profile.summary}</p>
                {profile.career_level && (
                  <div className="mt-3">
                    <span className="text-xs bg-purple-900/30 text-purple-400 border border-purple-800/50 px-2 py-0.5 rounded">
                      {profile.career_level}
                    </span>
                  </div>
                )}
              </div>
            )}

            {skills.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h3 className="font-semibold text-slate-200 mb-4">
                  Skills ({skills.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {skills.map((s, i) => (
                    <SkillBadge key={i} skill={s} />
                  ))}
                </div>
              </div>
            )}

            {experience.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h3 className="font-semibold text-slate-200 mb-4">Experiencia</h3>
                <div className="space-y-4">
                  {experience.map((exp, i) => (
                    <div key={i} className="border-l-2 border-slate-700 pl-4">
                      <p className="text-sm font-medium text-slate-200">
                        {(exp.title ?? exp.role ?? "") as string}
                        {exp.company ? ` · ${exp.company as string}` : ""}
                      </p>
                      {(exp.start_date ?? exp.start) != null && (
                        <p className="text-xs text-slate-500 mt-0.5">
                          {(exp.start_date ?? exp.start) as string}
                          {(exp.end_date ?? exp.end) != null ? ` – ${(exp.end_date ?? exp.end) as string}` : " – Presente"}
                        </p>
                      )}
                      {exp.description != null && (
                        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                          {(exp.description as string).slice(0, 200)}
                          {(exp.description as string).length > 200 ? "…" : ""}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p className="text-xs text-slate-600 text-center">
              Perfil v{profile.version} · Última actualización: {new Date(profile.rebuilt_at).toLocaleString("es-AR")}
            </p>
          </>
        )}

        {!profile && sources.length > 0 && (
          <div className="text-center py-12">
            <ZapIcon size={40} className="mx-auto text-slate-700 mb-4" />
            <p className="text-slate-400">Tenés {sources.length} fuente{sources.length !== 1 ? "s" : ""} cargada{sources.length !== 1 ? "s" : ""}.</p>
            <p className="text-slate-500 text-sm mt-1">Hacé click en "Reconstruir perfil" para consolidar tu información.</p>
          </div>
        )}
      </main>
    </div>
  );
}
