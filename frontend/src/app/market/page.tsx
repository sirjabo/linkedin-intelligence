"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import { getMarketSkills, getMarketTrends } from "@/lib/api";
import { MarketTrendsResponse, ROLE_LABELS, TargetRole } from "@/types/analysis";

const ROLES = Object.keys(ROLE_LABELS) as TargetRole[];

export default function MarketPage() {
  const [role, setRole] = useState<TargetRole>("ai_engineer");
  const [jobs, setJobs] = useState(0);
  const [skillCount, setSkillCount] = useState(0);
  const [trends, setTrends] = useState<MarketTrendsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getMarketSkills(role), getMarketTrends(role)])
      .then(([skills, trendData]) => {
        if (cancelled) return;
        setJobs(skills.total_jobs_analyzed);
        setSkillCount(skills.skills.length);
        setTrends(trendData);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Error al cargar mercado");
      });
    return () => {
      cancelled = true;
    };
  }, [role]);

  const stats = [
    { label: "Menciones analizadas", value: jobs ? jobs.toLocaleString("es-AR") : "—", sub: "rol seleccionado" },
    { label: "Skills tracked", value: String(skillCount || "—"), sub: ROLE_LABELS[role] },
    { label: "Skills en alza", value: String(trends?.rising.length ?? "—"), sub: "últimos 7 días" },
    { label: "Skills en baja", value: String(trends?.declining.length ?? "—"), sub: "últimos 7 días" },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />
      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">
          ← Volver al inicio
        </Link>
        <h1 className="text-2xl font-bold mt-8 mb-2">Inteligencia de Mercado</h1>
        <p className="text-sm text-slate-500 mb-6">
          Tendencias de skills para roles tech en Latam (MVP con catálogo de demanda)
        </p>

        <div className="flex flex-wrap gap-2 mb-8">
          {ROLES.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRole(r)}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                role === r ? "bg-blue-600 border-blue-500" : "border-white/10 text-slate-400"
              }`}
            >
              {ROLE_LABELS[r]}
            </button>
          ))}
        </div>

        {error && <p className="text-rose-400 text-sm mb-4">{error}</p>}

        <div className="grid grid-cols-2 gap-4 mb-10">
          {stats.map(({ label, value, sub }) => (
            <div key={label} className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
              <p className="text-2xl font-bold mb-0.5">{value}</p>
              <p className="text-sm font-medium text-slate-300">{label}</p>
              <p className="text-xs text-slate-500 mt-0.5">{sub}</p>
            </div>
          ))}
        </div>

        {trends && trends.rising.length > 0 && (
          <div>
            <h2 className="font-semibold mb-3">En alza esta semana</h2>
            <ul className="space-y-2">
              {trends.rising.map((item) => (
                <li
                  key={item.skill}
                  className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 px-4 py-3 text-sm"
                >
                  <span className="text-emerald-300 font-medium">{item.skill}</span>
                  <span className="text-slate-400"> · +{item.change_pct}%</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
