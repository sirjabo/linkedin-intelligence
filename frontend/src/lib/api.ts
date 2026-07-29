/** Typed HTTP client for LinkedIn Intelligence API */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type TargetRole = "ai_engineer" | "data_engineer" | "analytics_engineer";

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

export interface SectionScores {
  contact: number;
  summary: number;
  experience: number;
  skills: number;
  education: number;
  projects: number;
}

export interface Recommendation {
  priority: number;
  section: string;
  type: "add_keyword" | "rewrite_bullet" | "add_section";
  message: string;
  impact: "very_high" | "high" | "medium" | "low";
  original?: string | null;
  suggested?: string | null;
}

export interface CVAnalysisResponse {
  analysis_id: string;
  ats_score: number;
  target_role: TargetRole;
  summary: string;
  keyword_analysis: {
    found: KeywordFound[];
    missing: KeywordMissing[];
  };
  section_scores: SectionScores;
  recommendations: Recommendation[];
  processing_time_ms: number;
}

export interface AnalyzeCVInput {
  cvText?: string;
  file?: File;
  targetRole: TargetRole;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Error ${res.status}`;
    try {
      const body = (await res.json()) as {
        detail?: { message?: string } | string;
      };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail?.message) {
        message = body.detail.message;
      }
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  analyze: {
    async cv(input: AnalyzeCVInput): Promise<CVAnalysisResponse> {
      const form = new FormData();
      form.append("target_role", input.targetRole);
      if (input.file) {
        form.append("file", input.file);
      }
      if (input.cvText) {
        form.append("cv_text", input.cvText);
      }

      const res = await fetch(`${API_BASE}/analyze/cv`, {
        method: "POST",
        body: form,
      });
      return handleResponse<CVAnalysisResponse>(res);
    },
  },
};
