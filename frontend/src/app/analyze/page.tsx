"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/lib/auth";
import {
  analyzeLinkedIn,
  getAnalyzeRoles,
  type LinkedInAnalysis,
  type LinkedInRecommendation,
} from "@/lib/api-v2";
import {
  LinkedinIcon,
  ArrowLeftIcon,
  RefreshCwIcon,
  ZapIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  ChevronRightIcon,
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

const SECTION_LABELS: Record<string, string> = {
  title: "Título",
  about: "Extracto (About)",
  experience: "Experiencia",
  skills: "Skills",
  projects: "Proyectos",
  education: "Educación",
};

const IMPACT_BADGE: Record<string, string> = {
  very_high: "bg-red-500/15 text-red-400 border-red-500/20",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
  low: "bg-slate-500/15 text-slate-400 border-slate-500/20",
};

const IMPACT_LABEL: Record<string, string> = {
  very_high: "Impacto muy alto",
  high: "Impacto alto",
  medium: "Impacto medio",
  low: "Impacto bajo",
};

function ScoreRing({ score }: { score: number }) {
  const color =
    score >= 75 ? "text-emerald-400" : score >= 50 ? "text-yellow-400" : "text-red-400";
  return (
    <div className={`text-5xl font-bold tabular-nums ${color}`}>
      {score}
      <span className="text-2xl text-slate-500 font-normal">/100</span>
    </div>
  );
}

function SectionBar({ label, score }: { label: string; score: number }) {
  const color =
    score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 w-36 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs text-slate-400 w-8 text-right">{score}</span>
    </div>
  );
}

function RecommendationCard({ rec }: { rec: LinkedInRecommendation }) {
  const sectionLabel = SECTION_LABELS[rec.section] ?? rec.section;
  const badgeClass = IMPACT_BADGE[rec.impact] ?? IMPACT_BADGE.low;
  const impactLabel = IMPACT_LABEL[rec.impact] ?? rec.impact;
  return (
    <div className="flex gap-4 bg-slate-900 border border-slate-800 rounded-xl px-5 py-4">
      <span className="text-xs text-slate-600 font-mono w-4 shrink-0 mt-0.5">{rec.priority}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className="text-xs text-slate-500 uppercase tracking-wide">{sectionLabel}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${badgeClass}`}>
            {impactLabel}
          </span>
        </div>
        <p className="text-sm text-slate-200 leading-relaxed">{rec.message}</p>
      </div>
    </div>
  );
}

export default function AnalyzePage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [roles, setRoles] = useState<string[]>([]);
  const [selectedRole, setSelectedRole] = useState("ai_engineer");
  const [profileText, setProfileText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<LinkedInAnalysis | null>(null);

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    getAnalyzeRoles()
      .then((d) => setRoles(d.roles))
      .catch(() => setRoles(Object.keys(ROLE_LABELS)));
  }, []);

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !profileText.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyzeLinkedIn(token, profileText.trim(), selectedRole);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al analizar el perfil");
    } finally {
      setLoading(false);
    }
  }

  if (isLoading) return null;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-300 text-sm mb-10 transition-colors"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" /> Volver al inicio
        </Link>

        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-blue-600/20 flex items-center justify-center">
            <LinkedinIcon className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Analizador de Perfil LinkedIn</h1>
            <p className="text-sm text-slate-500">
              Pegá el texto de tu perfil y recibí un score por sección + variantes de título optimizadas
            </p>
          </div>
        </div>

        {/* Form */}
        {!result && (
          <form onSubmit={handleAnalyze} className="space-y-6">
            {/* Role selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Rol objetivo
              </label>
              <div className="flex flex-wrap gap-2">
                {(roles.length > 0 ? roles : Object.keys(ROLE_LABELS)).map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => setSelectedRole(role)}
                    className={`text-sm px-4 py-1.5 rounded-full border transition-colors ${
                      selectedRole === role
                        ? "bg-blue-600 border-blue-600 text-white"
                        : "bg-transparent border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200"
                    }`}
                  >
                    {ROLE_LABELS[role] ?? role}
                  </button>
                ))}
              </div>
            </div>

            {/* Text area */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Texto del perfil de LinkedIn
              </label>
              <p className="text-xs text-slate-500 mb-3">
                Copiá todo el texto visible de tu perfil (título, extracto, experiencia, skills).
                No necesitás la URL — solo el contenido.
              </p>
              <textarea
                value={profileText}
                onChange={(e) => setProfileText(e.target.value)}
                placeholder="Juan Pérez&#10;AI Engineer | Python · LangChain · FastAPI&#10;Buenos Aires, Argentina&#10;&#10;Sobre mí:&#10;..."
                rows={14}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {error && (
              <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !profileText.trim()}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-medium text-sm transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <RefreshCwIcon className="w-4 h-4 animate-spin" />
                  Analizando con IA…
                </>
              ) : (
                <>
                  <ZapIcon className="w-4 h-4" />
                  Analizar perfil
                </>
              )}
            </button>
          </form>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-8">
            {/* Overall score */}
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-6 flex items-center gap-8">
              <div>
                <ScoreRing score={result.overall_score} />
                <p className="text-xs text-slate-500 mt-2">Score general</p>
              </div>
              <div className="flex-1 space-y-2.5">
                {Object.entries(result.section_scores).map(([key, score]) => (
                  <SectionBar key={key} label={SECTION_LABELS[key] ?? key} score={score} />
                ))}
              </div>
            </div>

            {/* Title analysis */}
            <section>
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
                Análisis del título
              </h2>
              <div className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-4 mb-4">
                <p className="text-xs text-slate-500 mb-1">Título actual</p>
                <p className="text-sm font-medium text-slate-200">
                  {result.title_analysis.current || "No detectado"}
                </p>
                {result.title_analysis.issues.length > 0 && (
                  <ul className="mt-3 space-y-1">
                    {result.title_analysis.issues.map((issue, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-slate-400">
                        <AlertTriangleIcon className="w-3.5 h-3.5 text-yellow-500 shrink-0 mt-0.5" />
                        {issue}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="space-y-2">
                {result.title_analysis.suggested_variants.map((variant, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded-xl border border-emerald-800/40 bg-emerald-950/20 px-5 py-3"
                  >
                    <CheckCircleIcon className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span className="text-sm text-slate-200 flex-1">{variant}</span>
                    <ChevronRightIcon className="w-4 h-4 text-slate-600" />
                  </div>
                ))}
              </div>
            </section>

            {/* Keyword gaps */}
            {result.keyword_gaps.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
                  Skills / keywords faltantes para {ROLE_LABELS[result.target_role] ?? result.target_role}
                </h2>
                <div className="flex flex-wrap gap-2">
                  {result.keyword_gaps.map((kw) => (
                    <span
                      key={kw}
                      className="text-xs px-3 py-1.5 rounded-full border border-red-800/40 bg-red-950/20 text-red-400"
                    >
                      + {kw}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* Recommendations */}
            {result.recommendations.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
                  Recomendaciones priorizadas
                </h2>
                <div className="space-y-3">
                  {result.recommendations.map((rec) => (
                    <RecommendationCard key={rec.priority} rec={rec} />
                  ))}
                </div>
              </section>
            )}

            {/* Redo */}
            <button
              onClick={() => setResult(null)}
              className="w-full py-2.5 border border-slate-700 hover:border-slate-500 rounded-xl text-sm text-slate-400 hover:text-slate-200 transition-colors"
            >
              Analizar otro perfil
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
