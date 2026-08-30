import { createClient, type SupabaseClient } from "@supabase/supabase-js";

declare global {
  interface Window {
    __ENV__?: { SUPABASE_URL: string; SUPABASE_KEY: string; API_URL: string };
  }
}

function getSupabaseConfig(): { url: string; key: string } {
  // Prefer runtime-injected values (set by the server component in layout.tsx),
  // fall back to build-time baked NEXT_PUBLIC_* values if available.
  const url =
    (typeof window !== "undefined" && window.__ENV__?.SUPABASE_URL) ||
    process.env.NEXT_PUBLIC_SUPABASE_URL ||
    "";
  const key =
    (typeof window !== "undefined" && window.__ENV__?.SUPABASE_KEY) ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    "";
  return { url, key };
}

let _client: SupabaseClient | undefined;

// Lazy singleton — only created in the browser (inside useEffect/handlers),
// never at module import time (which would crash Next.js prerendering).
export function getSupabase(): SupabaseClient {
  if (!_client) {
    const { url, key } = getSupabaseConfig();
    _client = createClient(url, key);
  }
  return _client;
}

export async function getAccessToken(): Promise<string | null> {
  const {
    data: { session },
  } = await getSupabase().auth.getSession();
  return session?.access_token ?? null;
}
