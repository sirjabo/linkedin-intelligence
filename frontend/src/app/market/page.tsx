"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getMarketTrends, getMarketRoles, getSalaryRange, type MarketTrendsResponse, type SalaryRange } from "@/lib/api-v2";
import { TrendingUpIcon, ArrowLeftIcon, RefreshCwIcon, BuildingIcon, ZapIcon, DollarSignIcon } from "lucide-react";

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

function SalaryCard({ salary }: { salary: SalaryRange }) {
  return (
    <div className="rounded-2xl border border-emerald-800/30 bg-emerald-950/10 p-5">
      <div className="flex items-center gap-2 mb-4">
        <DollarSignIcon className="w-4 h-4 text-emerald-400" />
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Rango salarial — {ROLE_LABELS[salary.role] ?? salary.role}
        </h2>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="text-center">
          <p className="text-xs text-slate-500 mb-1">Mínimo</p>
          <p className="text-lg font-bold text-white">${(salary.min_usd ?? 0).toLocaleString()}</p>
          <p className="text-xs text-slate-600">USD/mes</p>
        </div>
        <div className="text-center border-x border-emerald-800/20">
          <p className="text-xs text-slate-500 mb-1">Mediana</p>
          <p className="text-xl font-bold text-emerald-400">${(salary.median_usd ?? 0).toLocaleString()}</p>
          <p className="text-xs text-slate-600">USD/mes</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-slate-500 mb-1">Máximo</p>
          <p className="text-lg font-bold text-white">${(salary.max_usd ?? 0).toLocaleString()}</p>
          <p className="text-xs text-slate-600">USD/mes</p>
        </div>
      </div>
      {salary.notes && (
        <p className="text-xs text-slate-500 mt-3 pt-3 border-t border-slate-800">
          {salary.notes}
        </p>
      )}
      {salary.sources && salary.sources.length > 0 && (
        <p className="text-xs text-slate-600 mt-1">
          Fuentes: {salary.sources.join(", ")}
        </p>
      )}
    </div>
  );
}

export default function MarketPage() {
  const [roles, setRoles] = useState<string[]>([]);
  const [selectedRole, setSelectedRole] = useState("ai_engineer");
  const [data, setData] = useState<MarketTrendsResponse | null>(null);
  const [salary, setSalary] = useState<SalaryRange | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getMarketRoles()
      .then((d) => setRoles(d.roles))
      .catch(() => setRoles(["ai_engineer", "data_engineer", "analytics_engineer"]));
  }, []);

  async function load(role: string) {
    setLoading(true);
    setError("");
    setSalary(null);
    try {
      const [trendsResult, salaryResult] = await Promise.allSettled([
        getMarketTrends(role),
        getSalaryRange(role),
      ]);
      if (trendsResult.status === "fulfilled") setData(trendsResult.value);
      else throw new Error(trendsResult.reason?.message ?? "Error al cargar datos");
      if (salaryResult.status === "fulfilled") setSalary(salaryResult.value);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al cargar datos");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(selectedRole);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRole]);

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

        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-white/8 flex items-center justify-center">
            <TrendingUpIcon className="w-5 h-5 text-slate-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Inteligencia de Mercado</h1>
            <p className="text-sm text-slate-500">
              Skills más demandadas, salarios y empresas que contratan tech
              {data && ` · ${data.total_jobs_analyzed} ofertas analizadas`}
            </p>
          </div>
        </div>

        {/* Role tabs */}
        <div role="tablist" aria-label="Rol objetivo" className="flex flex-wrap gap-2 mt-6 mb-8">
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
          <div role="status" aria-label="Analizando mercado" className="flex items-center justify-center py-20 gap-3 text-slate-400">
            <RefreshCwIcon className="w-5 h-5 animate-spin" aria-hidden="true" />
            <span>Analizando mercado…</span>
          </div>
        ) : data ? (
          <div className="space-y-8">
            {/* Stats row */}
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
                <p className="text-2xl font-bold text-white mb-0.5">{data.total_jobs_analyzed}</p>
                <p className="text-sm font-medium text-slate-300">Ofertas analizadas</p>
                <p className="text-xs text-slate-500 mt-0.5">hoy en tiempo real</p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-5">
                <p className="text-2xl font-bold text-white mb-0.5">{data.top_skills.length}</p>
                <p className="text-sm font-medium text-slate-300">Skills indexadas</p>
                <p className="text-xs text-slate-500 mt-0.5">para {ROLE_LABELS[selectedRole] ?? selectedRole}</p>
              </div>
            </div>

            {/* Salary range */}
            {salary && <SalaryCard salary={salary} />}

            {/* Top skills */}
            {data.top_skills.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                  <ZapIcon className="w-4 h-4 text-blue-400" />
                  Skills más demandadas
                </h2>
                <div className="space-y-2.5">
                  {data.top_skills.slice(0, 10).map((skill, i) => (
                    <div
                      key={skill.skill}
                      className="flex items-center gap-4 bg-slate-900 border border-slate-800 rounded-xl px-5 py-3"
                    >
                      <span className="text-xs text-slate-600 w-5 text-right" aria-hidden="true">{i + 1}</span>
                      <span className="flex-1 text-sm font-medium text-white">{skill.skill}</span>
                      <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden" role="progressbar" aria-valuenow={skill.frequency_pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${skill.skill}: ${skill.frequency_pct}%`}>
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${skill.frequency_pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-400 w-10 text-right" aria-hidden="true">{skill.frequency_pct}%</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Top companies */}
            {data.top_companies.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                  <BuildingIcon className="w-4 h-4 text-emerald-400" />
                  Empresas que más contratan
                </h2>
                <div className="grid grid-cols-2 gap-2">
                  {data.top_companies.map((company) => (
                    <div
                      key={company.name}
                      className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded-xl px-4 py-3"
                    >
                      <span className="text-sm text-slate-200 truncate">{company.name}</span>
                      <span className="text-xs text-slate-500 ml-2 shrink-0">
                        {company.job_count} oferta{company.job_count !== 1 ? "s" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <p className="text-xs text-slate-600 text-center">
              Datos en tiempo real de Remotive, Arbeitnow y RemoteOK · Salarios: referencia mercado remoto USD
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
