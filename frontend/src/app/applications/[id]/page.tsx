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
  type Application,
  type CVVersion,
  type CoverLetter,
  type ApplicationAnswer,
  type AgentSession,
  type AgentField,
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
} from "lucide-react";

const AGENT_STATUS_LABEL: Record<string, string> = {
  initializing: "Inicializando…",
  discovering: "Descubriendo formulario…",
  mapping: "Mapeando campos…",
  awaiting_human: "Esperando respuestas",
  ready_to_fill: "Listo para completar",
  filling: "Completando formulario…",
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
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando…</div>
      </div>
    );
  }

  if (!app) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
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
          <Link href="/applications" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeftIcon size={20} />
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
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
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
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            <FileTextIcon size={15} />
            {genCV ? "Generando CV…" : app.cv_versions.length > 0 ? "Regenerar CV" : "Generar CV"}
          </button>

          <button
            onClick={handleGenerateCoverLetter}
            disabled={genCL || !hasStrategy}
            title={!hasStrategy ? "Generá el CV primero" : ""}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            <MailIcon size={15} />
            {genCL ? "Generando carta…" : "Generar carta de presentación"}
          </button>

          <Link
            href={`/applications/${id}/interview-prep`}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            <BrainIcon size={15} />
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
            <div className="mb-3 flex items-start gap-2 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2.5">
              <AlertTriangleIcon size={14} className="flex-shrink-0 mt-0.5" />
              {agentError}
            </div>
          )}

          {/* Step 1: URL input */}
          {!agentSession && (
            <div className="flex gap-2">
              <input
                type="url"
                value={agentFormUrl}
                onChange={(e) => setAgentFormUrl(e.target.value)}
                placeholder="https://jobs.greenhouse.io/…"
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
              />
              <button
                onClick={handleStartAgent}
                disabled={agentLoading || !agentFormUrl.trim()}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              >
                {agentLoading ? (
                  <RefreshCwIcon size={14} className="animate-spin" />
                ) : (
                  <BotIcon size={14} />
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
                <div className="flex items-center gap-2 text-slate-400 text-sm">
                  <RefreshCwIcon size={14} className="animate-spin" />
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
                      <label className="text-xs font-medium text-slate-300 block mb-1.5">
                        {field.label}
                        {field.is_required && <span className="text-red-400 ml-1">*</span>}
                      </label>
                      {field.options && field.options.length > 0 ? (
                        <select
                          value={fieldAnswers[field.id] ?? field.human_answer ?? ""}
                          onChange={(e) => setFieldAnswers((prev) => ({ ...prev, [field.id]: e.target.value }))}
                          className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-600"
                        >
                          <option value="">Seleccioná…</option>
                          {field.options.map((opt) => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={fieldAnswers[field.id] ?? field.human_answer ?? ""}
                          onChange={(e) => setFieldAnswers((prev) => ({ ...prev, [field.id]: e.target.value }))}
                          placeholder={field.auto_fill_value ? `Sugerido: ${field.auto_fill_value}` : "Tu respuesta…"}
                          className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
                        />
                      )}
                      <div className="mt-2 flex items-center justify-between gap-2">
                        {field.auto_fill_value && !fieldAnswers[field.id] && (
                          <button
                            type="button"
                            onClick={() => setFieldAnswers((prev) => ({ ...prev, [field.id]: field.auto_fill_value! }))}
                            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                          >
                            Usar sugerencia
                          </button>
                        )}
                        <span />
                        <button
                          onClick={() => handleAnswerField(field)}
                          disabled={savingField === field.id || !fieldAnswers[field.id]?.trim()}
                          className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1 rounded transition-colors"
                        >
                          {savingField === field.id ? (
                            <RefreshCwIcon size={11} className="animate-spin" />
                          ) : (
                            <CheckIcon size={11} />
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
                    className="w-full flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 py-2 rounded-lg text-sm font-semibold transition-colors mt-2"
                  >
                    {previewing ? (
                      <RefreshCwIcon size={14} className="animate-spin" />
                    ) : (
                      <ZapIcon size={14} />
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

                  <button
                    onClick={handleConfirmSubmit}
                    disabled={confirming}
                    className="w-full flex items-center justify-center gap-2 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 py-2.5 rounded-lg text-sm font-semibold transition-colors"
                  >
                    {confirming ? (
                      <RefreshCwIcon size={14} className="animate-spin" />
                    ) : (
                      <SendIcon size={14} />
                    )}
                    {confirming ? "Enviando…" : "Confirmar y enviar postulación"}
                  </button>
                </div>
              )}

              {/* Error state */}
              {agentSession.status === "failed" && agentSession.error_message && (
                <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
                  {agentSession.error_message}
                </div>
              )}

              {/* Reset */}
              {["failed", "submitted"].includes(agentSession.status) && (
                <button
                  onClick={() => { setAgentSession(null); setAgentFormUrl(""); setFieldAnswers({}); }}
                  className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                  Iniciar nueva sesión
                </button>
              )}
            </div>
          )}

          {/* Submitted */}
          {submitDone && (
            <div className="flex items-center gap-2 text-emerald-400 text-sm font-semibold">
              <CheckIcon size={16} />
              ¡Postulación enviada exitosamente!
            </div>
          )}
        </div>

        {/* Notes + Follow-up date */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <StickyNoteIcon size={16} className="text-blue-400" />
              Notas personales
            </h3>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              placeholder="Contacto de referencia, comentarios de la entrevista…"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 resize-none mb-3"
            />
            <button
              onClick={handleSaveNotes}
              disabled={savingNotes}
              className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
            >
              <SaveIcon size={12} />
              {notesSaved ? "¡Guardado!" : savingNotes ? "Guardando…" : "Guardar notas"}
            </button>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <CalendarIcon size={16} className="text-blue-400" />
              Fecha de seguimiento
            </h3>
            <p className="text-xs text-slate-500 mb-3">
              Recordatorio para hacer follow-up si no recibiste respuesta.
            </p>
            <input
              type="date"
              value={followUpDate}
              onChange={(e) => setFollowUpDate(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-600 mb-3 [color-scheme:dark]"
            />
            <button
              onClick={handleSaveFollowUp}
              disabled={savingDate}
              className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
            >
              <SaveIcon size={12} />
              {dateSaved ? "¡Guardado!" : savingDate ? "Guardando…" : "Guardar fecha"}
            </button>
          </div>
        </div>

        {/* Strategy */}
        {app.strategy && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <ZapIcon size={16} className="text-blue-400" />
              Estrategia de postulación
            </h3>
            <p className="text-sm text-slate-300 leading-relaxed">
              {(app.strategy as Record<string, string>)?.overall_approach}
            </p>
          </div>
        )}

        {/* Latest CV */}
        {latestCV && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <FileTextIcon size={16} className="text-blue-400" />
              CV Personalizado
            </h3>
            {latestCV.headline_adapted && (
              <p className="text-blue-300 font-medium mb-2">{latestCV.headline_adapted}</p>
            )}
            {latestCV.summary_adapted && (
              <p className="text-sm text-slate-300 leading-relaxed">{latestCV.summary_adapted}</p>
            )}
            {Array.isArray(latestCV.changes) && latestCV.changes.length > 0 && (
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

        {/* Application answers */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <MessageSquareIcon size={16} className="text-blue-400" />
            Preguntas de la empresa
          </h3>
          <p className="text-xs text-slate-500 mb-3">Pegá las preguntas del formulario, una por línea.</p>
          <textarea
            value={questions}
            onChange={(e) => setQuestions(e.target.value)}
            rows={4}
            placeholder={"¿Por qué querés trabajar en esta empresa?\n¿Cuál es tu mayor fortaleza?\n…"}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600 resize-none mb-3"
          />
          <button
            onClick={handleGenerateAnswers}
            disabled={genAnswers || !questions.trim()}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            <ZapIcon size={14} />
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
            <div className="space-y-3">
              {app.events.map((ev) => (
                <div key={ev.id} className="flex gap-3 items-start">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-1.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm text-slate-300 font-medium capitalize">{ev.event_type}</p>
                    {ev.notes && <p className="text-xs text-slate-500 mt-0.5">{ev.notes}</p>}
                    <p className="text-xs text-slate-600 mt-0.5">
                      {new Date(ev.occurred_at).toLocaleString("es-AR")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
