"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import { getMarketSkills } from "@/lib/api";
import { MarketSkill, ROLE_LABELS, TargetRole } from "@/types/analysis";

const ROLES = Object.keys(ROLE_LABELS) as TargetRole[];

const CATEGORY_LABELS: Record<string, string> = {
  language: "Lenguajes",
  framework: "Frameworks",
  ai_ml: "IA / ML",
  devops: "DevOps",
  cloud: "Cloud / Data",
  database: "Bases de datos",
  platform: "Plataformas",
  backend: "Backend",
  bi: "BI",
  mlops: "MLOps",
  tool: "Herramientas",
};

function trendClass(trend: MarketSkill["trend"]): string {
  if (trend === "rising") return "text-emerald-400";
  if (trend === "declining") return "text-rose-400";
  return "text-slate-500";
}

function trendLabel(trend: MarketSkill["trend"]): string {
  if (trend === "rising") return "↑";
  if (trend === "declining") return "↓";
  return "→";
}

export default function SkillsPage() {
  const [role, setRole] = useState<TargetRole>("ai_engineer");
  const [skills, setSkills] = useState<MarketSkill[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getMarketSkills(role)
      .then((data) => {
        if (cancelled) return;
        setSkills(data.skills);
        setTotalJobs(data.total_jobs_analyzed);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Error al cargar skills");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [role]);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />
      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">
          ← Volver al inicio
        </Link>
        <h1 className="text-2xl font-bold mt-8 mb-2">Skills Radar</h1>
        <p className="text-sm text-slate-500 mb-6">
          Demanda relativa de skills por rol
          {totalJobs > 0 ? ` · ${totalJobs.toLocaleString("es-AR")} menciones indexadas` : ""}
        </p>

        <div className="flex flex-wrap gap-2 mb-8">
          {ROLES.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRole(r)}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                role === r
                  ? "bg-blue-600 border-blue-500"
                  : "border-white/10 text-slate-400"
              }`}
            >
              {ROLE_LABELS[r]}
            </button>
          ))}
        </div>

        {loading && <p className="text-slate-500 text-sm">Cargando mercado...</p>}
        {error && <p className="text-rose-400 text-sm">{error}</p>}

        <div className="space-y-3">
          {skills.map((skill) => (
            <div
              key={skill.slug}
              className="flex items-center gap-4 bg-white/[0.03] border border-white/8 rounded-xl px-5 py-3.5"
            >
              <span className="text-xs text-slate-500 w-6">{skill.rank}</span>
              <div className="w-36 shrink-0">
                <p className="text-sm font-medium">{skill.name}</p>
                <p className="text-xs text-slate-500">
                  {CATEGORY_LABELS[skill.category] ?? skill.category}
                </p>
              </div>
              <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${skill.frequency_pct}%` }}
                />
              </div>
              <span className="text-sm text-slate-400 w-12 text-right">
                {skill.frequency_pct}%
              </span>
              <span className={`text-sm w-8 ${trendClass(skill.trend)}`}>
                {trendLabel(skill.trend)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
