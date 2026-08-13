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
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse">Cargando…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeftIcon size={20} />
          </Link>
          <h1 className="font-bold text-white">Mis Postulaciones</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-6">
          <p className="text-slate-400 text-sm">{apps.length} postulación{apps.length !== 1 ? "es" : ""}</p>
        </div>

        {apps.length === 0 ? (
          <div className="text-center py-20">
            <FileTextIcon size={48} className="mx-auto text-slate-700 mb-4" />
            <p className="text-slate-400">No tenés postulaciones todavía.</p>
            <p className="text-slate-500 text-sm mt-1">
              Andá a un trabajo y hacé click en "Crear postulación".
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {apps.map((app) => (
              <Link
                key={app.id}
                href={`/applications/${app.id}`}
                className="block bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-slate-500 mb-1">Job ID: {app.job_id.slice(0, 8)}…</p>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLOR[app.status] ?? STATUS_COLOR.draft}`}>
                        {STATUS_LABEL[app.status] ?? app.status}
                      </span>
                      {app.cv_versions.length > 0 && (
                        <span className="text-xs text-slate-500">CV v{app.cv_versions.length}</span>
                      )}
                      {app.cover_letters.length > 0 && (
                        <span className="text-xs text-slate-500">Carta de presentación</span>
                      )}
                    </div>
                  </div>
                  {app.applied_at && (
                    <p className="text-xs text-slate-500">
                      {new Date(app.applied_at).toLocaleDateString("es-AR")}
                    </p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
