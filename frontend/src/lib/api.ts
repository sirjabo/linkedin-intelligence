import { CVData } from "@/types/cv";

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
