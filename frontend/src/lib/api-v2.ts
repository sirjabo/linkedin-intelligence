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
    if (res.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("auth:token-expired"));
    }
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// Auth
export function register(email: string, password: string) {
  return req<{ access_token: string; refresh_token: string; token_type: string }>(
    "POST", "/auth/register", undefined, { email, password }
  );
}

export function login(email: string, password: string) {
  return req<{ access_token: string; refresh_token: string; token_type: string }>(
    "POST", "/auth/login", undefined, { email, password }
  );
}

export function refreshTokens(refresh_token: string) {
  return req<{ access_token: string; refresh_token: string; token_type: string }>(
    "POST", "/auth/refresh", undefined, { refresh_token }
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
  match_tier: string;
  deterministic_score: number;
  llm_score: number | null;
  skill_overlap_score: number | null;
  experience_score: number | null;
  location_score: number | null;
  education_score: number | null;
  llm_reasoning: string | null;
  llm_strengths: string[];
  llm_gaps: string[];
  recommendation: string | null;
  created_at: string;
  // legacy aliases (kept for backwards compat)
  tier?: string;
  reasoning?: string | null;
  strengths?: string[];
  gaps?: string[];
}

export function runMatch(token: string, jobId: string) {
  return req<MatchResult>("POST", `/jobs/${jobId}/match`, token);
}

export function getMatch(token: string, jobId: string) {
  return req<MatchResult>("GET", `/jobs/${jobId}/match`, token);
}

export function recordMatchOutcome(token: string, jobId: string, outcome: string) {
  return req<MatchResult>("POST", `/jobs/${jobId}/match/feedback`, token, { outcome });
}

// Applications
export interface Application {
  id: string;
  job_id: string;
  job_title?: string | null;
  job_company?: string | null;
  status: string;
  notes: string | null;
  follow_up_date: string | null;
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

export function updateApplication(
  token: string,
  id: string,
  data: { status?: string; notes?: string | null; follow_up_date?: string | null; applied_at?: string | null }
) {
  return req<Application>("PATCH", `/applications/${id}`, token, data);
}

export function addEvent(token: string, appId: string, event_type: string, notes?: string) {
  return req<AppEvent>("POST", `/applications/${appId}/events`, token, { event_type, notes });
}

export interface ApplicationAnswer {
  id: string;
  question: string;
  answer: string;
  evidence_refs: unknown[] | null;
  created_at: string;
}

export function generateAnswers(token: string, appId: string, questions: string[]) {
  return req<ApplicationAnswer[]>("POST", `/applications/${appId}/answers`, token, { questions });
}

export interface TechnicalQuestion { question: string; rationale: string }
export interface BehavioralQuestion { question: string; competency: string }
export interface STARStory { competency: string; situation: string; task: string; action: string; result: string }
export interface CompanyResearch { culture: string; mission: string; values: string }

export interface InterviewPrep {
  id: string;
  application_id: string;
  technical_questions: TechnicalQuestion[];
  behavioral_questions: BehavioralQuestion[];
  star_stories: STARStory[];
  questions_to_ask: string[];
  company_research: CompanyResearch;
  created_at: string;
  updated_at: string;
}

// Stats
export interface ApplicationStats {
  total: number;
  funnel: Record<string, number>;
  active: number;
  offers: number;
  rejected: number;
}

export function getApplicationStats(token: string) {
  return req<ApplicationStats>("GET", "/applications/stats/summary", token);
}

export function generateInterviewPrep(token: string, appId: string) {
  return req<InterviewPrep>("POST", `/applications/${appId}/interview-prep`, token);
}

export function getInterviewPrep(token: string, appId: string) {
  return req<InterviewPrep>("GET", `/applications/${appId}/interview-prep`, token);
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

// getRecommendations is defined below with sources support

// Candidates
export interface Candidate {
  id: string;
  user_id: string;
  name: string | null;
  email: string | null;
  location: string | null;
  target_roles: string[] | null;
  preferences: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateSource {
  id: string;
  candidate_id: string;
  source_type: string;
  source_url: string | null;
  extracted_content: Record<string, unknown> | null;
  extraction_confidence: number | null;
  created_at: string;
}

export interface CandidateProfile {
  id: string;
  candidate_id: string;
  summary: string | null;
  professional_identity: Record<string, unknown> | null;
  career_level: string | null;
  industries: unknown[] | null;
  competencies: unknown[] | null;
  skills: unknown[] | null;
  experience: unknown[] | null;
  education: unknown[] | null;
  projects: unknown[] | null;
  certifications: unknown[] | null;
  achievements: unknown[] | null;
  conflicts: unknown[] | null;
  version: number;
  rebuilt_at: string;
}

export function getCandidate(token: string) {
  return req<Candidate>("GET", "/candidates/me", token);
}

export function updateCandidate(token: string, data: Partial<Pick<Candidate, "name" | "email" | "location" | "target_roles">>) {
  return req<Candidate>("PUT", "/candidates/me", token, data);
}

export function ingestTextSource(token: string, source_type: string, raw_text: string) {
  return req<CandidateSource>("POST", "/candidates/me/sources/text", token, { source_type, raw_text });
}

export function listSources(token: string) {
  return req<CandidateSource[]>("GET", "/candidates/me/sources", token);
}

export function rebuildProfile(token: string) {
  return req<CandidateProfile>("POST", "/candidates/me/profile/rebuild", token);
}

export function getProfile(token: string) {
  return req<CandidateProfile>("GET", "/candidates/me/profile", token);
}

export interface ProfileHealth {
  score: number;
  passed: number;
  total: number;
  checks: Record<string, boolean>;
  tips: string[];
}

export function getProfileHealth(token: string) {
  return req<ProfileHealth>("GET", "/candidates/me/health", token);
}

// Agent session
export interface AgentField {
  id: string;
  label: string;
  field_type: string;
  semantic_type: string;
  is_required: boolean;
  auto_fill_value: string | null;
  human_required: boolean;
  human_answer: string | null;
  options: string[] | null;
}

export interface AgentSession {
  session_id: string;
  application_id: string;
  status: string;
  ats_name: string | null;
  form_url: string | null;
  fields_total: number;
  fields_auto_filled: number;
  fields_human_pending: number;
  fields_confirmed: number;
  avg_confidence: number | null;
  confirmation_id: string | null;
  final_url: string | null;
  error_message: string | null;
  fields: AgentField[] | null;
}

export function startAgent(token: string, appId: string, formUrl: string) {
  return req<AgentSession>("POST", `/applications/${appId}/agent/start`, token, { form_url: formUrl });
}

export function getAgentStatus(token: string, appId: string) {
  return req<AgentSession>("GET", `/applications/${appId}/agent/status`, token);
}

export function answerAgentField(token: string, appId: string, fieldId: string, value: string) {
  return req<AgentSession>(
    "POST", `/applications/${appId}/agent/answer/${fieldId}`, token, { field_id: fieldId, value }
  );
}

export function previewAgent(token: string, appId: string) {
  return req<AgentSession>("POST", `/applications/${appId}/agent/preview`, token);
}

export function submitAgent(token: string, appId: string, humanConfirmed: boolean) {
  return req<AgentSession>(
    "POST", `/applications/${appId}/agent/submit`, token, { human_confirmed: humanConfirmed }
  );
}

// Fit analysis, decision, outcome
export interface FitAnalysis {
  job_fit_score: number;
  match_tier: string;
  matched_skills: string[];
  missing_skills: string[];
  career_fit_score: number | null;
  skill_overlap_score: number | null;
  experience_score: number | null;
  location_score: number | null;
  llm_reasoning: string | null;
  llm_strengths: string[];
  llm_gaps: string[];
}

export interface DecisionResult {
  decision: string;
  blockers: string[];
  overall_approach: string | null;
}

export interface OutcomeResult {
  outcome: string;
  match_tier: string;
}

export function getFitAnalysis(token: string, appId: string) {
  return req<FitAnalysis>("GET", `/applications/${appId}/fit-analysis`, token);
}

export function getDecision(token: string, appId: string) {
  return req<DecisionResult>("GET", `/applications/${appId}/decision`, token);
}

export function recordOutcome(token: string, appId: string, outcome: string) {
  return req<OutcomeResult>("POST", `/applications/${appId}/outcome`, token, { outcome });
}

// Agent answers (list + edit)
export function listAgentAnswers(token: string, appId: string) {
  return req<ApplicationAnswer[]>("GET", `/applications/${appId}/agent/answers`, token);
}

export function updateAgentAnswer(token: string, appId: string, answerId: string, answer: string) {
  return req<ApplicationAnswer>("PATCH", `/applications/${appId}/agent/answers/${answerId}`, token, { answer });
}

// Profile Optimizer
export interface SkillGap {
  skill: string;
  frequency: number;
}

export interface OptimizationTip {
  priority: number;
  category: string;
  tip: string;
  evidence: string;
  impact: "high" | "medium" | "low";
}

export interface OptimizationReport {
  total_analyses_reviewed: number;
  summary: string;
  top_skill_gaps: SkillGap[];
  tips: OptimizationTip[];
}

export function getProfileOptimizer(token: string) {
  return req<OptimizationReport>("GET", "/candidates/me/profile-optimizer", token);
}

// Job Radar
export function getJobSources() {
  return req<{ sources: string[] }>("GET", "/recommendations/sources", undefined);
}

export function getRecommendations(
  token: string,
  query?: string,
  sources?: string[]
) {
  return req<Recommendation[]>("POST", "/recommendations", token, {
    query: query ?? "",
    limit: 20,
    sources: sources ?? null,
  });
}
