"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface Skill {
  name: string;
  frequency_pct: number;
  trend: "rising" | "stable" | "declining";
}

interface SkillsRadarProps {
  role: string;
  skills: Skill[];
}

const TREND_COLORS = {
  rising: "#22c55e",
  stable: "#3b82f6",
  declining: "#ef4444",
} as const;

export default function SkillsRadar({ role, skills }: SkillsRadarProps) {
  const top10 = skills.slice(0, 10);

  const chartData = top10.map((s) => ({
    subject: s.name,
    value: s.frequency_pct,
    trend: s.trend,
  }));

  return (
    <div className="w-full">
      <h2 className="text-xl font-semibold mb-4 text-center">
        Skills más demandadas — {role.replace("_", " ").toUpperCase()}
      </h2>
      <ResponsiveContainer width="100%" height={400}>
        <RadarChart data={chartData}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="Frecuencia %"
            dataKey="value"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.35}
          />
          <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`, "Frecuencia"]} />
        </RadarChart>
      </ResponsiveContainer>

      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2 pr-4">#</th>
              <th className="text-left py-2 pr-4">Skill</th>
              <th className="text-right py-2 pr-4">Frecuencia</th>
              <th className="text-right py-2">Tendencia</th>
            </tr>
          </thead>
          <tbody>
            {skills.map((skill, i) => (
              <tr key={skill.name} className="border-b last:border-0">
                <td className="py-2 pr-4 text-gray-500">{i + 1}</td>
                <td className="py-2 pr-4 font-medium">{skill.name}</td>
                <td className="py-2 pr-4 text-right">
                  {skill.frequency_pct.toFixed(1)}%
                </td>
                <td className="py-2 text-right">
                  <span
                    className="text-xs font-medium"
                    style={{ color: TREND_COLORS[skill.trend] }}
                  >
                    {skill.trend === "rising"
                      ? "↑"
                      : skill.trend === "declining"
                        ? "↓"
                        : "→"}{" "}
                    {skill.trend}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
