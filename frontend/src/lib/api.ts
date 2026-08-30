import { CVData } from "@/types/cv";
import { getAccessToken } from "./supabase";

// Use relative path so Next.js rewrites proxy to the backend — avoids build-time
// NEXT_PUBLIC_API_URL baking issues. Falls back to window.__ENV__ if set.
function getBase(): string {
  if (typeof window !== "undefined" && window.__ENV__?.API_URL) {
    const raw = window.__ENV__.API_URL.trim().replace(/\/$/, "").replace(/\/api\/v[12]$/, "");
    if (raw) return raw;
  }
  return "";  // empty → relative /api/v1/... caught by next.config rewrites
}
const BASE = getBase();

async function authHeader(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function uploadCV(file: File): Promise<{ id: string; cv_data: CVData }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/v1/cv/upload`, {
    method: "POST",
    headers: await authHeader(),
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createCVFromText(text: string): Promise<{ id: string; cv_data: CVData }> {
  const res = await fetch(`${BASE}/api/v1/cv/from-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSession(id: string): Promise<{ id: string; cv_data: CVData }> {
  const res = await fetch(`${BASE}/api/v1/cv/${id}`, {
    headers: await authHeader(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function chatStream(sessionId: string, message: string): Promise<ReadableStream<string>> {
  const token = await getAccessToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}/api/v1/cv/${sessionId}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message }),
  });

  if (!res.ok || !res.body) {
    throw new Error("Chat request failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  return new ReadableStream<string>({
    async start(controller) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        controller.enqueue(decoder.decode(value, { stream: true }));
      }
      controller.close();
    },
    cancel() {
      reader.cancel();
    },
  });
}

export function getPdfUrl(sessionId: string): string {
  return `${BASE}/api/v1/cv/${sessionId}/pdf`;
}
