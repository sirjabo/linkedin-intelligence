"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { getApplicationStats, listApplications, type ApplicationStats, type Application } from "@/lib/api-v2";
import { ArrowLeftIcon, TrendingUpIcon, BriefcaseIcon, CheckCircleIcon, XCircleIcon } from "lucide-react";

const STAGE_LABELS: Record<string, string> = {
  draft: "Borrador",
  applied: "Postulado",
  phone_screen: "Entrevista inicial",
  interview: "Entrevista",
  offer: "Oferta",
  rejected: "Rechazado",
  withdrawn: "Retirado",
};

const STAGE_COLORS: Record<string, string> = {
  draft: "bg-slate-600",
  applied: "bg-blue-600",
  phone_screen: "bg-indigo-500",
  interview: "bg-violet-500",
  offer: "bg-emerald-500",
  rejected: "bg-red-600",
  withdrawn: "bg-slate-500",
};

const FUNNEL_STAGES = ["applied", "phone_screen", "interview", "offer"];

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: React.ElementType; color: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<ApplicationStats | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      getApplicationStats(token),
      listApplications(token),
    ])
      .then(([s, a]) => { setStats(s); setApps(a); })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (isLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando…</div>
      </div>
    );
  }

  const funnelMax = stats ? Math.max(...FUNNEL_STAGES.map((s) => stats.funnel[s] ?? 0), 1) : 1;

  const recentApps = apps.slice(0, 5);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeftIcon size={20} />
          </Link>
          <div>
            <h1 className="font-bold text-white">Analytics</h1>
            <p className="text-xs text-slate-500">Resumen de tu embudo de postulaciones</p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {stats && (
          <>
            {/* KPI cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Total postulaciones" value={stats.total} icon={BriefcaseIcon} color="bg-slate-700" />
              <StatCard label="En proceso" value={stats.active} icon={TrendingUpIcon} color="bg-blue-700" />
              <StatCard label="Ofertas recibidas" value={stats.offers} icon={CheckCircleIcon} color="bg-emerald-700" />
              <StatCard label="Rechazadas" value={stats.rejected} icon={XCircleIcon} color="bg-red-800" />
            </div>

            {/* Funnel visualization */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="font-semibold text-slate-200 mb-6">Embudo de postulaciones</h2>
              <div className="space-y-4">
                {FUNNEL_STAGES.map((stage) => {
                  const count = stats.funnel[stage] ?? 0;
                  const pct = funnelMax > 0 ? (count / funnelMax) * 100 : 0;
                  return (
                    <div key={stage}>
                      <div className="flex justify-between text-sm mb-1.5">
                        <span className="text-slate-400">{STAGE_LABELS[stage]}</span>
                        <span className="text-slate-300 font-semibold">{count}</span>
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${STAGE_COLORS[stage]}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Status breakdown */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="font-semibold text-slate-200 mb-5">Por estado</h2>
              <div className="flex flex-wrap gap-3">
                {Object.entries(stats.funnel)
                  .filter(([, count]) => count > 0)
                  .map(([stage, count]) => (
                    <div key={stage} className="flex items-center gap-2">
                      <div className={`w-2.5 h-2.5 rounded-full ${STAGE_COLORS[stage] ?? "bg-slate-600"}`} />
                      <span className="text-sm text-slate-400">{STAGE_LABELS[stage] ?? stage}</span>
                      <span className="text-sm font-semibold text-slate-200">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          </>
        )}

        {/* Recent applications */}
        {recentApps.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-slate-200">Postulaciones recientes</h2>
              <Link href="/applications" className="text-xs text-blue-400 hover:text-blue-300">
                Ver todas
              </Link>
            </div>
            <div className="space-y-3">
              {recentApps.map((a) => (
                <Link
                  key={a.id}
                  href={`/applications/${a.id}`}
                  className="flex items-center justify-between py-2 border-b border-slate-800 last:border-0 hover:text-blue-300 transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-300">{a.job_title ?? "Trabajo"}</p>
                    {a.job_company && <p className="text-xs text-slate-500">{a.job_company}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${STAGE_COLORS[a.status] ?? "bg-slate-600"}`} />
                    <span className="text-xs text-slate-500">{STAGE_LABELS[a.status] ?? a.status}</span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        {stats && stats.total === 0 && (
          <div className="text-center py-16 text-slate-500">
            <TrendingUpIcon size={48} className="mx-auto mb-4 text-slate-700" />
            <p>Todavía no tenés postulaciones.</p>
            <p className="text-sm mt-1">
              <Link href="/applications" className="text-blue-400 hover:text-blue-300">Creá tu primera postulación</Link>
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
