import { CVData } from "@/types/cv";
import {
  CVAnalysisResult,
  LinkedInAnalysisResult,
  MarketSkillsResponse,
  MarketTrendsResponse,
  TargetRole,
} from "@/types/analysis";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadCV(file: File): Promise<{ id: string; cv_data: CVData }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/v1/cv/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createCVFromText(text: string): Promise<{ id: string; cv_data: CVData }> {
  const res = await fetch(`${BASE}/api/v1/cv/from-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSession(id: string): Promise<{ id: string; cv_data: CVData }> {
  const res = await fetch(`${BASE}/api/v1/cv/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function chatStream(sessionId: string, message: string): ReadableStream<string> {
  const controller = new AbortController();

  return new ReadableStream({
    async start(c) {
      const res = await fetch(`${BASE}/api/v1/cv/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        c.error(new Error("Chat request failed"));
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        c.enqueue(decoder.decode(value, { stream: true }));
      }
      c.close();
    },
    cancel() {
      controller.abort();
    },
  });
}

export function getPdfUrl(sessionId: string): string {
  return `${BASE}/api/v1/cv/${sessionId}/pdf`;
}

async function parseError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const body = JSON.parse(text) as { detail?: { message?: string } | string };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail && typeof body.detail === "object" && body.detail.message) {
      return body.detail.message;
    }
  } catch {
    /* use raw text */
  }
  return text || `Request failed (${res.status})`;
}

export async function analyzeCV(payload: {
  cv_text: string;
  target_role: TargetRole;
}): Promise<CVAnalysisResult> {
  const res = await fetch(`${BASE}/api/v1/analyze/cv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function analyzeCVFile(
  file: File,
  targetRole: TargetRole,
): Promise<CVAnalysisResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("target_role", targetRole);
  const res = await fetch(`${BASE}/api/v1/analyze/cv`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function analyzeLinkedIn(payload: {
  profile_text: string;
  target_role: TargetRole;
}): Promise<LinkedInAnalysisResult> {
  const res = await fetch(`${BASE}/api/v1/analyze/linkedin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getMarketSkills(
  role: TargetRole,
  country = "AR",
): Promise<MarketSkillsResponse> {
  const res = await fetch(
    `${BASE}/api/v1/market/skills/${role}?country=${country}&limit=50`,
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getMarketTrends(role: TargetRole): Promise<MarketTrendsResponse> {
  const res = await fetch(`${BASE}/api/v1/market/trends?role=${role}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
