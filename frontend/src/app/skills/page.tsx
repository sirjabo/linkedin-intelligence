"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getMarketRoles, getSkillsRadar, type SkillFrequency } from "@/lib/api-v2";
import { BarChart2Icon, ArrowLeftIcon, RefreshCwIcon, DownloadIcon, TrendingUpIcon, TrendingDownIcon, MinusIcon } from "lucide-react";

const ROLE_LABELS: Record<string, string> = {
  ai_engineer: "AI Engineer",
  data_engineer: "Data Engineer",
  analytics_engineer: "Analytics Engineer",
  ml_engineer: "ML Engineer",
  backend_engineer: "Backend Engineer",
  frontend_engineer: "Frontend Engineer",
  devops_engineer: "DevOps Engineer",
  data_scientist: "Data Scientist",
};

const CATEGORY_COLORS: Record<string, string> = {
  language: "bg-blue-500",
  frontend: "bg-violet-500",
  backend: "bg-indigo-500",
  ai_ml: "bg-emerald-500",
  data: "bg-cyan-500",
  cloud: "bg-orange-500",
  database: "bg-yellow-500",
  tools: "bg-slate-500",
  other: "bg-slate-600",
};

const CATEGORY_LABELS: Record<string, string> = {
  language: "Lenguaje",
  frontend: "Frontend",
  backend: "Backend",
  ai_ml: "AI / ML",
  data: "Data",
  cloud: "Cloud / Infra",
  database: "Base de datos",
  tools: "Herramientas",
  other: "Otro",
};

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "rising" || trend === "new") {
    return <TrendingUpIcon className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
  }
  if (trend === "falling") {
    return <TrendingDownIcon className="w-3.5 h-3.5 text-red-400 shrink-0" />;
  }
  return <MinusIcon className="w-3.5 h-3.5 text-slate-600 shrink-0" />;
}

function SkillBar({ skill, max }: { skill: SkillFrequency; max: number }) {
  const barPct = max > 0 ? (skill.frequency_pct / max) * 100 : 0;
  const barColor = CATEGORY_COLORS[skill.category] ?? "bg-slate-500";
  return (
    <div className="flex items-center gap-4 bg-slate-900 border border-slate-800 rounded-xl px-5 py-3.5">
      <div className="w-6 text-xs text-slate-600 text-right shrink-0">{skill.rank}</div>
      <div className="w-32 shrink-0">
        <p className="text-sm font-medium text-white leading-tight">{skill.name}</p>
        <p className="text-xs text-slate-500 mt-0.5">{CATEGORY_LABELS[skill.category] ?? skill.category}</p>
      </div>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden" role="progressbar" aria-valuenow={skill.frequency_pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${skill.name}: ${skill.frequency_pct}%`}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${barPct}%` }}
        />
      </div>
      <div className="flex items-center gap-2 w-16 justify-end shrink-0">
        <TrendIcon trend={skill.trend} />
        <span className="text-sm text-slate-300 font-medium tabular-nums">
          {skill.frequency_pct}%
        </span>
      </div>
    </div>
  );
}

export default function SkillsPage() {
  const [roles, setRoles] = useState<string[]>([]);
  const [selectedRole, setSelectedRole] = useState("ai_engineer");
  const [skills, setSkills] = useState<SkillFrequency[]>([]);
  const [total, setTotal] = useState(0);
  const [period, setPeriod] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getMarketRoles()
      .then((d) => setRoles(d.roles))
      .catch(() => setRoles(["ai_engineer", "data_engineer", "analytics_engineer"]));
  }, []);

  async function loadSkills(role: string) {
    setLoading(true);
    setError("");
    try {
      const data = await getSkillsRadar(role, 30);
      setSkills(data.skills);
      setTotal(data.total_jobs_analyzed);
      setPeriod(data.period);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al cargar skills");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSkills(selectedRole);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRole]);

  const maxPct = skills.length > 0 ? Math.max(...skills.map((s) => s.frequency_pct)) : 100;
  const rising = skills.filter((s) => s.trend === "rising" || s.trend === "new").length;
  const falling = skills.filter((s) => s.trend === "falling").length;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <Link
          href="/"
          aria-label="Volver al inicio"
          className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-300 text-sm mb-10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" aria-hidden="true" /> Volver al inicio
        </Link>

        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/8 flex items-center justify-center">
              <BarChart2Icon className="w-5 h-5 text-slate-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Skills Radar</h1>
              <p className="text-sm text-slate-500">
                Tendencias de mercado en tiempo real
                {total > 0 && ` · ${total} ofertas`}
                {period && ` · ${period}`}
              </p>
            </div>
          </div>
          {!loading && skills.length > 0 && (
            <button
              onClick={() => window.print()}
              aria-label="Exportar Skills Radar como PDF"
              className="no-print flex items-center gap-1.5 text-xs text-slate-400 hover:text-white border border-slate-700 hover:border-slate-500 px-3 py-1.5 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <DownloadIcon className="w-3.5 h-3.5" aria-hidden="true" /> PDF
            </button>
          )}
        </div>

        {/* Trend summary badges */}
        {!loading && skills.length > 0 && (
          <div className="flex gap-3 mb-6">
            {rising > 0 && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/30 border border-emerald-800/30 px-3 py-1 rounded-full">
                <TrendingUpIcon className="w-3 h-3" /> {rising} en alza esta semana
              </span>
            )}
            {falling > 0 && (
              <span className="flex items-center gap-1.5 text-xs text-red-400 bg-red-950/30 border border-red-800/30 px-3 py-1 rounded-full">
                <TrendingDownIcon className="w-3 h-3" /> {falling} en baja
              </span>
            )}
          </div>
        )}

        {/* Role selector */}
        <div role="tablist" aria-label="Rol objetivo" className="flex flex-wrap gap-2 mb-8">
          {(roles.length > 0 ? roles : Object.keys(ROLE_LABELS)).map((role) => (
            <button
              key={role}
              role="tab"
              aria-selected={selectedRole === role}
              onClick={() => setSelectedRole(role)}
              className={`text-sm px-4 py-1.5 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                selectedRole === role
                  ? "bg-blue-600 border-blue-600 text-white"
                  : "bg-transparent border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200"
              }`}
            >
              {ROLE_LABELS[role] ?? role}
            </button>
          ))}
        </div>

        {error && (
          <div role="alert" className="mb-4 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {loading ? (
          <div role="status" aria-label="Consultando fuentes de empleo" className="flex items-center justify-center py-20 gap-3 text-slate-400">
            <RefreshCwIcon className="w-5 h-5 animate-spin" aria-hidden="true" />
            <span>Consultando fuentes de empleo…</span>
          </div>
        ) : (
          <div className="space-y-2.5">
            {skills.length === 0 && (
              <div className="text-center py-16 text-slate-500">
                No se encontraron skills para este rol.
              </div>
            )}
            {skills.map((skill) => (
              <SkillBar key={skill.slug} skill={skill} max={maxPct} />
            ))}
          </div>
        )}

        {!loading && skills.length > 0 && (
          <div className="mt-8 flex items-center justify-center gap-6 text-xs text-slate-600">
            <span className="flex items-center gap-1.5"><TrendingUpIcon className="w-3 h-3 text-emerald-500" /> En alza vs. semana anterior</span>
            <span className="flex items-center gap-1.5"><MinusIcon className="w-3 h-3 text-slate-600" /> Estable</span>
            <span className="flex items-center gap-1.5"><TrendingDownIcon className="w-3 h-3 text-red-500" /> En baja</span>
          </div>
        )}
      </div>
    </div>
  );
}
