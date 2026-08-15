"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { ArrowRight, FileText, BarChart2, TrendingUp, Zap, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth";

const features = [
  {
    icon: FileText,
    label: "Optimizador de CV",
    desc: "Subí tu CV y un coach con IA lo reescribe sección por sección para pasar filtros ATS y destacar ante reclutadores tech.",
    href: "/profile",
    available: true,
    badge: "Disponible ahora",
  },
  {
    icon: BarChart2,
    label: "Skills Radar",
    desc: "Las 50 skills más demandadas para tu rol objetivo, en tiempo real desde cientos de ofertas en Remotive, Arbeitnow y RemoteOK.",
    href: "/skills",
    available: true,
    badge: "Disponible ahora",
  },
  {
    icon: TrendingUp,
    label: "Inteligencia de Mercado",
    desc: "Skills trending y empresas tech contratando activamente, actualizados en tiempo real desde las principales bolsas de empleo.",
    href: "/market",
    available: true,
    badge: "Disponible ahora",
  },
];

const roles = ["AI Engineer", "Analytics Engineer", "Data Engineer", "ML Engineer", "Data Scientist"];

export default function HomePage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && token) router.replace("/dashboard");
  }, [token, isLoading, router]);

  if (isLoading) return null;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-20 pb-20 text-center">
        <div className="inline-flex items-center gap-2 bg-blue-600/10 border border-blue-500/20 rounded-full px-4 py-1.5 text-blue-400 text-sm mb-8">
          <Sparkles className="w-3.5 h-3.5" />
          IA para profesionales tech de Latam
        </div>

        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-5 leading-tight">
          Optimizá tu perfil tech<br />
          <span className="text-blue-400">para el mercado de IA</span>
        </h1>

        <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-4 leading-relaxed">
          Analizamos miles de ofertas de trabajo cada semana para darte recomendaciones exactas:
          qué skills agregar, cómo reescribir tu CV, y dónde estás parado vs. los mejores.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
          {roles.map((r) => (
            <span key={r} className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1 text-slate-400">
              {r}
            </span>
          ))}
        </div>

        <Link
          href="/profile"
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-7 py-3.5 rounded-xl font-medium transition-all shadow-lg shadow-blue-900/40 hover:shadow-blue-800/50"
        >
          Analizar mi CV gratis
          <ArrowRight className="w-4 h-4" />
        </Link>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <div className="grid sm:grid-cols-3 gap-5">
          {features.map(({ icon: Icon, label, desc, href, available, badge }) => (
            <div
              key={label}
              className={`rounded-2xl border p-6 flex flex-col gap-4 transition-all ${
                available
                  ? "border-blue-500/30 bg-blue-950/20 hover:border-blue-400/40"
                  : "border-white/8 bg-white/[0.02]"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  available ? "bg-blue-600 shadow-md shadow-blue-900/40" : "bg-white/8"
                }`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                  available
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/20"
                    : "bg-white/5 text-slate-500 border border-white/10"
                }`}>
                  {badge}
                </span>
              </div>

              <div className="flex-1">
                <h3 className="font-semibold text-white mb-2">{label}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
              </div>

              <Link
                href={href}
                className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
              >
                Empezar <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/8 py-8 text-center text-xs text-slate-600">
        <div className="flex items-center justify-center gap-2 mb-1">
          <Zap className="w-3 h-3 text-blue-600" />
          <span className="text-slate-500 font-medium">LinkedIn Intelligence</span>
        </div>
        Hecho para profesionales tech de Latam
      </footer>
    </div>
  );
}
