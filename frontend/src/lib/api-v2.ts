const BASE = "/api/v2";

function authHeader(token: string) {
  return { Authorization: `Bearer ${token}` };
}

async function req<T>(
  method: string,
  path: string,
  token?: string,
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) Object.assign(headers, authHeader(token));
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// Auth
export function register(email: string, password: string) {
  return req<{ access_token: string; token_type: string }>(
    "POST", "/auth/register", undefined, { email, password }
  );
}

export function login(email: string, password: string) {
  return req<{ access_token: string; token_type: string }>(
    "POST", "/auth/login", undefined, { email, password }
  );
}

// Jobs
export interface Job {
  id: string;
  title: string | null;
  company: string | null;
  location: string | null;
  remote_type: string | null;
  seniority: string | null;
  tech_stack: string[] | null;
  status: string;
  created_at: string;
}

export function createJob(token: string, raw_jd: string) {
  return req<Job>("POST", "/jobs", token, { raw_jd });
}

export function listJobs(token: string) {
  return req<Job[]>("GET", "/jobs", token);
}

export function getJob(token: string, id: string) {
  return req<Job>("GET", `/jobs/${id}`, token);
}

// Match
export interface MatchResult {
  id: string;
  job_id: string;
  overall_score: number;
  tier: string;
  deterministic_score: number;
  llm_score: number | null;
  reasoning: string | null;
  strengths: string[];
  gaps: string[];
  recommendation: string | null;
  created_at: string;
}

export function runMatch(token: string, jobId: string) {
  return req<MatchResult>("POST", `/jobs/${jobId}/match`, token);
}

export function getMatch(token: string, jobId: string) {
  return req<MatchResult>("GET", `/jobs/${jobId}/match`, token);
}

// Applications
export interface Application {
  id: string;
  job_id: string;
  status: string;
  notes: string | null;
  applied_at: string | null;
  created_at: string;
  cv_versions: CVVersion[];
  cover_letters: CoverLetter[];
  events: AppEvent[];
  strategy: Record<string, unknown> | null;
}

export interface CVVersion {
  id: string;
  summary_adapted: string | null;
  headline_adapted: string | null;
  changes: unknown[];
  created_at: string;
}

export interface CoverLetter {
  id: string;
  content: string;
  created_at: string;
}

export interface AppEvent {
  id: string;
  event_type: string;
  notes: string | null;
  occurred_at: string;
}

export function createApplication(token: string, job_id: string) {
  return req<Application>("POST", "/applications", token, { job_id });
}

export function listApplications(token: string) {
  return req<Application[]>("GET", "/applications", token);
}

export function getApplication(token: string, id: string) {
  return req<Application>("GET", `/applications/${id}`, token);
}

export function generateCV(token: string, appId: string) {
  return req<CVVersion>("POST", `/applications/${appId}/cv`, token);
}

export function generateCoverLetter(token: string, appId: string) {
  return req<CoverLetter>("POST", `/applications/${appId}/cover-letter`, token);
}

export function addEvent(token: string, appId: string, event_type: string, notes?: string) {
  return req<AppEvent>("POST", `/applications/${appId}/events`, token, { event_type, notes });
}

// Recommendations
export interface Recommendation {
  external_id: string;
  title: string;
  company: string;
  location: string;
  remote_type: string;
  url: string;
  tech_tags: string[];
  salary_range: string | null;
  score: number;
  matched_keywords: string[];
}

export function getRecommendations(token: string, query?: string) {
  return req<Recommendation[]>("POST", "/recommendations", token, { query: query ?? "", limit: 20 });
}
