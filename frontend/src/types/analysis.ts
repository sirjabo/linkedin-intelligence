export type TargetRole =
  | "ai_engineer"
  | "data_engineer"
  | "analytics_engineer"
  | "ml_engineer";

export const ROLE_LABELS: Record<TargetRole, string> = {
  ai_engineer: "AI Engineer",
  data_engineer: "Data Engineer",
  analytics_engineer: "Analytics Engineer",
  ml_engineer: "ML Engineer",
};

export interface KeywordFound {
  keyword: string;
  count: number;
  weight: number;
}

export interface KeywordMissing {
  keyword: string;
  weight: number;
  suggested_section: string;
}

export interface Recommendation {
  priority: number;
  section: string;
  type?: string;
  message: string;
  impact: "very_high" | "high" | "medium" | "low";
  original?: string | null;
  suggested?: string | null;
}

export interface CVAnalysisResult {
  analysis_id: string;
  ats_score: number;
  target_role: TargetRole;
  summary: string;
  keyword_analysis: {
    found: KeywordFound[];
    missing: KeywordMissing[];
  };
  section_scores: {
    contact: number;
    summary: number;
    experience: number;
    skills: number;
    education: number;
    projects: number;
  };
  recommendations: Recommendation[];
  processing_time_ms: number;
}

export interface LinkedInAnalysisResult {
  analysis_id: string;
  overall_score: number;
  target_role: string;
  section_scores: {
    title: number;
    about: number;
    experience: number;
    skills: number;
    projects: number;
    education: number;
  };
  title_analysis: {
    current: string;
    issues: string[];
    suggested_variants: string[];
  };
  recommendations: Recommendation[];
  processing_time_ms: number;
}

export interface MarketSkill {
  rank: number;
  name: string;
  slug: string;
  category: string;
  frequency_pct: number;
  job_count: number;
  trend: "rising" | "stable" | "declining";
  change_pct: number;
}

export interface MarketSkillsResponse {
  role: string;
  country: string;
  period: string;
  total_jobs_analyzed: number;
  skills: MarketSkill[];
}

export interface MarketTrendsResponse {
  generated_at: string;
  role: string;
  country: string;
  rising: { skill: string; change_pct: number; period_days: number; message: string }[];
  declining: { skill: string; change_pct: number; period_days: number; message: string }[];
  new_skills: { skill: string; change_pct: number }[];
}
