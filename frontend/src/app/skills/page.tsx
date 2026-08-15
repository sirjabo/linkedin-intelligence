"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getMarketRoles, getSkillsRadar, type SkillFrequency } from "@/lib/api-v2";
import { BarChart2Icon, ArrowLeftIcon, RefreshCwIcon } from "lucide-react";

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
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${barPct}%` }}
        />
      </div>
      <span className="text-sm text-slate-300 w-12 text-right shrink-0 font-medium">
        {skill.frequency_pct}%
      </span>
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

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-300 text-sm mb-10 transition-colors"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" /> Volver al inicio
        </Link>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-white/8 flex items-center justify-center">
            <BarChart2Icon className="w-5 h-5 text-slate-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Skills Radar</h1>
            <p className="text-sm text-slate-500">
              Tendencias de mercado en tiempo real
              {total > 0 && ` · ${total} ofertas analizadas`}
              {period && ` · ${period}`}
            </p>
          </div>
        </div>

        {/* Role selector */}
        <div className="flex flex-wrap gap-2 mb-8">
          {(roles.length > 0 ? roles : Object.keys(ROLE_LABELS)).map((role) => (
            <button
              key={role}
              onClick={() => setSelectedRole(role)}
              className={`text-sm px-4 py-1.5 rounded-full border transition-colors ${
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
          <div className="mb-4 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20 gap-3 text-slate-400">
            <RefreshCwIcon className="w-5 h-5 animate-spin" />
            <span>Consultando {roles.length} fuentes de empleo…</span>
          </div>
        ) : (
          <div className="space-y-2.5">
            {skills.length === 0 && !loading && (
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
          <p className="text-xs text-slate-600 text-center mt-8">
            Datos en tiempo real de Remotive, Arbeitnow y RemoteOK · Actualizado hoy
          </p>
        )}
      </div>
    </div>
  );
}
