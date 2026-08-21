"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import {
  getApplication,
  generateCV,
  generateCoverLetter,
  addEvent,
  generateAnswers,
  updateApplication,
  startAgent,
  getAgentStatus,
  answerAgentField,
  previewAgent,
  submitAgent,
  getFitAnalysis,
  downloadCVUrl,
  type Application,
  type CVVersion,
  type CoverLetter,
  type ApplicationAnswer,
  type AgentSession,
  type AgentField,
  type FitAnalysis,
  type RequirementMatch,
} from "@/lib/api-v2";
import {
  ArrowLeftIcon,
  FileTextIcon,
  MailIcon,
  ZapIcon,
  CheckIcon,
  MessageSquareIcon,
  BrainIcon,
  ClipboardListIcon,
  CalendarIcon,
  StickyNoteIcon,
  SaveIcon,
  BotIcon,
  AlertTriangleIcon,
  RefreshCwIcon,
  SendIcon,
  DownloadIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  TargetIcon,
  ShieldAlertIcon,
} from "lucide-react";

const AGENT_STATUS_LABEL: Record<string, string> = {
  initializing: "Inicializando…",
  discovering: "Descubriendo formulario…",
  mapping: "Mapeando campos…",
  awaiting_human: "Esperando respuestas",
  ready_to_fill: "Listo para completar",
  filling: "Completando formulario…",
  paused: "Pausado",
  previewing: "Vista previa…",
  submitting: "Enviando…",
  submitted: "Enviado",
  failed: "Falló",
};

const AGENT_POLL_INTERVAL = 3000;

const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador",
  applied: "Postulado",
  phone_screen: "Entrevista inicial",
  interview: "Entrevista",
  offer: "Oferta",
  rejected: "Rechazado",
  withdrawn: "Retirado",
};

function ReadinessItem({ done, label }: { done: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${done ? "bg-emerald-600" : "bg-slate-700"}`}>
        {done && <CheckIcon size={10} className="text-white" />}
      </div>
      <span className={done ? "text-slate-300" : "text-slate-500"}>{label}</span>
    </div>
  );
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [app, setApp] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [genCV, setGenCV] = useState(false);
  const [genCL, setGenCL] = useState(false);
  const [markApplied, setMarkApplied] = useState(false);
  const [questions, setQuestions] = useState("");
  const [answers, setAnswers] = useState<ApplicationAnswer[]>([]);
  const [genAnswers, setGenAnswers] = useState(false);

  // Browser Agent state
  const [agentFormUrl, setAgentFormUrl] = useState("");
  const [agentSession, setAgentSession] = useState<AgentSession | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState("");
  const [fieldAnswers, setFieldAnswers] = useState<Record<string, string>>({});
  const [savingField, setSavingField] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [submitDone, setSubmitDone] = useState(false);

  // Sprint J: fit analysis for req-by-req breakdown
  const [fitAnalysis, setFitAnalysis] = useState<FitAnalysis | null>(null);
  const [cvDiffOpen, setCvDiffOpen] = useState(false);
  const [strategyOpen, setStrategyOpen] = useState(false);
  const [preSubmitOpen, setPreSubmitOpen] = useState(true);

  // Notes editing
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesSaved, setNotesSaved] = useState(false);

  // Follow-up date
  const [followUpDate, setFollowUpDate] = useState("");
  const [savingDate, setSavingDate] = useState(false);
  const [dateSaved, setDateSaved] = useState(false);

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token || !id) return;
    getApplication(token, id)
      .then((data) => {
        setApp(data);
        setNotes(data.notes ?? "");
        setFollowUpDate(data.follow_up_date ?? "");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // Sprint J: load fit analysis in background
    getFitAnalysis(token, id)
      .then(setFitAnalysis)
      .catch(() => null);
  }, [token, id]);

  async function handleGenerateCV() {
    if (!token || !id) return;
    setGenCV(true);
    setError("");
    try {
      const cv: CVVersion = await generateCV(token, id);
      setApp((prev) =>
        prev ? { ...prev, cv_versions: [...prev.cv_versions, cv] } : prev
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al generar CV");
    } finally {
      setGenCV(false);
    }
  }

  async function handleGenerateCoverLetter() {
    if (!token || !id) return;
    setGenCL(true);
    setError("");
    try {
      const cl: CoverLetter = await generateCoverLetter(token, id);
      setApp((prev) =>
        prev ? { ...prev, cover_letters: [...prev.cover_letters, cl] } : prev
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al generar carta");
    } finally {
      setGenCL(false);
    }
  }

  async function handleGenerateAnswers() {
    if (!token || !id) return;
    const qs = questions.split("\n").map((q) => q.trim()).filter(Boolean);
    if (qs.length === 0) return;
    setGenAnswers(true);
    setError("");
    try {
      const result = await generateAnswers(token, id, qs);
      setAnswers(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al generar respuestas");
    } finally {
      setGenAnswers(false);
    }
  }

  async function handleMarkApplied() {
    if (!token || !id) return;
    setMarkApplied(true);
    setError("");
    try {
      await addEvent(token, id, "applied");
      const updated = await getApplication(token, id);
      setApp(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setMarkApplied(false);
    }
  }

  async function handleSaveNotes() {
    if (!token || !id) return;
    setSavingNotes(true);
    setError("");
    try {
      const updated = await updateApplication(token, id, { notes: notes || null });
      setApp(updated);
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al guardar notas");
    } finally {
      setSavingNotes(false);
    }
  }

  async function handleSaveFollowUp() {
    if (!token || !id) return;
    setSavingDate(true);
    setError("");
    try {
      const updated = await updateApplication(token, id, { follow_up_date: followUpDate || null });
      setApp(updated);
      setDateSaved(true);
      setTimeout(() => setDateSaved(false), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al guardar fecha");
    } finally {
      setSavingDate(false);
    }
  }

  async function handleStartAgent() {
    if (!token || !id || !agentFormUrl.trim()) return;
    setAgentLoading(true);
    setAgentError("");
    setAgentSession(null);
    setFieldAnswers({});
    setSubmitDone(false);
    try {
      const session = await startAgent(token, id, agentFormUrl.trim());
      setAgentSession(session);
      pollAgentStatus();
    } catch (err: unknown) {
      setAgentError(err instanceof Error ? err.message : "Error al iniciar agente");
    } finally {
      setAgentLoading(false);
    }
  }

  function pollAgentStatus() {
    if (!token || !id) return;
    const interval = setInterval(async () => {
      try {
        const session = await getAgentStatus(token, id);
        setAgentSession(session);
        const terminal = ["awaiting_human", "ready_to_fill", "submitted", "failed"];
        if (terminal.includes(session.status)) {
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, AGENT_POLL_INTERVAL);
  }

  async function handleAnswerField(field: AgentField) {
    if (!token || !id) return;
    const value = fieldAnswers[field.id] ?? "";
    if (!value.trim()) return;
    setSavingField(field.id);
    setAgentError("");
    try {
      const session = await answerAgentField(token, id, field.id, value.trim());
      setAgentSession(session);
    } catch (err: unknown) {
      setAgentError(err instanceof Error ? err.message : "Error al guardar respuesta");
    } finally {
      setSavingField(null);
    }
  }

  async function handlePreview() {
    if (!token || !id) return;
    setPreviewing(true);
    setAgentError("");
    try {
      const session = await previewAgent(token, id);
      setAgentSession(session);
    } catch (err: unknown) {
      setAgentError(err instanceof Error ? err.message : "Error en vista previa");
    } finally {
      setPreviewing(false);
    }
  }

  async function handleConfirmSubmit() {
    if (!token || !id) return;
    setConfirming(true);
    setAgentError("");
    try {
      const session = await submitAgent(token, id, true);
      setAgentSession(session);
      if (session.status === "submitted") {
        setSubmitDone(true);
        await addEvent(token, id, "applied", "Enviado con agente");
        const updated = await getApplication(token, id);
        setApp(updated);
      }
    } catch (err: unknown) {
      setAgentError(err instanceof Error ? err.message : "Error al enviar");
    } finally {
      setConfirming(false);
    }
  }

  if (isLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center" role="status" aria-label="Cargando postulación">
        <div className="text-slate-400 animate-pulse" aria-hidden="true">Cargando…</div>
      </div>
    );
  }

  if (!app) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center" role="alert">
        <div className="text-red-400">{error || "Postulación no encontrada"}</div>
      </div>
    );
  }

  const latestCV = app.cv_versions[app.cv_versions.length - 1];
  const latestCL = app.cover_letters[app.cover_letters.length - 1];
  const hasStrategy = !!app.strategy;
  const hasAppliedEvent = app.events.some((e) => e.event_type === "applied");

  const readinessChecks = [
    { done: app.cv_versions.length > 0, label: "CV personalizado generado" },
    { done: app.cover_letters.length > 0, label: "Carta de presentación generada" },
    { done: hasStrategy, label: "Estrategia de postulación lista" },
    { done: hasAppliedEvent || app.status !== "draft", label: "Postulación enviada" },
  ];
  const readinessScore = readinessChecks.filter((c) => c.done).length;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href="/applications" aria-label="Volver a mis postulaciones" className="text-slate-400 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
            <ArrowLeftIcon size={20} aria-hidden="true" />
          </Link>
          <div className="flex-1">
            <h1 className="font-bold text-white">
              {app.job_title ?? "Postulación"}
              {app.job_company && <span className="text-slate-400 font-normal"> — {app.job_company}</span>}
            </h1>
            <p className="text-xs text-slate-500">
              Estado: <span className="text-slate-300">{STATUS_LABEL[app.status] ?? app.status}</span>
            </p>
          </div>
          {app.status === "draft" && (
            <button
              onClick={handleMarkApplied}
              disabled={markApplied}
              className="flex items-center gap-2 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-sm font-semibold transition-colors"
            >
              <CheckIcon size={14} />
              {markApplied ? "…" : "Marcar postulado"}
            </button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {error && (
          <div role="alert" className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {/* Readiness checklist */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
              <ClipboardListIcon size={16} className="text-blue-400" />
              Lista de preparación
            </h3>
            <span className="text-xs text-slate-500">{readinessScore}/{readinessChecks.length}</span>
          </div>
          <div className="space-y-2">
            {readinessChecks.map((check, i) => (
              <ReadinessItem key={i} done={check.done} label={check.label} />
            ))}
          </div>
          {readinessScore === readinessChecks.length && (
            <div className="mt-4 text-xs text-emerald-400 font-semibold">¡Listo para postularte!</div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleGenerateCV}
            disabled={genCV}
            aria-busy={genCV}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <FileTextIcon size={15} aria-hidden="true" />
            {genCV ? "Generando CV…" : app.cv_versions.length > 0 ? "Regenerar CV" : "Generar CV"}
          </button>
          {genCV && (
            <div className="w-full mt-1" role="status" aria-label="Generando CV personalizado">
              <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-1 bg-blue-500 rounded-full animate-progress" style={{ width: "100%" }} />
              </div>
              <p className="text-xs text-slate-500 mt-1">Personalizando CV para esta posición…</p>
            </div>
          )}

          <button
            onClick={handleGenerateCoverLetter}
            disabled={genCL || !hasStrategy}
            aria-busy={genCL}
            aria-label={!hasStrategy ? "Generar carta de presentación (generá el CV primero)" : "Generar carta de presentación"}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <MailIcon size={15} aria-hidden="true" />
            {genCL ? "Generando carta…" : "Generar carta de presentación"}
          </button>

          <Link
            href={`/applications/${id}/interview-prep`}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <BrainIcon size={15} aria-hidden="true" />
            Preparación entrevista
          </Link>
        </div>

        {/* Browser Agent */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold text-slate-200 mb-1 flex items-center gap-2">
            <BotIcon size={16} className="text-blue-400" />
            Agente de postulación
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            El agente abre el formulario, lo completa con tu perfil y espera tu confirmación antes de enviarlo.
          </p>

          {agentError && (
            <div role="alert" className="mb-3 flex items-start gap-2 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2.5">
              <AlertTriangleIcon size={14} className="flex-shrink-0 mt-0.5" aria-hidden="true" />
              {agentError}
            </div>
          )}

          {/* Step 1: URL input */}
          {!agentSession && (
            <div className="flex gap-2">
              <input
                id="agent-form-url"
                type="url"
                value={agentFormUrl}
                onChange={(e) => setAgentFormUrl(e.target.value)}
                placeholder="https://jobs.greenhouse.io/…"
                aria-label="URL del formulario de postulación"
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500"
              />
              <button
                onClick={handleStartAgent}
                disabled={agentLoading || !agentFormUrl.trim()}
                aria-busy={agentLoading}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                {agentLoading ? (
                  <RefreshCwIcon size={14} className="animate-spin" aria-hidden="true" />
                ) : (
                  <BotIcon size={14} aria-hidden="true" />
                )}
                {agentLoading ? "Iniciando…" : "Iniciar agente"}
              </button>
            </div>
          )}

          {/* Session status */}
          {agentSession && !submitDone && (
            <div className="space-y-4">
              {/* Status bar */}
              <div className="flex items-center justify-between flex-wrap gap-2">
                <span className="text-sm font-medium text-slate-200">
                  {AGENT_STATUS_LABEL[agentSession.status] ?? agentSession.status}
                </span>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  <span>{agentSession.fields_auto_filled} auto · {agentSession.fields_human_pending} pendiente</span>
                  {agentSession.ats_name && (
                    <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-400">
                      {agentSession.ats_name}
                    </span>
                  )}
                </div>
              </div>

              {/* Polling spinner for in-progress states */}
              {["initializing", "discovering", "mapping", "filling", "previewing", "submitting"].includes(agentSession.status) && (
                <div role="status" aria-label="Agente procesando" className="flex items-center gap-2 text-slate-400 text-sm">
                  <RefreshCwIcon size={14} className="animate-spin" aria-hidden="true" />
                  <span>Procesando, no cierres esta página…</span>
                </div>
              )}

              {/* HUMAN_REQUIRED fields */}
              {agentSession.status === "awaiting_human" && agentSession.fields && (
                <div className="space-y-3">
                  <p className="text-xs text-slate-400">
                    Completá los campos que el agente no pudo resolver automáticamente:
                  </p>
                  {(agentSession.fields as AgentField[])
                    .filter((f) => f.human_required)
                    .map((field) => (
                    <div key={field.id} className="bg-slate-800 rounded-lg p-3">
                      <label htmlFor={`field-${field.id}`} className="text-xs font-medium text-slate-300 block mb-1.5">
                        {field.label}
                        {field.is_required && <span className="text-red-400 ml-1" aria-label="(requerido)">*</span>}
                      </label>
                      {field.options && field.options.length > 0 ? (
                        <select
                          id={`field-${field.id}`}
                          value={fieldAnswers[field.id] ?? field.human_answer ?? ""}
                          onChange={(e) => setFieldAnswers((prev) => ({ ...prev, [field.id]: e.target.value }))}
                          className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500"
                        >
                          <option value="">Seleccioná…</option>
                          {field.options.map((opt) => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          id={`field-${field.id}`}
                          type="text"
                          value={fieldAnswers[field.id] ?? field.human_answer ?? ""}
                          onChange={(e) => setFieldAnswers((prev) => ({ ...prev, [field.id]: e.target.value }))}
                          placeholder={field.auto_fill_value ? `Sugerido: ${field.auto_fill_value}` : "Tu respuesta…"}
                          className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500"
                        />
                      )}
                      <div className="mt-2 flex items-center justify-between gap-2">
                        {field.auto_fill_value && !fieldAnswers[field.id] && (
                          <button
                            type="button"
                            onClick={() => setFieldAnswers((prev) => ({ ...prev, [field.id]: field.auto_fill_value! }))}
                            className="text-xs text-blue-400 hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                          >
                            Usar sugerencia
                          </button>
                        )}
                        <span />
                        <button
                          onClick={() => handleAnswerField(field)}
                          disabled={savingField === field.id || !fieldAnswers[field.id]?.trim()}
                          aria-busy={savingField === field.id}
                          className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                        >
                          {savingField === field.id ? (
                            <RefreshCwIcon size={11} className="animate-spin" aria-hidden="true" />
                          ) : (
                            <CheckIcon size={11} aria-hidden="true" />
                          )}
                          Guardar
                        </button>
                      </div>
                      {field.human_answer && (
                        <p className="text-xs text-emerald-400 mt-1">
                          Guardado: {field.human_answer}
                        </p>
                      )}
                    </div>
                  ))}

                  <button
                    onClick={handlePreview}
                    disabled={previewing}
                    aria-busy={previewing}
                    className="w-full flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 py-2 rounded-lg text-sm font-semibold transition-colors mt-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    {previewing ? (
                      <RefreshCwIcon size={14} className="animate-spin" aria-hidden="true" />
                    ) : (
                      <ZapIcon size={14} aria-hidden="true" />
                    )}
                    {previewing ? "Procesando…" : "Completar formulario"}
                  </button>
                </div>
              )}

              {/* Ready to fill / preview */}
              {(agentSession.status === "ready_to_fill" || agentSession.confirmation_id) && !submitDone && (
                <div className="space-y-3">
                  <div className="bg-yellow-900/20 border border-yellow-800 rounded-lg px-4 py-3">
                    <p className="text-sm font-semibold text-yellow-300 mb-1 flex items-center gap-2">
                      <AlertTriangleIcon size={14} />
                      Confirmación requerida
                    </p>
                    <p className="text-xs text-yellow-200/70">
                      El agente completó el formulario y está esperando tu aprobación explícita para enviarlo.
                      Revisá los datos antes de confirmar.
                    </p>
                    {agentSession.avg_confidence != null && (
                      <p className="text-xs text-yellow-300 mt-1.5">
                        Confianza promedio: {Math.round(agentSession.avg_confidence * 100)}%
                      </p>
                    )}
                  </div>

                  {/* Pre-submit field review */}
                  {agentSession.fields && (agentSession.fields as AgentField[]).length > 0 && (
                    <div className="border border-slate-700 rounded-lg overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setPreSubmitOpen((v) => !v)}
                        className="w-full flex items-center justify-between px-3 py-2 bg-slate-800 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                        aria-expanded={preSubmitOpen}
                      >
                        <span>Revisá los datos a enviar ({(agentSession.fields as AgentField[]).length} campos)</span>
                        {preSubmitOpen
                          ? <ChevronUpIcon size={13} aria-hidden="true" />
                          : <ChevronDownIcon size={13} aria-hidden="true" />}
                      </button>
                      {preSubmitOpen && (
                        <ul className="divide-y divide-slate-800 max-h-64 overflow-y-auto" role="list">
                          {(agentSession.fields as AgentField[]).map((field) => {
                            const effectiveValue = field.human_answer ?? field.auto_fill_value ?? "";
                            const isHuman = Boolean(field.human_answer);
                            return (
                              <li key={field.id} className="flex items-start gap-2 px-3 py-2 text-xs">
                                <span className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${isHuman ? "bg-yellow-400" : "bg-emerald-500"}`} aria-hidden="true" />
                                <div className="min-w-0">
                                  <p className="text-slate-400 truncate">{field.label}</p>
                                  <p className="text-slate-200 break-words">{effectiveValue || <span className="italic text-slate-600">vacío</span>}</p>
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                      <p className="text-xs text-slate-600 px-3 py-1.5 bg-slate-900">
                        <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1" aria-hidden="true" />auto ·
                        <span className="inline-block w-2 h-2 rounded-full bg-yellow-400 mx-1" aria-hidden="true" />revisado por vos
                      </p>
                    </div>
                  )}

                  <button
                    onClick={handleConfirmSubmit}
                    disabled={confirming}
                    aria-busy={confirming}
                    className="w-full flex items-center justify-center gap-2 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 py-2.5 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                  >
                    {confirming ? (
                      <RefreshCwIcon size={14} className="animate-spin" aria-hidden="true" />
                    ) : (
                      <SendIcon size={14} aria-hidden="true" />
                    )}
                    {confirming ? "Enviando…" : "Confirmar y enviar postulación"}
                  </button>
                </div>
              )}

              {/* Error state */}
              {agentSession.status === "failed" && agentSession.error_message && (
                <div role="alert" className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
                  {agentSession.error_message}
                </div>
              )}

              {/* Reset */}
              {["failed", "submitted"].includes(agentSession.status) && (
                <button
                  onClick={() => { setAgentSession(null); setAgentFormUrl(""); setFieldAnswers({}); }}
                  className="text-xs text-slate-500 hover:text-slate-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                >
                  Iniciar nueva sesión
                </button>
              )}
            </div>
          )}

          {/* Submitted */}
          {submitDone && (
            <div role="status" className="flex items-center gap-2 text-emerald-400 text-sm font-semibold">
              <CheckIcon size={16} aria-hidden="true" />
              ¡Postulación enviada exitosamente!
            </div>
          )}
        </div>

        {/* Notes + Follow-up date */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <StickyNoteIcon size={16} className="text-blue-400" aria-hidden="true" />
              Notas personales
            </h3>
            <label htmlFor="app-notes" className="sr-only">Notas personales</label>
            <textarea
              id="app-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              placeholder="Contacto de referencia, comentarios de la entrevista…"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 resize-none mb-3"
            />
            <button
              onClick={handleSaveNotes}
              disabled={savingNotes}
              aria-busy={savingNotes}
              className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <SaveIcon size={12} aria-hidden="true" />
              {notesSaved ? "¡Guardado!" : savingNotes ? "Guardando…" : "Guardar notas"}
            </button>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <CalendarIcon size={16} className="text-blue-400" aria-hidden="true" />
              Fecha de seguimiento
            </h3>
            <p id="follow-up-hint" className="text-xs text-slate-500 mb-3">
              Recordatorio para hacer follow-up si no recibiste respuesta.
            </p>
            <label htmlFor="app-follow-up-date" className="sr-only">Fecha de seguimiento</label>
            <input
              id="app-follow-up-date"
              type="date"
              value={followUpDate}
              onChange={(e) => setFollowUpDate(e.target.value)}
              aria-describedby="follow-up-hint"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 mb-3 [color-scheme:dark]"
            />
            <button
              onClick={handleSaveFollowUp}
              disabled={savingDate}
              aria-busy={savingDate}
              className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <SaveIcon size={12} aria-hidden="true" />
              {dateSaved ? "¡Guardado!" : savingDate ? "Guardando…" : "Guardar fecha"}
            </button>
          </div>
        </div>

        {/* Sprint J: Strategy panel (full Sprint E fields) */}
        {app.strategy && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <button
              className="w-full flex items-center justify-between focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
              onClick={() => setStrategyOpen((v) => !v)}
              aria-expanded={strategyOpen}
            >
              <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <ZapIcon size={16} className="text-blue-400" aria-hidden="true" />
                Estrategia de postulación
              </h3>
              {strategyOpen ? <ChevronUpIcon size={16} className="text-slate-400" aria-hidden="true" /> : <ChevronDownIcon size={16} className="text-slate-400" aria-hidden="true" />}
            </button>

            {strategyOpen && (() => {
              const s = app.strategy as Record<string, unknown>;
              return (
                <div className="mt-4 space-y-4 text-sm">
                  {Boolean(s.positioning) && (
                    <div>
                      <p className="text-xs font-semibold text-blue-400 mb-1 uppercase tracking-wider">Posicionamiento</p>
                      <p className="text-slate-300 leading-relaxed">{String(s.positioning)}</p>
                    </div>
                  )}
                  {Boolean(s.target_narrative) && (
                    <div>
                      <p className="text-xs font-semibold text-blue-400 mb-1 uppercase tracking-wider">Narrativa objetivo</p>
                      <p className="text-slate-300 leading-relaxed">{String(s.target_narrative)}</p>
                    </div>
                  )}
                  {Boolean(s.overall_approach) && (
                    <div>
                      <p className="text-xs font-semibold text-slate-500 mb-1 uppercase tracking-wider">Enfoque general</p>
                      <p className="text-slate-400 leading-relaxed">{String(s.overall_approach)}</p>
                    </div>
                  )}
                  {Array.isArray(s.keywords_for_form) && s.keywords_for_form.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-blue-400 mb-2 uppercase tracking-wider">Keywords para formularios</p>
                      <div className="flex flex-wrap gap-1.5">
                        {(s.keywords_for_form as string[]).map((kw) => (
                          <span key={kw} className="bg-blue-900/40 border border-blue-800/40 text-blue-300 px-2 py-0.5 rounded text-xs font-mono">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {Array.isArray(s.interview_preparation_strategy) && s.interview_preparation_strategy.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-blue-400 mb-2 uppercase tracking-wider">Preparación para entrevistas</p>
                      <ul className="space-y-1.5">
                        {(s.interview_preparation_strategy as string[]).map((tip, i) => (
                          <li key={i} className="flex gap-2 text-slate-300">
                            <span className="text-blue-400 flex-shrink-0">·</span>
                            {tip}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {Array.isArray(s.claims_to_avoid) && s.claims_to_avoid.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-red-400 mb-2 uppercase tracking-wider flex items-center gap-1">
                        <ShieldAlertIcon size={11} />
                        No mencionar en entrevistas
                      </p>
                      <ul className="space-y-1">
                        {(s.claims_to_avoid as string[]).map((c, i) => (
                          <li key={i} className="text-red-400/80 text-xs flex gap-2">
                            <span className="flex-shrink-0">✗</span>{c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {Boolean(s.company_specific_angle) && (
                    <div>
                      <p className="text-xs font-semibold text-emerald-400 mb-1 uppercase tracking-wider">Ángulo empresa</p>
                      <p className="text-slate-300 leading-relaxed">{String(s.company_specific_angle)}</p>
                    </div>
                  )}
                  {Array.isArray(s.strengths_to_emphasize) && s.strengths_to_emphasize.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-emerald-400 mb-2 uppercase tracking-wider">Fortalezas a destacar</p>
                      <ul className="space-y-1">
                        {(s.strengths_to_emphasize as string[]).map((st, i) => (
                          <li key={i} className="text-emerald-300/80 text-xs flex gap-2">
                            <span className="flex-shrink-0">✓</span>{st}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {Array.isArray(s.risks_to_address) && s.risks_to_address.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-yellow-400 mb-2 uppercase tracking-wider">Riesgos a abordar</p>
                      <ul className="space-y-1">
                        {(s.risks_to_address as string[]).map((r, i) => (
                          <li key={i} className="text-yellow-300/80 text-xs flex gap-2">
                            <span className="flex-shrink-0">!</span>{r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        {/* Sprint J: Requirement-by-requirement match breakdown */}
        {fitAnalysis && fitAnalysis.requirement_matches && fitAnalysis.requirement_matches.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <TargetIcon size={16} className="text-blue-400" />
              Análisis de requisitos
            </h3>
            <ul className="space-y-2">
              {fitAnalysis.requirement_matches.map((rm: RequirementMatch, i: number) => {
                const statusColors: Record<string, string> = {
                  MATCHED: "bg-emerald-900/40 border-emerald-800/40 text-emerald-300",
                  PARTIAL: "bg-yellow-900/40 border-yellow-800/40 text-yellow-300",
                  MISSING: "bg-slate-800 border-slate-700 text-slate-400",
                  BLOCKER: "bg-red-900/40 border-red-800/40 text-red-300",
                  UNCERTAIN: "bg-blue-900/40 border-blue-800/40 text-blue-300",
                };
                const statusLabel: Record<string, string> = {
                  MATCHED: "Cubierto", PARTIAL: "Parcial",
                  MISSING: "Faltante", BLOCKER: "Bloqueante", UNCERTAIN: "Incierto",
                };
                const cls = statusColors[rm.candidate_status] ?? "bg-slate-800 border-slate-700 text-slate-400";
                return (
                  <li key={i} className="flex items-start gap-3">
                    <span className={`text-xs px-2 py-0.5 rounded border flex-shrink-0 font-mono mt-0.5 ${cls}`}>
                      {statusLabel[rm.candidate_status] ?? rm.candidate_status}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-300 leading-snug">{rm.text}</p>
                      <p className="text-xs text-slate-600 mt-0.5">
                        {rm.importance === "MUST" ? "Obligatorio" : "Deseable"} · {Math.round(rm.match_score * 100)}%
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Sprint J: Latest CV with diff view + download */}
        {latestCV && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <FileTextIcon size={16} className="text-blue-400" />
                CV Personalizado
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCvDiffOpen((v) => !v)}
                  aria-expanded={cvDiffOpen}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                >
                  {cvDiffOpen ? <ChevronUpIcon size={13} aria-hidden="true" /> : <ChevronDownIcon size={13} aria-hidden="true" />}
                  {cvDiffOpen ? "Ocultar cambios" : "Ver cambios"}
                </button>
                <a
                  href={`${downloadCVUrl(id)}?token=${token}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Descargar CV personalizado como PDF (abre en nueva pestaña)"
                  className="flex items-center gap-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                >
                  <DownloadIcon size={11} aria-hidden="true" />
                  PDF
                </a>
              </div>
            </div>

            {latestCV.headline_adapted && (
              <p className="text-blue-300 font-medium mb-2">{latestCV.headline_adapted}</p>
            )}
            {latestCV.summary_adapted && (
              <p className="text-sm text-slate-300 leading-relaxed">{latestCV.summary_adapted}</p>
            )}
            {latestCV.ats_keywords && latestCV.ats_keywords.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {latestCV.ats_keywords.map((kw) => (
                  <span key={kw} className="bg-slate-800 text-slate-400 text-xs px-1.5 py-0.5 rounded font-mono">{kw}</span>
                ))}
              </div>
            )}

            {/* Sprint J: CV Diff View */}
            {cvDiffOpen && latestCV.experience_personalized && latestCV.experience_personalized.length > 0 && (
              <div className="mt-4 space-y-4 border-t border-slate-800 pt-4">
                <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Bullets adaptados por experiencia</p>
                {latestCV.experience_personalized.map((ep, ei) => (
                  <div key={ei} className="space-y-2">
                    <p className="text-xs font-semibold text-slate-300">{ep.title} @ {ep.company}</p>
                    {ep.bullets_adapted.map((bc, bi) => (
                      <div key={bi} className="bg-slate-800/50 rounded-lg p-3 text-xs space-y-1.5 border border-slate-700/50">
                        <div className="flex gap-2">
                          <span className="text-red-400/70 flex-shrink-0">−</span>
                          <span className="text-slate-500 line-through">{bc.original}</span>
                        </div>
                        <div className="flex gap-2">
                          <span className="text-emerald-400 flex-shrink-0">+</span>
                          <span className="text-slate-300">{bc.adapted}</span>
                        </div>
                        {bc.reason && (
                          <p className="text-slate-600 italic pl-4">{bc.reason}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}

            {Array.isArray(latestCV.changes) && latestCV.changes.length > 0 && !cvDiffOpen && (
              <div className="mt-3 pt-3 border-t border-slate-800">
                <p className="text-xs text-slate-500 mb-2">{latestCV.changes.length} cambio(s) sugerido(s)</p>
              </div>
            )}
          </div>
        )}

        {/* Latest Cover Letter */}
        {latestCL && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <MailIcon size={16} className="text-blue-400" />
              Carta de Presentación
            </h3>
            <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
              {latestCL.content}
            </div>
          </div>
        )}

        {/* Sprint J: Submission evidence panel */}
        {app.status === "applied" && agentSession?.status === "submitted" && (
          <div className="bg-slate-900 border border-emerald-900/40 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <CheckIcon size={16} className="text-emerald-400" />
              Evidencia de postulación
            </h3>
            {agentSession.confirmation_id && (
              <p className="text-xs text-slate-400 mb-2">
                ID de confirmación: <span className="font-mono text-slate-200">{agentSession.confirmation_id}</span>
              </p>
            )}
            {agentSession.final_url && (
              <p className="text-xs text-slate-400 mb-3">
                URL final: <span className="font-mono text-blue-400">{agentSession.final_url}</span>
              </p>
            )}
            <p className="text-xs text-slate-500">
              {agentSession.fields_confirmed} campo(s) completados · ATS: {agentSession.ats_name ?? "genérico"}
            </p>
          </div>
        )}

        {/* Application answers */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <MessageSquareIcon size={16} className="text-blue-400" aria-hidden="true" />
            Preguntas de la empresa
          </h3>
          <p id="questions-hint" className="text-xs text-slate-500 mb-3">Pegá las preguntas del formulario, una por línea.</p>
          <label htmlFor="app-questions" className="sr-only">Preguntas del formulario</label>
          <textarea
            id="app-questions"
            value={questions}
            onChange={(e) => setQuestions(e.target.value)}
            rows={4}
            placeholder={"¿Por qué querés trabajar en esta empresa?\n¿Cuál es tu mayor fortaleza?\n…"}
            aria-describedby="questions-hint"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 resize-none mb-3"
          />
          <button
            onClick={handleGenerateAnswers}
            disabled={genAnswers || !questions.trim()}
            aria-busy={genAnswers}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <ZapIcon size={14} aria-hidden="true" />
            {genAnswers ? "Generando…" : "Generar respuestas"}
          </button>
          {answers.length > 0 && (
            <div className="mt-5 space-y-5">
              {answers.map((a, i) => (
                <div key={a.id ?? i}>
                  <p className="text-sm font-medium text-slate-300 mb-1">{i + 1}. {a.question}</p>
                  <p className="text-sm text-slate-400 leading-relaxed whitespace-pre-line border-l-2 border-blue-600/40 pl-3">{a.answer}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Events timeline */}
        {app.events.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-4">Historial</h3>
            <ul className="space-y-3">
              {app.events.map((ev) => (
                <li key={ev.id} className="flex gap-3 items-start">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-1.5 flex-shrink-0" aria-hidden="true" />
                  <div>
                    <p className="text-sm text-slate-300 font-medium capitalize">{ev.event_type}</p>
                    {ev.notes && <p className="text-xs text-slate-500 mt-0.5">{ev.notes}</p>}
                    <time dateTime={ev.occurred_at} className="text-xs text-slate-600 mt-0.5 block">
                      {new Date(ev.occurred_at).toLocaleString("es-AR")}
                    </time>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}
