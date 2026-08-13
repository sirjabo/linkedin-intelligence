"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { updateCandidate, ingestTextSource, rebuildProfile } from "@/lib/api-v2";
import { CheckIcon, ArrowRightIcon, ZapIcon, RefreshCwIcon, UserIcon, FileTextIcon, SparklesIcon } from "lucide-react";

const STEPS = ["Bienvenida", "Tu perfil", "Tu CV", "Procesando", "¡Listo!"];

const SOURCE_TYPES = [
  { value: "cv", label: "CV / Currículum" },
  { value: "linkedin", label: "LinkedIn (texto pegado)" },
  { value: "manual", label: "Texto libre" },
];

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2 justify-center mb-8">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
            i < current
              ? "bg-emerald-600 text-white"
              : i === current
              ? "bg-blue-600 text-white"
              : "bg-slate-800 text-slate-500"
          }`}>
            {i < current ? <CheckIcon size={13} /> : i + 1}
          </div>
          {i < STEPS.length - 1 && (
            <div className={`h-0.5 w-8 transition-all ${i < current ? "bg-emerald-600" : "bg-slate-800"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

export default function OnboardingPage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");

  // Step 1 — profile info
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [roles, setRoles] = useState("");

  // Step 2 — source
  const [sourceType, setSourceType] = useState("cv");
  const [rawText, setRawText] = useState("");

  // Step 3 — processing state
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    if (!isLoading && !token) { router.replace("/login"); return; }
    if (!isLoading && token && localStorage.getItem("li_onboarding_done")) {
      router.replace("/dashboard");
    }
  }, [token, isLoading, router]);

  async function handleProfileSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError("");
    try {
      await updateCandidate(token, {
        name: name.trim() || undefined,
        location: location.trim() || undefined,
        target_roles: roles ? roles.split(",").map((r) => r.trim()).filter(Boolean) : [],
      });
      setStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al guardar");
    }
  }

  async function handleSourceSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !rawText.trim()) return;
    setError("");
    setStep(3);
    setProcessing(true);
    try {
      await ingestTextSource(token, sourceType, rawText.trim());
      await rebuildProfile(token);
      setStep(4);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al procesar");
      setStep(2);
    } finally {
      setProcessing(false);
    }
  }

  function finish() {
    localStorage.setItem("li_onboarding_done", "1");
    router.push("/dashboard");
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <ZapIcon size={16} className="text-white" />
          </div>
          <span className="font-bold text-white">LinkedIn Intelligence</span>
        </div>

        <StepIndicator current={step} />

        {error && (
          <div className="mb-4 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {/* Step 0 — Welcome */}
        {step === 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
            <SparklesIcon size={40} className="mx-auto text-blue-400 mb-4" />
            <h1 className="text-2xl font-bold text-white mb-3">Bienvenido a LinkedIn Intelligence</h1>
            <p className="text-slate-400 leading-relaxed mb-6">
              Te vamos a ayudar a optimizar tu perfil para el mercado tech de Latam. En menos de 2 minutos vas a tener tu inteligencia de candidato lista.
            </p>
            <ul className="text-left space-y-3 mb-8">
              {[
                "Analizamos tu CV y LinkedIn con IA",
                "Encontramos los mejores trabajos para vos",
                "Generamos CVs y cartas personalizadas",
                "Te preparamos para cada entrevista",
              ].map((item, i) => (
                <li key={i} className="flex items-center gap-3 text-sm text-slate-300">
                  <CheckIcon size={15} className="text-emerald-400 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
            <button
              onClick={() => setStep(1)}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-xl font-semibold transition-colors"
            >
              Empezar <ArrowRightIcon size={16} />
            </button>
          </div>
        )}

        {/* Step 1 — Profile info */}
        {step === 1 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8">
            <UserIcon size={32} className="text-blue-400 mb-4" />
            <h2 className="text-xl font-bold text-white mb-1">¿Cómo te llamás?</h2>
            <p className="text-slate-400 text-sm mb-6">Completá tu información básica. Podés editarla después.</p>
            <form onSubmit={handleProfileSubmit} className="space-y-4">
              <div>
                <label className="text-xs text-slate-500 block mb-1">Nombre completo</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Juan García"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Ubicación</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Buenos Aires, Argentina"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Roles objetivo (separados por coma)</label>
                <input
                  type="text"
                  value={roles}
                  onChange={(e) => setRoles(e.target.value)}
                  placeholder="Data Engineer, ML Engineer"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="text-sm text-slate-400 hover:text-white transition-colors px-4 py-2.5"
                >
                  Saltar
                </button>
                <button
                  type="submit"
                  className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-2.5 rounded-xl font-semibold transition-colors text-sm"
                >
                  Continuar <ArrowRightIcon size={15} />
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Step 2 — Source */}
        {step === 2 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8">
            <FileTextIcon size={32} className="text-blue-400 mb-4" />
            <h2 className="text-xl font-bold text-white mb-1">Cargá tu CV o LinkedIn</h2>
            <p className="text-slate-400 text-sm mb-6">
              Pegá el texto de tu CV, tu perfil de LinkedIn, o cualquier descripción de tu experiencia.
            </p>
            <form onSubmit={handleSourceSubmit} className="space-y-4">
              <div>
                <label className="text-xs text-slate-500 block mb-1">Tipo de contenido</label>
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
                <label className="text-xs text-slate-500 block mb-1">Contenido</label>
                <textarea
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  rows={8}
                  placeholder="Pegá aquí el texto de tu CV, perfil de LinkedIn, o describí tu experiencia…"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 resize-none"
                />
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={finish}
                  className="text-sm text-slate-400 hover:text-white transition-colors px-4 py-2.5"
                >
                  Saltar
                </button>
                <button
                  type="submit"
                  disabled={!rawText.trim()}
                  className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-2.5 rounded-xl font-semibold transition-colors text-sm"
                >
                  Analizar con IA <ZapIcon size={15} />
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Step 3 — Processing */}
        {step === 3 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
            <RefreshCwIcon size={40} className={`mx-auto text-blue-400 mb-4 ${processing ? "animate-spin" : ""}`} />
            <h2 className="text-xl font-bold text-white mb-2">Analizando tu perfil…</h2>
            <p className="text-slate-400 text-sm">
              Nuestra IA está extrayendo tu experiencia, skills y logros. Esto puede tomar unos segundos.
            </p>
          </div>
        )}

        {/* Step 4 — Done */}
        {step === 4 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-600/20 border border-emerald-600/40 flex items-center justify-center mx-auto mb-4">
              <CheckIcon size={32} className="text-emerald-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">¡Tu perfil está listo!</h2>
            <p className="text-slate-400 text-sm mb-8">
              Ya podés empezar a buscar trabajos y generar postulaciones personalizadas.
            </p>
            <button
              onClick={finish}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-xl font-semibold transition-colors"
            >
              Ir al dashboard <ArrowRightIcon size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
