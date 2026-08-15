"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { updateCandidate, ingestTextSource, rebuildProfile } from "@/lib/api-v2";
import {
  CheckIcon,
  ArrowRightIcon,
  ZapIcon,
  RefreshCwIcon,
  UserIcon,
  FileTextIcon,
  SparklesIcon,
  BarChart2Icon,
  BriefcaseIcon,
  LinkedinIcon,
} from "lucide-react";

const STEPS = ["Bienvenida", "Tu perfil", "Tu CV", "Procesando", "¡Listo!"];

const ROLE_OPTIONS = [
  { value: "ai_engineer", label: "AI Engineer" },
  { value: "data_engineer", label: "Data Engineer" },
  { value: "analytics_engineer", label: "Analytics Engineer" },
  { value: "ml_engineer", label: "ML Engineer" },
  { value: "backend_engineer", label: "Backend Engineer" },
  { value: "frontend_engineer", label: "Frontend Engineer" },
  { value: "devops_engineer", label: "DevOps Engineer" },
  { value: "data_scientist", label: "Data Scientist" },
];

const SOURCE_TYPES = [
  { value: "cv", label: "CV / Currículum", icon: FileTextIcon },
  { value: "linkedin", label: "LinkedIn (texto pegado)", icon: LinkedinIcon },
  { value: "manual", label: "Descripción libre", icon: UserIcon },
];

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2 justify-center mb-8">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            title={label}
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
              i < current
                ? "bg-emerald-600 text-white"
                : i === current
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-500"
            }`}
          >
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
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);

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

  function toggleRole(role: string) {
    setSelectedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  }

  async function handleProfileSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError("");
    try {
      await updateCandidate(token, {
        name: name.trim() || undefined,
        location: location.trim() || undefined,
        target_roles: selectedRoles,
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
              Tu plataforma de inteligencia para el mercado tech. En 2 minutos configuramos tu perfil
              y empezás a recibir insights accionables.
            </p>
            <ul className="text-left space-y-3 mb-8">
              {[
                { icon: BarChart2Icon, text: "Skills radar: qué pide el mercado para tu rol" },
                { icon: ZapIcon, text: "Score de tu perfil de LinkedIn con recomendaciones IA" },
                { icon: BriefcaseIcon, text: "Match con ofertas y generación automática de CVs" },
                { icon: LinkedinIcon, text: "About Writer: tu sección 'Acerca de' optimizada con IA" },
              ].map(({ icon: Icon, text }, i) => (
                <li key={i} className="flex items-center gap-3 text-sm text-slate-300">
                  <div className="w-6 h-6 rounded-md bg-blue-600/20 flex items-center justify-center shrink-0">
                    <Icon size={13} className="text-blue-400" />
                  </div>
                  {text}
                </li>
              ))}
            </ul>
            <button
              onClick={() => setStep(1)}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-xl font-semibold transition-colors"
            >
              Empezar configuración <ArrowRightIcon size={16} />
            </button>
          </div>
        )}

        {/* Step 1 — Profile info */}
        {step === 1 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8">
            <UserIcon size={32} className="text-blue-400 mb-4" />
            <h2 className="text-xl font-bold text-white mb-1">Tu información básica</h2>
            <p className="text-slate-400 text-sm mb-6">Completá tu perfil para recibir contenido personalizado.</p>
            <form onSubmit={handleProfileSubmit} className="space-y-5">
              <div>
                <label className="text-xs text-slate-500 block mb-1.5">Nombre completo</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Juan García"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 transition-colors"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1.5">Ubicación</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Buenos Aires, Argentina"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 transition-colors"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-2">
                  Roles objetivo{" "}
                  <span className="text-slate-600 font-normal">(seleccioná uno o más)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {ROLE_OPTIONS.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleRole(value)}
                      className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                        selectedRoles.includes(value)
                          ? "bg-blue-600 border-blue-600 text-white"
                          : "bg-transparent border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-3 pt-1">
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
              La IA extrae tu experiencia, skills y logros automáticamente.
            </p>
            <form onSubmit={handleSourceSubmit} className="space-y-4">
              <div>
                <label className="text-xs text-slate-500 block mb-2">Tipo de contenido</label>
                <div className="flex gap-2">
                  {SOURCE_TYPES.map(({ value, label, icon: Icon }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setSourceType(value)}
                      className={`flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border transition-colors ${
                        sourceType === value
                          ? "bg-blue-600/20 border-blue-600 text-blue-300"
                          : "bg-transparent border-slate-700 text-slate-400 hover:border-slate-500"
                      }`}
                    >
                      <Icon size={12} /> {label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1.5">Contenido</label>
                <textarea
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  rows={9}
                  placeholder={
                    sourceType === "linkedin"
                      ? "Copiá todo el texto visible de tu perfil de LinkedIn: nombre, título, extracto, experiencia, skills..."
                      : sourceType === "cv"
                      ? "Pegá el texto de tu CV aquí (experiencia, educación, skills, logros)..."
                      : "Describí tu trayectoria: roles, años de experiencia, tecnologías, logros..."
                  }
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 resize-none transition-colors"
                />
                <p className="text-xs text-slate-600 mt-1 text-right">
                  {rawText.trim().split(/\s+/).filter(Boolean).length} palabras
                </p>
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
            <RefreshCwIcon
              size={40}
              className={`mx-auto text-blue-400 mb-4 ${processing ? "animate-spin" : ""}`}
            />
            <h2 className="text-xl font-bold text-white mb-2">Analizando tu perfil…</h2>
            <p className="text-slate-400 text-sm mb-6">
              La IA está extrayendo tu experiencia, skills y logros. Esto toma unos segundos.
            </p>
            <div className="space-y-2 text-left">
              {[
                "Extrayendo experiencia laboral",
                "Identificando skills técnicas",
                "Analizando logros y métricas",
                "Construyendo tu perfil de candidato",
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-3 text-sm text-slate-500">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" style={{ animationDelay: `${i * 200}ms` }} />
                  {step}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 4 — Done */}
        {step === 4 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-600/20 border border-emerald-600/40 flex items-center justify-center mx-auto mb-4">
              <CheckIcon size={32} className="text-emerald-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">¡Tu perfil está listo!</h2>
            <p className="text-slate-400 text-sm mb-6">
              Analizamos tu experiencia y construimos tu perfil inteligente.
            </p>
            <div className="space-y-2 mb-8 text-left">
              {[
                "Skills extraídas y categorizadas",
                "Perfil listo para match con ofertas",
                "Score de LinkedIn disponible",
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-slate-300">
                  <CheckIcon size={14} className="text-emerald-400 shrink-0" />
                  {item}
                </div>
              ))}
            </div>
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
