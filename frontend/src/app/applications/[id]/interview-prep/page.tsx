"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { generateInterviewPrep, getInterviewPrep, type InterviewPrep } from "@/lib/api-v2";
import {
  ArrowLeftIcon, ZapIcon, CodeIcon, UsersIcon, StarIcon,
  MessageCircleIcon, BuildingIcon, RefreshCwIcon,
} from "lucide-react";

function Section({ title, icon: Icon, children }: {
  title: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
        <Icon size={16} className="text-blue-400" />
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function InterviewPrepPage() {
  const { id } = useParams<{ id: string }>();
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [prep, setPrep] = useState<InterviewPrep | null>(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token || !id) return;
    getInterviewPrep(token, id)
      .then(setPrep)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, id]);

  async function handleGenerate() {
    if (!token || !id) return;
    setGenerating(true);
    setError("");
    try {
      const result = await generateInterviewPrep(token, id);
      setPrep(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al generar");
    } finally {
      setGenerating(false);
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
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href={`/applications/${id}`} className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeftIcon size={20} />
          </Link>
          <div className="flex-1">
            <h1 className="font-bold text-white">Preparación para entrevista</h1>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            {generating ? (
              <RefreshCwIcon size={14} className="animate-spin" />
            ) : (
              <ZapIcon size={14} />
            )}
            {generating ? "Generando…" : prep ? "Regenerar" : "Generar prep"}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {!prep && !generating && (
          <div className="text-center py-20">
            <ZapIcon size={48} className="mx-auto text-slate-700 mb-4" />
            <p className="text-slate-400">Todavía no generaste la preparación para esta entrevista.</p>
            <p className="text-slate-500 text-sm mt-1">Hacé click en "Generar prep" para empezar.</p>
          </div>
        )}

        {prep && (
          <>
            {/* Technical questions */}
            <Section title="Preguntas técnicas" icon={CodeIcon}>
              <div className="space-y-4">
                {prep.technical_questions.map((q, i) => (
                  <div key={i} className="border-l-2 border-blue-600/40 pl-4">
                    <p className="text-sm text-white font-medium mb-1">{i + 1}. {q.question}</p>
                    <p className="text-xs text-slate-500">{q.rationale}</p>
                  </div>
                ))}
              </div>
            </Section>

            {/* Behavioral questions */}
            <Section title="Preguntas conductuales" icon={UsersIcon}>
              <div className="space-y-4">
                {prep.behavioral_questions.map((q, i) => (
                  <div key={i} className="border-l-2 border-purple-600/40 pl-4">
                    <p className="text-sm text-white font-medium mb-1">{i + 1}. {q.question}</p>
                    <span className="text-xs bg-purple-900/30 text-purple-400 border border-purple-800/50 px-2 py-0.5 rounded">
                      {q.competency}
                    </span>
                  </div>
                ))}
              </div>
            </Section>

            {/* STAR stories */}
            <Section title="Historias STAR" icon={StarIcon}>
              <div className="space-y-5">
                {prep.star_stories.map((s, i) => (
                  <div key={i} className="bg-slate-800/50 rounded-lg p-4">
                    <span className="text-xs bg-yellow-900/30 text-yellow-400 border border-yellow-800/50 px-2 py-0.5 rounded mb-3 inline-block">
                      {s.competency}
                    </span>
                    <div className="space-y-2 text-sm">
                      <div><span className="text-slate-500 font-medium">Situación: </span><span className="text-slate-300">{s.situation}</span></div>
                      <div><span className="text-slate-500 font-medium">Tarea: </span><span className="text-slate-300">{s.task}</span></div>
                      <div><span className="text-slate-500 font-medium">Acción: </span><span className="text-slate-300">{s.action}</span></div>
                      <div><span className="text-slate-500 font-medium">Resultado: </span><span className="text-slate-300">{s.result}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            </Section>

            {/* Questions to ask */}
            <Section title="Preguntas para hacerle al entrevistador" icon={MessageCircleIcon}>
              <ul className="space-y-2">
                {prep.questions_to_ask.map((q, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-300">
                    <span className="text-blue-500 mt-0.5 flex-shrink-0">→</span>
                    {q}
                  </li>
                ))}
              </ul>
            </Section>

            {/* Company research */}
            {prep.company_research && (
              <Section title="Research de la empresa" icon={BuildingIcon}>
                <div className="space-y-3 text-sm">
                  {prep.company_research.culture && (
                    <div>
                      <p className="text-slate-500 font-medium mb-0.5">Cultura</p>
                      <p className="text-slate-300">{prep.company_research.culture}</p>
                    </div>
                  )}
                  {prep.company_research.mission && (
                    <div>
                      <p className="text-slate-500 font-medium mb-0.5">Misión</p>
                      <p className="text-slate-300">{prep.company_research.mission}</p>
                    </div>
                  )}
                  {prep.company_research.values && (
                    <div>
                      <p className="text-slate-500 font-medium mb-0.5">Valores</p>
                      <p className="text-slate-300">{prep.company_research.values}</p>
                    </div>
                  )}
                </div>
              </Section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
