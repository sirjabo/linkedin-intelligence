import Navbar from "@/components/Navbar";
import Link from "next/link";
import { BarChart2, ArrowLeft, Zap } from "lucide-react";

const previewSkills = [
  { name: "Python", pct: 94, cat: "Lenguajes" },
  { name: "SQL", pct: 88, cat: "Lenguajes" },
  { name: "dbt", pct: 71, cat: "Herramientas" },
  { name: "Spark", pct: 65, cat: "Herramientas" },
  { name: "LangChain", pct: 58, cat: "IA / ML" },
  { name: "Airflow", pct: 54, cat: "Orquestación" },
  { name: "Snowflake", pct: 49, cat: "Cloud / Data" },
  { name: "AWS", pct: 47, cat: "Cloud / Data" },
];

export default function SkillsPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-300 text-sm mb-10 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Volver al inicio
        </Link>

        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-white/8 flex items-center justify-center">
            <BarChart2 className="w-5 h-5 text-slate-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Skills Radar</h1>
            <p className="text-sm text-slate-500">Tendencias de mercado para roles tech</p>
          </div>
        </div>

        {/* Coming soon banner */}
        <div className="mt-8 rounded-2xl border border-blue-500/20 bg-blue-950/20 p-6 mb-10 flex items-start gap-4">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center shrink-0 mt-0.5">
            <Zap className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <p className="font-medium text-blue-300 mb-1">En desarrollo</p>
            <p className="text-sm text-slate-400 leading-relaxed">
              Estamos procesando miles de ofertas de trabajo cada semana para mostrarte las skills
              más demandadas por rol. Este módulo estará disponible en las próximas semanas.
            </p>
          </div>
        </div>

        {/* Preview (blurred) */}
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-950/60 to-slate-950 z-10 rounded-2xl" />
          <div className="blur-sm pointer-events-none space-y-3">
            {previewSkills.map(({ name, pct, cat }) => (
              <div key={name} className="flex items-center gap-4 bg-white/[0.03] border border-white/8 rounded-xl px-5 py-3.5">
                <div className="w-28 shrink-0">
                  <p className="text-sm font-medium text-white">{name}</p>
                  <p className="text-xs text-slate-500">{cat}</p>
                </div>
                <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-sm text-slate-400 w-10 text-right">{pct}%</span>
              </div>
            ))}
          </div>
          <div className="absolute inset-0 flex items-center justify-center z-20">
            <div className="text-center bg-slate-950/80 rounded-2xl px-8 py-5 border border-white/10 backdrop-blur-sm">
              <p className="font-semibold text-white mb-1">Próximamente</p>
              <p className="text-sm text-slate-400">Skills top para cada rol, actualizadas semanalmente</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
