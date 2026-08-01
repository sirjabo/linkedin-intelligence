import Navbar from "@/components/Navbar";
import Link from "next/link";
import { TrendingUp, ArrowLeft, Zap } from "lucide-react";

const mockStats = [
  { label: "Ofertas analizadas", value: "12.400+", sub: "últimas 4 semanas" },
  { label: "Roles tracked", value: "8", sub: "AI, Data, Analytics, ML..." },
  { label: "Empresas activas", value: "340+", sub: "contratando ahora" },
  { label: "Skills indexadas", value: "2.100+", sub: "actualizadas semanalmente" },
];

export default function MarketPage() {
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
            <TrendingUp className="w-5 h-5 text-slate-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Inteligencia de Mercado</h1>
            <p className="text-sm text-slate-500">Tendencias, salarios y empresas que contratan tech</p>
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
              El dashboard de mercado laboral tech estará disponible en las próximas semanas.
              Incluirá tendencias de skills en tiempo real, comparación de salarios por rol y región,
              y alertas de oportunidades que encajan con tu perfil.
            </p>
          </div>
        </div>

        {/* Stats preview (blurred) */}
        <div className="relative">
          <div className="grid grid-cols-2 gap-4 blur-sm pointer-events-none">
            {mockStats.map(({ label, value, sub }) => (
              <div key={label} className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
                <p className="text-2xl font-bold text-white mb-0.5">{value}</p>
                <p className="text-sm font-medium text-slate-300">{label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{sub}</p>
              </div>
            ))}
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center bg-slate-950/80 rounded-2xl px-8 py-5 border border-white/10 backdrop-blur-sm">
              <p className="font-semibold text-white mb-1">Próximamente</p>
              <p className="text-sm text-slate-400">Dashboard de mercado laboral tech en Latam</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
