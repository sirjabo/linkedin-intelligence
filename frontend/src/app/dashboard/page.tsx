"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/lib/auth";
import {
  listApplications,
  getApplicationStats,
  getProfileHealth,
  getRecommendations,
  type Application,
  type ApplicationStats,
  type ProfileHealth,
  type Recommendation,
} from "@/lib/api-v2";
import {
  ZapIcon,
  BriefcaseIcon,
  TrendingUpIcon,
  LinkedinIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  ClockIcon,
  XCircleIcon,
  SparklesIcon,
} from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  applied: "bg-blue-500/15 text-blue-400",
  interview: "bg-emerald-500/15 text-emerald-400",
  offer: "bg-yellow-500/15 text-yellow-400",
  rejected: "bg-red-500/15 text-red-400",
  withdrawn: "bg-slate-500/15 text-slate-400",
};

const STATUS_LABEL: Record<string, string> = {
  applied: "Aplicado",
  interview: "Entrevista",
  offer: "Oferta",
  rejected: "Rechazado",
  withdrawn: "Retirado",
};

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string; icon: React.ElementType; color: string;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon className="w-4.5 h-4.5" />
        </div>
      </div>
      <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
      <p className="text-sm font-medium text-white mt-0.5">{label}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function HealthBar({ score, passed, total }: { score: number; passed: number; total: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 75 ? "bg-emerald-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-slate-300">Completitud del perfil</span>
        <span className="text-sm font-bold text-white">{pct}%</span>
      </div>
      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-slate-500 mt-1.5">{passed}/{total} checks pasados</p>
    </div>
  );
}

export default function DashboardPage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [apps, setApps] = useState<Application[]>([]);
  const [stats, setStats] = useState<ApplicationStats | null>(null);
  const [health, setHealth] = useState<ProfileHealth | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token) return;
    Promise.allSettled([
      listApplications(token).then(setApps),
      getApplicationStats(token).then(setStats),
      getProfileHealth(token).then(setHealth),
      getRecommendations(token, "", []).then((r) => setRecs(r.slice(0, 4))),
    ]).finally(() => setLoading(false));
  }, [token]);

  if (isLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando dashboard…</div>
      </div>
    );
  }

  const recentApps = apps.slice(0, 5);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <main className="max-w-6xl mx-auto px-6 pt-10 pb-24">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">Tu panorama completo de búsqueda de empleo</p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Postulaciones"
            value={stats?.total ?? 0}
            sub={`${stats?.active ?? 0} activas`}
            icon={BriefcaseIcon}
            color="bg-blue-600/20 text-blue-400"
          />
          <StatCard
            label="Entrevistas"
            value={stats?.funnel?.["interview"] ?? 0}
            sub="en proceso"
            icon={CheckCircleIcon}
            color="bg-emerald-600/20 text-emerald-400"
          />
          <StatCard
            label="Ofertas"
            value={stats?.offers ?? 0}
            sub="recibidas"
            icon={SparklesIcon}
            color="bg-yellow-600/20 text-yellow-400"
          />
          <StatCard
            label="Rechazos"
            value={stats?.rejected ?? 0}
            sub="registrados"
            icon={XCircleIcon}
            color="bg-slate-600/20 text-slate-400"
          />
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Left: Recent applications */}
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Postulaciones recientes</h2>
              <Link href="/applications" className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
                Ver todas <ArrowRightIcon className="w-3 h-3" />
              </Link>
            </div>

            {recentApps.length === 0 ? (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
                <BriefcaseIcon className="w-10 h-10 text-slate-700 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">Todavía no tenés postulaciones registradas.</p>
                <Link
                  href="/recommendations"
                  className="inline-flex items-center gap-1.5 mt-4 text-sm text-blue-400 hover:text-blue-300"
                >
                  Ver ofertas recomendadas <ArrowRightIcon className="w-3.5 h-3.5" />
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {recentApps.map((app) => (
                  <Link
                    key={app.id}
                    href={`/applications/${app.id}`}
                    className="flex items-center justify-between bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl px-5 py-3.5 transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {app.job_title ?? "Trabajo sin título"}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {app.job_company ?? "Empresa desconocida"}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 ml-4 shrink-0">
                      {app.follow_up_date && (
                        <span className="flex items-center gap-1 text-xs text-slate-500">
                          <ClockIcon className="w-3 h-3" />
                          {new Date(app.follow_up_date).toLocaleDateString("es-AR", { day: "2-digit", month: "short" })}
                        </span>
                      )}
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[app.status] ?? "bg-slate-800 text-slate-400"}`}>
                        {STATUS_LABEL[app.status] ?? app.status}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}

            {/* Recommended jobs */}
            {recs.length > 0 && (
              <>
                <div className="flex items-center justify-between mt-6">
                  <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Ofertas para vos</h2>
                  <Link href="/recommendations" className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
                    Ver más <ArrowRightIcon className="w-3 h-3" />
                  </Link>
                </div>
                <div className="space-y-2">
                  {recs.map((rec) => (
                    <a
                      key={rec.external_id}
                      href={rec.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl px-5 py-3.5 transition-colors group"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-white group-hover:text-blue-300 transition-colors truncate">
                          {rec.title}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">{rec.company} · {rec.location}</p>
                      </div>
                      <span className="ml-4 shrink-0 text-xs font-bold text-emerald-400 tabular-nums">
                        {rec.score}%
                      </span>
                    </a>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Right: Profile + quick actions */}
          <div className="space-y-4">
            {/* Profile health */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Perfil</h2>
              {health ? (
                <>
                  <HealthBar score={health.score} passed={health.passed} total={health.total} />
                  {health.tips.length > 0 && (
                    <ul className="mt-4 space-y-1.5">
                      {health.tips.slice(0, 3).map((tip, i) => (
                        <li key={i} className="text-xs text-slate-400 flex items-start gap-2">
                          <span className="text-yellow-500 mt-0.5 shrink-0">▸</span>
                          {tip}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-500">Cargando…</p>
              )}
              <Link
                href="/profile"
                className="mt-4 flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 border border-slate-700 hover:border-blue-500/50 rounded-lg py-2 transition-colors"
              >
                Ir a mi perfil <ArrowRightIcon className="w-3 h-3" />
              </Link>
            </div>

            {/* Quick actions */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Herramientas</h2>
              <div className="space-y-2">
                {[
                  { href: "/analyze", icon: LinkedinIcon, label: "Analizar LinkedIn", color: "text-blue-400" },
                  { href: "/skills", icon: TrendingUpIcon, label: "Skills Radar", color: "text-emerald-400" },
                  { href: "/market", icon: ZapIcon, label: "Mercado", color: "text-yellow-400" },
                ].map(({ href, icon: Icon, label, color }) => (
                  <Link
                    key={href}
                    href={href}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors group"
                  >
                    <Icon className={`w-4 h-4 ${color}`} />
                    <span className="text-sm text-slate-300 group-hover:text-white transition-colors">{label}</span>
                    <ArrowRightIcon className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 ml-auto transition-colors" />
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
