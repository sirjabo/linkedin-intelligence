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
  type Application,
  type CVVersion,
  type CoverLetter,
  type ApplicationAnswer,
} from "@/lib/api-v2";
import { ArrowLeftIcon, FileTextIcon, MailIcon, ZapIcon, CheckIcon, MessageSquareIcon, BrainIcon } from "lucide-react";

const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador",
  applied: "Postulado",
  phone_screen: "Entrevista inicial",
  interview: "Entrevista",
  offer: "Oferta",
  rejected: "Rechazado",
  withdrawn: "Retirado",
};

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

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token || !id) return;
    getApplication(token, id)
      .then(setApp)
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

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href="/applications" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeftIcon size={20} />
          </Link>
          <div className="flex-1">
            <h1 className="font-bold text-white">Postulación</h1>
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
