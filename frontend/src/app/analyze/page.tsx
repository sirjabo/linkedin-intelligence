"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/lib/auth";
import {
  analyzeLinkedIn,
  analyzeLinkedInFromUrl,
  rewriteLinkedIn,
  getAnalyzeRoles,
  type LinkedInAnalysis,
  type LinkedInRecommendation,
  type LinkedInRewrite,
} from "@/lib/api-v2";
import {
  LinkedinIcon,
  ArrowLeftIcon,
  RefreshCwIcon,
  ZapIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  ChevronRightIcon,
  DownloadIcon,
  LinkIcon,
  ClipboardCopyIcon,
  SparklesIcon,
  Loader2Icon,
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

type InputMode = "paste" | "url";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:border-slate-500 transition-colors"
    >
      <ClipboardCopyIcon className="w-3.5 h-3.5" />
      {copied ? "Copiado!" : "Copiar"}
    </button>
  );
}

export default function AnalyzePage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [roles, setRoles] = useState<string[]>([]);
  const [selectedRole, setSelectedRole] = useState("ai_engineer");
  const [inputMode, setInputMode] = useState<InputMode>("paste");
  const [profileText, setProfileText] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<LinkedInAnalysis | null>(null);
  const [fetchedProfileText, setFetchedProfileText] = useState("");
  const [rewrite, setRewrite] = useState<LinkedInRewrite | null>(null);
  const [rewriteLoading, setRewriteLoading] = useState(false);
  const [rewriteError, setRewriteError] = useState("");

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
    if (!token) return;
    setLoading(true);
    setError("");
    setResult(null);
    setRewrite(null);
    try {
      if (inputMode === "url") {
        if (!linkedinUrl.trim()) return;
        const data = await analyzeLinkedInFromUrl(token, linkedinUrl.trim(), selectedRole);
        setFetchedProfileText(data.profile_text ?? "");
        setResult(data);
      } else {
        if (!profileText.trim()) return;
        const data = await analyzeLinkedIn(token, profileText.trim(), selectedRole);
        setFetchedProfileText(profileText.trim());
        setResult(data);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al analizar el perfil");
    } finally {
      setLoading(false);
    }
  }

  async function handleRewrite() {
    if (!token || !result || !fetchedProfileText) return;
    setRewriteLoading(true);
    setRewriteError("");
    try {
      const data = await rewriteLinkedIn(token, fetchedProfileText, selectedRole, result);
      setRewrite(data);
    } catch (err: unknown) {
      setRewriteError(err instanceof Error ? err.message : "Error al generar reescrituras");
    } finally {
      setRewriteLoading(false);
    }
  }

  if (isLoading) return null;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <Link
          href="/"
          aria-label="Volver al inicio"
          className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-300 text-sm mb-10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" aria-hidden="true" /> Volver al inicio
        </Link>

        <div className="flex items-center gap-3 mb-6">
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

        {/* Secondary tool link */}
        <div className="mb-8 flex gap-3">
          <Link
            href="/analyze/about"
            className="flex items-center gap-2 text-sm px-4 py-2 rounded-xl border border-purple-800/40 bg-purple-950/20 text-purple-300 hover:bg-purple-950/40 transition-colors"
          >
            <ZapIcon className="w-3.5 h-3.5" /> About Writer — generá tu sección "Acerca de"
          </Link>
        </div>

        {/* Form */}
        {!result && (
          <form onSubmit={handleAnalyze} className="space-y-6" noValidate>
            {/* Role selector */}
            <fieldset>
              <legend className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Rol objetivo
              </legend>
              <div role="tablist" aria-label="Rol objetivo" className="flex flex-wrap gap-2">
                {(roles.length > 0 ? roles : Object.keys(ROLE_LABELS)).map((role) => (
                  <button
                    key={role}
                    type="button"
                    role="tab"
                    aria-selected={selectedRole === role}
                    onClick={() => setSelectedRole(role)}
                    className={`text-sm px-4 py-1.5 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                      selectedRole === role
                        ? "bg-blue-600 border-blue-600 text-white"
                        : "bg-transparent border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200"
                    }`}
                  >
                    {ROLE_LABELS[role] ?? role}
                  </button>
                ))}
              </div>
            </fieldset>

            {/* Input mode tabs */}
            <div>
              <div className="flex bg-slate-900 border border-slate-800 rounded-xl p-1 mb-4 w-fit gap-1">
                <button
                  type="button"
                  onClick={() => setInputMode("paste")}
                  className={`flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg transition-colors ${
                    inputMode === "paste" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                  }`}
                >
                  <ZapIcon className="w-3.5 h-3.5" /> Pegar texto
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode("url")}
                  className={`flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg transition-colors ${
                    inputMode === "url" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                  }`}
                >
                  <LinkIcon className="w-3.5 h-3.5" /> Importar por URL
                </button>
              </div>

              {inputMode === "paste" ? (
                <div>
                  <label htmlFor="profile-text" className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    Texto del perfil de LinkedIn
                  </label>
                  <p id="profile-text-hint" className="text-xs text-slate-500 mb-3">
                    Copiá todo el texto visible de tu perfil (título, extracto, experiencia, skills).
                  </p>
                  <textarea
                    id="profile-text"
                    value={profileText}
                    onChange={(e) => setProfileText(e.target.value)}
                    aria-describedby="profile-text-hint"
                    placeholder={"Juan Pérez\nAI Engineer | Python · LangChain · FastAPI\nBuenos Aires, Argentina\n\nSobre mí:\n..."}
                    rows={14}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
              ) : (
                <div>
                  <label htmlFor="linkedin-url" className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    URL de tu perfil de LinkedIn
                  </label>
                  <p className="text-xs text-slate-500 mb-3">
                    Tu perfil debe ser público. Si es privado, usá el modo "Pegar texto".
                  </p>
                  <div className="flex gap-2">
                    <input
                      id="linkedin-url"
                      type="url"
                      value={linkedinUrl}
                      onChange={(e) => setLinkedinUrl(e.target.value)}
                      placeholder="https://linkedin.com/in/tu-usuario"
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div role="alert" className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || (inputMode === "paste" ? !profileText.trim() : !linkedinUrl.trim())}
              aria-busy={loading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-medium text-sm transition-colors flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              {loading ? (
                <>
                  <RefreshCwIcon className="w-4 h-4 animate-spin" aria-hidden="true" />
                  {inputMode === "url" ? "Importando y analizando…" : "Analizando con IA…"}
                </>
              ) : (
                <>
                  <ZapIcon className="w-4 h-4" aria-hidden="true" />
                  {inputMode === "url" ? "Importar y analizar perfil" : "Analizar perfil"}
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

            {/* Rewrite CTA */}
            {!rewrite && (
              <div className="rounded-2xl border border-blue-800/40 bg-blue-950/20 p-6">
                <div className="flex items-start gap-4">
                  <SparklesIcon className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h2 className="text-sm font-semibold text-white mb-1">
                      Generar modificaciones listas para copiar
                    </h2>
                    <p className="text-xs text-slate-400 mb-4">
                      La IA reescribe cada sección de tu perfil — título, about, experiencia y skills —
                      optimizadas para el rol de {ROLE_LABELS[result.target_role] ?? result.target_role}.
                      Cada texto viene listo para pegar directamente en LinkedIn.
                    </p>
                    {rewriteError && (
                      <p className="text-xs text-red-400 mb-3">{rewriteError}</p>
                    )}
                    <button
                      onClick={handleRewrite}
                      disabled={rewriteLoading}
                      className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-sm font-medium text-white transition-colors"
                    >
                      {rewriteLoading ? (
                        <><Loader2Icon className="w-4 h-4 animate-spin" /> Generando...</>
                      ) : (
                        <><SparklesIcon className="w-4 h-4" /> Generar modificaciones por sección</>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Rewrite results */}
            {rewrite && (
              <section className="space-y-6">
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                  Modificaciones por sección — listas para copiar
                </h2>

                {rewrite.summary_of_changes && (
                  <div className="rounded-xl border border-blue-800/30 bg-blue-950/10 px-5 py-4">
                    <p className="text-xs text-blue-400 font-medium mb-1">Resumen de cambios</p>
                    <p className="text-sm text-slate-300">{rewrite.summary_of_changes}</p>
                  </div>
                )}

                {/* Title */}
                {rewrite.title && (
                  <div className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Título / Headline</p>
                      <CopyButton text={rewrite.title.rewrite} />
                    </div>
                    <p className="text-sm text-white font-medium">{rewrite.title.rewrite}</p>
                    <p className="text-xs text-slate-500">{rewrite.title.rationale}</p>
                  </div>
                )}

                {/* About */}
                {rewrite.about && (
                  <div className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Extracto (About)</p>
                      <CopyButton text={rewrite.about.rewrite} />
                    </div>
                    <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">{rewrite.about.rewrite}</p>
                    <p className="text-xs text-slate-500">{rewrite.about.rationale}</p>
                  </div>
                )}

                {/* Experience */}
                {rewrite.experience && rewrite.experience.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Experiencia — bullets optimizados</p>
                    {rewrite.experience.map((exp, i) => (
                      <div key={i} className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium text-slate-200">{exp.company}</p>
                          <CopyButton text={exp.bullets.map((b) => `• ${b}`).join("\n")} />
                        </div>
                        <ul className="space-y-2">
                          {exp.bullets.map((bullet, j) => (
                            <li key={j} className="flex gap-2 text-sm text-slate-300">
                              <span className="text-blue-500 shrink-0 mt-0.5">•</span>
                              <span>{bullet}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}

                {/* Skills */}
                {rewrite.skills && (
                  <div className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Skills</p>
                      <CopyButton text={rewrite.skills.rewrite.join(", ")} />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {rewrite.skills.rewrite.map((skill) => (
                        <span key={skill} className="text-xs px-3 py-1.5 rounded-full border border-blue-800/40 bg-blue-950/20 text-blue-300">
                          {skill}
                        </span>
                      ))}
                    </div>
                    <p className="text-xs text-slate-500">{rewrite.skills.rationale}</p>
                  </div>
                )}
              </section>
            )}

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={() => { setResult(null); setRewrite(null); setFetchedProfileText(""); }}
                className="flex-1 py-2.5 border border-slate-700 hover:border-slate-500 rounded-xl text-sm text-slate-400 hover:text-slate-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                Analizar otro perfil
              </button>
              <button
                onClick={() => window.print()}
                aria-label="Exportar análisis como PDF"
                className="no-print flex items-center gap-2 px-4 py-2.5 border border-slate-700 hover:border-slate-500 rounded-xl text-sm text-slate-400 hover:text-slate-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <DownloadIcon className="w-4 h-4" aria-hidden="true" /> Exportar PDF
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
