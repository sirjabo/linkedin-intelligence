"use client";

import { useEffect, useState } from "react";

import SkillsRadar from "@/components/SkillsRadar";

type Role = "ai_engineer" | "data_engineer" | "analytics_engineer" | "ml_engineer";

const ROLE_LABELS: Record<Role, string> = {
  ai_engineer: "AI Engineer",
  data_engineer: "Data Engineer",
  analytics_engineer: "Analytics Engineer",
  ml_engineer: "ML Engineer",
};

interface MarketSkill {
  name: string;
  frequency_pct: number;
  trend: "rising" | "stable" | "declining";
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export default function MarketPage() {
  const [role, setRole] = useState<Role>("ai_engineer");
  const [skills, setSkills] = useState<MarketSkill[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/market/skills/${role}?limit=15`)
      .then((r) => r.json())
      .then((data: { skills?: MarketSkill[] }) => {
        if (!cancelled) {
          setSkills(data.skills ?? []);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [role]);

  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold mb-2">Skills Radar</h1>
      <p className="text-gray-500 mb-8">
        Skills más demandadas en el mercado laboral tech argentino.
      </p>

      <div className="flex gap-2 mb-10 flex-wrap">
        {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => setRole(r)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              role === r
                ? "bg-indigo-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {ROLE_LABELS[r]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">Cargando...</div>
      ) : (
        <SkillsRadar role={role} skills={skills} />
      )}
    </main>
  );
}
