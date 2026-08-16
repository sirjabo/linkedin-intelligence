"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { listApplications, type Application } from "@/lib/api-v2";
import { FileTextIcon, ArrowLeftIcon } from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-slate-800 text-slate-400",
  applied: "bg-blue-900/40 text-blue-400",
  phone_screen: "bg-purple-900/40 text-purple-400",
  interview: "bg-yellow-900/40 text-yellow-400",
  offer: "bg-emerald-900/40 text-emerald-400",
  rejected: "bg-red-900/40 text-red-400",
  withdrawn: "bg-slate-800 text-slate-500",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador",
  applied: "Postulado",
  phone_screen: "Entrevista inicial",
  interview: "Entrevista",
  offer: "Oferta",
  rejected: "Rechazado",
  withdrawn: "Retirado",
};

export default function ApplicationsPage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    if (!token) return;
    listApplications(token)
      .then(setApps)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  if (isLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center" role="status" aria-label="Cargando postulaciones">
        <div className="text-slate-400 animate-pulse" aria-hidden="true">Cargando…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link
            href="/dashboard"
            aria-label="Volver al dashboard"
            className="text-slate-400 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
          >
            <ArrowLeftIcon size={20} aria-hidden="true" />
          </Link>
          <h1 className="font-bold text-white">Mis Postulaciones</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-6">
          <p className="text-slate-400 text-sm" aria-live="polite">
            {apps.length} postulación{apps.length !== 1 ? "es" : ""}
          </p>
        </div>

        {apps.length === 0 ? (
          <div className="text-center py-20" role="status">
            <FileTextIcon size={48} className="mx-auto text-slate-700 mb-4" aria-hidden="true" />
            <p className="text-slate-400">No tenés postulaciones todavía.</p>
            <p className="text-slate-500 text-sm mt-1">
              Andá a un trabajo y hacé click en &quot;Crear postulación&quot;.
            </p>
          </div>
        ) : (
          <ul className="space-y-3" aria-label="Lista de postulaciones">
            {apps.map((app) => (
              <li key={app.id}>
                <Link
                  href={`/applications/${app.id}`}
                  aria-label={`${app.job_title ?? "Trabajo sin título"} en ${app.job_company ?? "empresa desconocida"} — ${STATUS_LABEL[app.status] ?? app.status}`}
                  className="block bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-white truncate">
                        {app.job_title ?? "Trabajo sin título"}
                      </h3>
                      {app.job_company && (
                        <p className="text-sm text-slate-400 mt-0.5">{app.job_company}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2" aria-label={`Estado: ${STATUS_LABEL[app.status] ?? app.status}`}>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLOR[app.status] ?? STATUS_COLOR.draft}`} aria-hidden="true">
                          {STATUS_LABEL[app.status] ?? app.status}
                        </span>
                        {app.cv_versions.length > 0 && (
                          <span className="text-xs text-slate-500">CV v{app.cv_versions.length}</span>
                        )}
                        {app.cover_letters.length > 0 && (
                          <span className="text-xs text-slate-500">Carta</span>
                        )}
                      </div>
                    </div>
                    {app.applied_at && (
                      <time
                        dateTime={app.applied_at}
                        className="text-xs text-slate-500 flex-shrink-0"
                      >
                        {new Date(app.applied_at).toLocaleDateString("es-AR")}
                      </time>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
