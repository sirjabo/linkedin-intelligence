"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { getRecommendations, getJobSources, type Recommendation } from "@/lib/api-v2";
import { ArrowLeftIcon, ExternalLinkIcon, SearchIcon, StarIcon, ServerIcon } from "lucide-react";

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 70 ? "bg-emerald-900/40 text-emerald-400 border-emerald-800" :
    pct >= 40 ? "bg-yellow-900/40 text-yellow-400 border-yellow-800" :
    "bg-slate-800 text-slate-400 border-slate-700";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${color}`}>
      {pct}% match
    </span>
  );
}

const SOURCE_LABELS: Record<string, string> = {
  remotive: "Remotive",
  arbeitnow: "Arbeitnow",
  remoteok: "RemoteOK",
};

export default function RecommendationsPage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  const [jobs, setJobs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [fetched, setFetched] = useState(false);

  // Sources
  const [availableSources, setAvailableSources] = useState<string[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);

  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [token, isLoading, router]);

  useEffect(() => {
    getJobSources()
      .then((data) => {
        setAvailableSources(data.sources);
        setSelectedSources(data.sources);
      })
      .catch(() => {
        setAvailableSources(["remotive", "arbeitnow", "remoteok"]);
        setSelectedSources(["remotive", "arbeitnow", "remoteok"]);
      });
  }, []);

  function toggleSource(src: string) {
    setSelectedSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src]
    );
  }

  async function handleSearch(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const data = await getRecommendations(
        token,
        query || undefined,
        selectedSources.length > 0 ? selectedSources : undefined
      );
      setJobs(data);
      setFetched(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al buscar trabajos");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (token && availableSources.length > 0) handleSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, availableSources]);

  if (isLoading) {
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
          <h1 className="font-bold text-white">Trabajos Recomendados</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {/* Search + source selector */}
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <SearchIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ej: Python data engineer, ML engineer…"
                className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors"
            >
              {loading ? "Buscando…" : "Buscar"}
            </button>
          </div>

          {/* Source checkboxes */}
          {availableSources.length > 0 && (
            <div className="flex items-center gap-4 flex-wrap">
              <span className="flex items-center gap-1.5 text-xs text-slate-500">
                <ServerIcon size={12} />
                Fuentes:
              </span>
              {availableSources.map((src) => (
                <label key={src} className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={selectedSources.includes(src)}
                    onChange={() => toggleSource(src)}
                    className="accent-blue-600 w-3.5 h-3.5"
                  />
                  <span className="text-xs text-slate-300">
                    {SOURCE_LABELS[src] ?? src}
                  </span>
                </label>
              ))}
            </div>
          )}
        </form>

        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {/* Results */}
        {fetched && jobs.length === 0 && !loading && (
          <div className="text-center py-16">
            <StarIcon size={40} className="mx-auto text-slate-700 mb-4" />
            <p className="text-slate-400">No se encontraron trabajos.</p>
            <p className="text-slate-500 text-sm mt-1">Intentá con otra búsqueda o cargá tu perfil primero.</p>
          </div>
        )}

        <div className="space-y-3">
          {jobs.map((job) => (
            <div
              key={job.external_id}
              className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1 flex-wrap">
                    <h3 className="font-semibold text-white">{job.title}</h3>
                    <ScoreBadge score={job.score} />
                  </div>
                  <p className="text-sm text-slate-400 mb-2">
                    {job.company}
                    {job.location ? ` · ${job.location}` : ""}
                    {job.remote_type ? ` · ${job.remote_type}` : ""}
                  </p>
                  {job.tech_tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {job.tech_tags.slice(0, 6).map((tag) => (
                        <span key={tag} className="text-xs bg-blue-900/30 text-blue-300 border border-blue-800/50 px-2 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {job.matched_keywords.length > 0 && (
                    <p className="text-xs text-slate-500">
                      Coincidencias: {job.matched_keywords.slice(0, 5).join(", ")}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  {job.salary_range && (
                    <span className="text-xs text-slate-400">{job.salary_range}</span>
                  )}
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
                  >
                    Ver oferta <ExternalLinkIcon size={13} />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
