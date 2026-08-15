"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/lib/auth";
import { generateAbout, type AboutVariant } from "@/lib/api-v2";
import {
  ArrowLeftIcon,
  RefreshCwIcon,
  ZapIcon,
  CheckIcon,
  ClipboardCopyIcon,
  LightbulbIcon,
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

const TONE_COLOR: Record<string, string> = {
  "1": "border-blue-800/40 bg-blue-950/20",
  "2": "border-emerald-800/40 bg-emerald-950/20",
  "3": "border-purple-800/40 bg-purple-950/20",
};

function VariantCard({ variant, index }: { variant: AboutVariant; index: number }) {
  const [copied, setCopied] = useState(false);
  const colorClass = TONE_COLOR[String(variant.id)] ?? "border-slate-800 bg-slate-900";

  const copy = () => {
    navigator.clipboard.writeText(variant.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`rounded-xl border px-5 py-4 ${colorClass}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-mono">#{index + 1}</span>
          <span className="text-xs text-slate-400 bg-white/5 px-2 py-0.5 rounded-full border border-white/10">
            {variant.tone}
          </span>
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-2 py-1 rounded-lg hover:bg-white/5"
        >
          {copied ? (
            <><CheckIcon className="w-3.5 h-3.5 text-emerald-400" /> Copiado</>
          ) : (
            <><ClipboardCopyIcon className="w-3.5 h-3.5" /> Copiar</>
          )}
        </button>
      </div>
      <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{variant.text}</p>
      <p className="text-xs text-slate-600 mt-3 text-right">{variant.text.split(" ").length} palabras</p>
    </div>
  );
}

export default function AboutWriterPage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [selectedRole, setSelectedRole] = useState("ai_engineer");
  const [profileSummary, setProfileSummary] = useState("");
  const [currentAbout, setCurrentAbout] = useState("");
  const [skills, setSkills] = useState("");
  const [achievements, setAchievements] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ variants: AboutVariant[]; tips: string[] } | null>(null);

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !profileSummary.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await generateAbout(
        token,
        selectedRole,
        profileSummary.trim(),
        currentAbout.trim() || undefined,
        skills.trim() ? skills.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        achievements.trim() ? achievements.split("\n").map((s) => s.trim()).filter(Boolean) : undefined,
      );
      setResult({ variants: data.variants, tips: data.tips });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al generar el About");
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
          href="/analyze"
          className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-300 text-sm mb-10 transition-colors"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" /> Volver al analizador
        </Link>

        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-purple-600/20 flex items-center justify-center">
            <ZapIcon className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">About Writer</h1>
            <p className="text-sm text-slate-500">
              Generá 3 variantes optimizadas de tu sección "Acerca de" en LinkedIn
            </p>
          </div>
        </div>

        {!result ? (
          <form onSubmit={handleGenerate} className="space-y-6">
            {/* Role */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Rol objetivo
              </label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(ROLE_LABELS).map(([role, label]) => (
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
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Profile summary — required */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Resumen de tu experiencia <span className="text-red-400">*</span>
              </label>
              <p className="text-xs text-slate-500 mb-2">
                Describí tu trayectoria: años de experiencia, tecnologías principales, logros destacados. No hace falta que sea perfecto — la IA lo transforma.
              </p>
              <textarea
                value={profileSummary}
                onChange={(e) => setProfileSummary(e.target.value)}
                placeholder="Ej: 5 años como desarrollador Python, trabajé en startups fintech construyendo APIs con FastAPI y LangChain. Lideré migración a microservicios que redujo latencia 40%..."
                rows={6}
                required
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Current About — optional */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                About actual (opcional)
              </label>
              <textarea
                value={currentAbout}
                onChange={(e) => setCurrentAbout(e.target.value)}
                placeholder="Pegá tu sección About actual si querés que la IA la tome como base y la mejore…"
                rows={4}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Skills — optional */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Skills clave (opcional, separadas por coma)
              </label>
              <input
                type="text"
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                placeholder="Python, LangChain, FastAPI, PostgreSQL, Docker…"
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Achievements — optional */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Logros destacados (opcional, uno por línea)
              </label>
              <textarea
                value={achievements}
                onChange={(e) => setAchievements(e.target.value)}
                placeholder="Reduje el tiempo de respuesta de la API en 60%&#10;Lideré equipo de 4 ingenieros&#10;Implementé sistema RAG con 95% de accuracy"
                rows={3}
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
              disabled={loading || !profileSummary.trim()}
              className="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-medium text-sm transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <><RefreshCwIcon className="w-4 h-4 animate-spin" /> Generando variantes…</>
              ) : (
                <><ZapIcon className="w-4 h-4" /> Generar 3 variantes del About</>
              )}
            </button>
          </form>
        ) : (
          <div className="space-y-6">
            {/* Tips */}
            {result.tips.length > 0 && (
              <div className="bg-yellow-950/20 border border-yellow-800/30 rounded-xl px-5 py-4">
                <div className="flex items-center gap-2 mb-2.5">
                  <LightbulbIcon className="w-4 h-4 text-yellow-400" />
                  <span className="text-xs font-semibold text-yellow-400 uppercase tracking-wider">Tips adicionales</span>
                </div>
                <ul className="space-y-1.5">
                  {result.tips.map((tip, i) => (
                    <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                      <span className="text-yellow-500 mt-0.5 shrink-0">▸</span>
                      {tip}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Variants */}
            <div className="space-y-4">
              {result.variants.map((v, i) => (
                <VariantCard key={v.id} variant={v} index={i} />
              ))}
            </div>

            <button
              onClick={() => setResult(null)}
              className="w-full py-2.5 border border-slate-700 hover:border-slate-500 rounded-xl text-sm text-slate-400 hover:text-slate-200 transition-colors"
            >
              Generar nuevas variantes
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
