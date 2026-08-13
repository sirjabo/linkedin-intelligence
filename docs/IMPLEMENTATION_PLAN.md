# LinkedIn Intelligence 2.0 — Implementation Plan

**Date**: 2026-08-13  
**Target**: Transform CV coaching chatbot → AI Job Application Agent  
**Strategy**: Incremental, phase-gated, end-to-end tested at each checkpoint

---

## Definition of Done (per feature)

A feature is done when ALL of these are true:
- [ ] Backend implemented and tested (unit + integration)
- [ ] Frontend implemented if applicable
- [ ] Alembic migration runs forward and backward cleanly
- [ ] Error states handled (not just happy path)
- [ ] Logging with request_id and relevant context
- [ ] Auth scoping enforced (user isolation)
- [ ] Type hints on all new functions
- [ ] End-to-end smoke test passes

---

## Phase 0 — Audit (Complete)

**Deliverables**: ✅ `docs/AUDIT.md`, `docs/ARCHITECTURE_2.0.md`, `docs/MIGRATION_PLAN.md`, `docs/IMPLEMENTATION_PLAN.md`

---

## Phase 1 — Foundation

**Goal**: Secure, testable infrastructure with the new data model. The existing CV coaching feature continues to work on top of the new foundation.

**Duration**: ~2 weeks  
**Branch**: `claude/new-session-ce0sct`

### 1.1 Alembic Setup

- [ ] Install `alembic` and add to `requirements.txt`
- [ ] `alembic init backend/alembic` with async SQLAlchemy configuration
- [ ] Migration 001: capture existing `cv_sessions` + `chat_messages` schema
- [ ] Remove `await conn.run_sync(Base.metadata.create_all)` from `session.py`
- [ ] Add `alembic upgrade head` to app startup check
- [ ] Acceptance: `alembic upgrade head` and `alembic downgrade -1` both work

### 1.2 Dependency Update

- [ ] Add: `alembic`, `python-jose[cryptography]`, `passlib[bcrypt]`, `slowapi`, `structlog`, `redis`
- [ ] Add (dev/test): `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`
- [ ] Create `requirements-dev.txt` for dev-only deps
- [ ] Verify: `pip install -r requirements.txt` succeeds cleanly

### 1.3 User + Auth

- [ ] `app/db/models/user.py`: `User` model (id, email, hashed_password, is_active, created_at)
- [ ] Migration 002: `users` table
- [ ] `app/core/security.py`: JWT creation/validation, password hashing with bcrypt
- [ ] `app/api/deps.py`: `get_current_user` dependency
- [ ] `app/api/routes/auth.py`: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`
- [ ] `app/schemas/auth.py`: request/response schemas
- [ ] Rate limit: 5 req/min on auth endpoints
- [ ] Acceptance: register → login → receive JWT → use JWT on protected endpoint

### 1.4 Candidate Model

- [ ] `app/db/models/candidate.py`: `Candidate`, `CandidateSource`, `CandidateProfile`, `EvidenceRecord`
- [ ] Migration 003: these 4 tables
- [ ] `app/api/routes/candidates.py`: `POST /candidates`, `GET /candidates/{id}`
- [ ] `app/api/routes/sources.py`: `POST /candidates/{id}/sources` (accept PDF or text)
- [ ] Reuse `pdf_extractor.py` for PDF sources
- [ ] All queries scoped: `WHERE candidate.user_id = current_user.id`
- [ ] Acceptance: create candidate → upload CV source → see structured source data

### 1.5 AI Provider Layer

- [ ] `app/services/ai/provider.py`: `LLMProvider` protocol + `AnthropicProvider` implementation
- [ ] `app/services/ai/cost_tracker.py`: log model, tokens, cost per call
- [ ] `app/services/ai/structured.py`: helpers for Anthropic tool_use structured output
- [ ] Migrate `parse_cv_text` → `agents/profile_agent.py::extract_from_source`
  - Use Anthropic `tool_use` instead of JSON string parsing
  - Broader schema: includes `evidence` array per skill/experience
- [ ] Acceptance: upload CV → `ProfileAgent` returns structured `CandidateProfile` with evidence refs

### 1.6 Profile Consolidation

- [ ] `app/agents/profile_agent.py`: `build_profile(sources[]) → CandidateProfile`
- [ ] `POST /candidates/{id}/profile/rebuild`: triggers profile rebuild from all sources
- [ ] Conflict detection: when two sources disagree on dates/titles, flag for user review
- [ ] `GET /candidates/{id}/profile`: returns consolidated profile
- [ ] Acceptance: upload CV + paste LinkedIn → system detects inconsistencies → shows them

### 1.7 Test Infrastructure

- [ ] `backend/tests/conftest.py`: async DB fixtures, test client, mock `LLMProvider`
- [ ] `backend/tests/test_auth.py`: register, login, invalid credentials, expired token
- [ ] `backend/tests/test_candidates.py`: CRUD, user isolation (user A cannot access user B's candidate)
- [ ] `backend/tests/test_profile_agent.py`: extraction accuracy on fixture CVs
- [ ] `backend/tests/fixtures/`: sample CV texts, expected extraction outputs
- [ ] Acceptance: `pytest --cov=app tests/` runs, ≥70% coverage on Phase 1 code, 0 failures

### 1.8 Structured Logging

- [ ] `app/core/logging.py`: structlog with JSON output in prod, pretty in dev
- [ ] Request ID middleware: assign UUID per request, include in all logs
- [ ] Replace all `print()` calls with `structlog.get_logger()`
- [ ] Log on every LLM call: model, input_tokens, output_tokens, cost_usd, duration_ms

### 1.9 Fix Docker Compose

- [ ] Remove or comment out `worker`, `beat`, `flower` services (app.worker doesn't exist)
- [ ] Add health check verification script
- [ ] Acceptance: `docker compose up -d` starts all running services without errors

### Phase 1 Acceptance Criteria

- [ ] `alembic upgrade head` runs cleanly from fresh DB
- [ ] `POST /auth/register` + `POST /auth/login` work
- [ ] All existing `/api/v1/cv/*` routes require auth token
- [ ] Candidate CRUD works with user isolation verified by test
- [ ] CV PDF upload creates `CandidateSource` + triggers `ProfileAgent` extraction
- [ ] Extracted profile includes evidence references
- [ ] `pytest tests/` passes with ≥70% coverage
- [ ] `docker compose up -d` starts without errors

---

## Phase 2 — Job Intelligence

**Goal**: Parse any job description into a structured, queryable format.

**Duration**: ~1 week

### 2.1 Job Model

- [ ] `app/db/models/job.py`: `Job`, `JobRequirement`
- [ ] Migration 004: `jobs`, `job_requirements` tables
- [ ] `app/api/routes/jobs.py`: `POST /jobs/analyze`, `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`
- [ ] `app/schemas/job.py`: request/response schemas

### 2.2 Job Intelligence Agent

- [ ] `app/agents/job_agent.py`: `parse_job_description(raw: str) → JobStructured`
  - Extract: title, company, location, employment_type, seniority, salary, responsibilities
  - Extract: mandatory_requirements, preferred_requirements, skills, tools, languages
  - Extract: education, years_experience, domain, soft_skills, keywords, red_flags
  - Classify each requirement as `mandatory | preferred | inferred | unknown`
  - Never promote an inferred requirement to confirmed
  - Model: `claude-haiku-4-5-20251001` (fast, high volume)
- [ ] `POST /jobs/analyze`: analyze JD without saving (preview)
- [ ] `POST /jobs`: analyze + save

### 2.3 Job Normalization

- [ ] `app/services/job_deduplicator.py`: detect same job from different sources
  - Match on: company + title + location + description similarity
  - Generate canonical job record
- [ ] Deduplication runs on `POST /jobs` before insert

### 2.4 Tests

- [ ] `tests/test_job_agent.py`: 5+ fixture JDs with expected structured output
- [ ] `tests/test_jobs.py`: API tests for job CRUD and deduplication

### Phase 2 Acceptance Criteria

- [ ] Paste raw JD → get structured JSON with requirements classified as mandatory/preferred
- [ ] Same job posted twice → second insert returns existing job ID
- [ ] Tests pass for job parsing with fixture JDs

---

## Phase 3 — Matching Engine

**Goal**: Score candidate fit against a job with explainable reasoning.

**Duration**: ~1.5 weeks

### 3.1 Match Model

- [ ] `app/db/models/match.py`: `MatchAnalysis`
- [ ] Migration 005: `match_analyses` table with scoring weights stored as JSONB

### 3.2 Deterministic Matching

- [ ] `app/matching/deterministic.py`:
  - Skill coverage: candidate skills vs job requirements (exact + alias)
  - Seniority alignment: candidate level vs job seniority
  - Location compatibility: candidate preferences vs job location/remote
  - Experience years: candidate years vs job minimum
  - Language requirements
- [ ] Each component returns `(score: float, evidence: list[str], missing: list[str])`

### 3.3 LLM Reasoning Layer

- [ ] `app/agents/match_agent.py`:
  - Input: `CandidateProfile` + `JobStructured` + deterministic scores
  - Output: `MatchAnalysis` with strengths, gaps, blockers, recommendation, explanation
  - Identify transferable skills (e.g. "customer segmentation" ↔ "segmentación de clientes")
  - Flag blockers: requirements candidate cannot demonstrate
  - Generate recommendation: `APPLY | APPLY_WITH_CUSTOMIZATION | STRETCH | LOW_FIT | DO_NOT_APPLY`
  - Always include confidence alongside score
  - Model: `claude-sonnet-5`

### 3.4 Match API

- [ ] `POST /jobs/{id}/match`: generate and save match analysis
- [ ] `GET /jobs/{id}/match`: return latest match for authenticated candidate
- [ ] Include scoring weights in response (configurable, versioned)

### 3.5 Tests

- [ ] `tests/test_matching.py`: deterministic scoring unit tests (no LLM)
- [ ] `tests/test_match_agent.py`: fixture candidate + job → expected recommendation range
- [ ] Test user isolation: user A cannot see user B's match analysis

### Phase 3 Acceptance Criteria

- [ ] Upload CV → analyze JD → `POST /jobs/{id}/match` → get score + explanation + recommendation
- [ ] Score includes: overall, component breakdown, confidence, strengths list, gaps list, blockers list
- [ ] `DO_NOT_APPLY` for a JD requiring 10 years when candidate has 2
- [ ] Tests pass

---

## Phase 4 — Application Agent (Golden Path)

**Goal**: The full Golden User Journey (spec section 58) works end-to-end.

**Duration**: ~2 weeks

### 4.1 Application Model

- [ ] `app/db/models/application.py`: `Application`, `CVVersion`, `CoverLetter`, `ApplicationAnswer`, `ApplicationEvent`
- [ ] Migration 006: application tables
- [ ] `app/schemas/application.py`: full schema including status enum

### 4.2 Evidence + Anti-Hallucination

- [ ] `app/services/claim_validator.py`: `ClaimValidator`
  - Detect claims in generated text
  - Verify each claim against `evidence_records` for the candidate
  - Return: valid claims, needs_review, rejected
- [ ] All generation agents must return `evidence_refs` with their output
- [ ] Route handlers call `ClaimValidator` before persisting generated content
- [ ] Content with unverified claims is rejected with `EVIDENCE_VALIDATION_FAILED` error

### 4.3 CV Agent

- [ ] `app/agents/cv_agent.py`: `personalize_cv(master_cv, job, match, strategy) → CVVersion`
  - Allowed changes: summary, bullet reordering, skill ordering, project selection, keyword emphasis
  - Prohibited: inventing skills, changing dates, changing titles, inventing metrics
  - Every change includes: original text, new text, rationale, evidence reference
  - Returns `evidence_refs` for each changed section

### 4.4 Communication Agent

- [ ] `app/agents/communication_agent.py`:
  - `generate_cover_letter(candidate, job, match, strategy) → CoverLetter`
  - `generate_application_answers(candidate, job, questions[]) → ApplicationAnswer[]`
  - All output includes `evidence_refs`
  - Common questions: why interested, why hire you, salary, years of experience

### 4.5 Application Agent (Strategy)

- [ ] `app/agents/application_agent.py`:
  - Input: `CandidateProfile + Job + MatchAnalysis`
  - Output: `ApplicationStrategy` with `cv_changes`, `cover_letter_guidance`, `strengths_to_emphasize`, `risks`
  - Question to answer: "How do we maximize interview probability without lying?"

### 4.6 Application API

- [ ] `POST /applications`: create application for candidate + job
- [ ] `GET /applications`: list candidate's applications (with status)
- [ ] `GET /applications/{id}`: full application detail
- [ ] `PATCH /applications/{id}`: update status, notes, outcome
- [ ] `POST /applications/{id}/cv`: generate personalized CV version
- [ ] `POST /applications/{id}/cover-letter`: generate cover letter
- [ ] `POST /applications/{id}/answers`: generate application answers
- [ ] `POST /applications/{id}/events`: record application event (applied, response, interview, etc.)

### 4.7 Application Workspace (Frontend)

- [ ] `/applications` page: kanban board or table by status
- [ ] `/applications/[id]` page: full workspace
  - Job description panel
  - Fit score card (overall, components, confidence)
  - Strengths + gaps list
  - Personalized CV viewer (diff view: original vs adapted)
  - Cover letter viewer
  - Application Q&A
  - Status + notes + follow-up date
  - Event timeline

### 4.8 Candidate Onboarding (Frontend)

- [ ] `/onboarding` multi-step flow:
  - Step 1: Upload CV PDF
  - Step 2: Paste LinkedIn profile (text)
  - Step 3: Set target roles + preferences + remote preference
  - Step 4: Review extracted profile ("This is what we understood about you")
  - Step 5: Confirm or correct inconsistencies
- [ ] Replace `/cv` with `/onboarding`
- [ ] Landing page routes unauthenticated users to `/onboarding`

### 4.9 Remove Legacy Code

- [ ] After all data migrated and end-to-end verified:
  - Remove `/api/v1/cv/upload`, `/api/v1/cv/from-text` (replaced by `/candidates/{id}/sources`)
  - Archive `CVSession` model (rename table, keep data)
  - Remove `stream_cv_chat` XML protocol from `ai_service.py`

### Phase 4 Acceptance Criteria (Golden User Journey)

- [ ] User registers and logs in
- [ ] User uploads CV PDF → profile extracted with evidence
- [ ] User pastes LinkedIn text → merged with CV data, inconsistencies flagged
- [ ] User sets target roles
- [ ] User pastes job description → system parses and structures it
- [ ] System generates match analysis: score + confidence + strengths + gaps + recommendation
- [ ] User clicks "Prepare Application"
- [ ] System generates: personalized CV + cover letter + application answers
- [ ] Every generated item shows: original / adapted / why it changed / evidence used
- [ ] User reviews and clicks "Mark as Applied" → application status updated
- [ ] System creates event timeline
- [ ] User updates status as process evolves
- [ ] All tests pass, ≥70% overall coverage

---

## Phase 5 — Job Discovery

**Goal**: Jobs flow into the system automatically from legal sources.

**Duration**: ~2 weeks

### 5.1 Job Source Interface

- [ ] `app/services/job_sources/base.py`: `JobSource` protocol
  ```python
  class JobSource(Protocol):
      async def search(self, criteria: SearchCriteria) -> list[JobRaw]: ...
      async def get_details(self, job_id: str) -> JobRaw: ...
  ```
- [ ] `app/services/job_sources/manual.py`: user pastes a JD (already works, just wraps it)
- [ ] Implement 1 additional source using a legal public API (e.g. Adzuna, Remotive, RemoteOK, or similar open job board)

### 5.2 Job Recommender

- [ ] `POST /candidates/{id}/job-recommendations`: fetch + rank jobs by candidate fit
- [ ] `/jobs` frontend page: inbox view sorted by recommendation priority

### 5.3 Background Infrastructure (optional, if volume demands)

- [ ] Add Celery + Redis worker module only when sync discovery is too slow
- [ ] Until then: discovery runs synchronously via endpoint call

---

## Phase 6 — Interview Prep

**Duration**: ~1 week

- [ ] `app/agents/interview_agent.py`:
  - Generate technical questions from JD requirements
  - Generate behavioral questions (focus on gaps from match analysis)
  - Generate STAR stories from candidate achievements
  - Generate company research questions
  - Generate questions to ask the interviewer
- [ ] `POST /applications/{id}/interview-prep`
- [ ] Frontend: interview prep tab in application workspace

---

## Phase 7 — Tracking and Analytics

**Duration**: ~1 week

- [ ] Complete `ApplicationEvent` recording
- [ ] `GET /analytics`: outcome stats, response rates by role/company/source
- [ ] `/analytics` frontend page: response rate, funnel, top performing roles/CVs
- [ ] Follow-up reminders: flag applications where `follow_up_date < today`

---

## Phase 8 — Learning Loop

**Duration**: ~2 weeks

- [ ] Analyze outcomes across all applications
- [ ] Detect patterns: role, company, seniority, CV variant, timing
- [ ] Surface insights: "Your response rate is 2.3x higher for Analytics/BI vs Data Science"
- [ ] Distinguish correlation from causation in all reported insights
- [ ] `experiments` table: track scoring weight experiments
- [ ] `GET /recommendations`: personalized job search strategy based on outcomes

---

## Phase 9 — Self Improvement

**Duration**: Ongoing

- [ ] Evaluation datasets: fixture candidates + jobs + expected match decisions
- [ ] Prompt versioning: each agent prompt has a name + version + test cases
- [ ] A/B framework: run two scoring weight variants in parallel, measure outcomes
- [ ] Hallucination rate tracking: percentage of generated claims that fail validation
- [ ] Match calibration: are `APPLY` recommendations actually converting to interviews?

---

## Dependency Chart

```
Phase 0 (Audit) → Phase 1 (Foundation) → Phase 2 (Job Intelligence)
                                       ↘
                                         → Phase 3 (Matching)
                                                            ↘
                                                              → Phase 4 (Application Agent) ← GOLDEN PATH
                                                                                            ↘
                                                                                              → Phase 5, 6, 7, 8, 9
```

Phases 5, 6, 7 can begin in parallel after Phase 4 is complete.

---

## Sprint 002 Definition (Phase 1)

**Goal**: Secure foundation — auth, Alembic, Candidate model, AI provider layer, test infrastructure.

**Acceptance criteria:**
- `alembic upgrade head` from scratch: 3 migrations run cleanly
- `POST /auth/register` + `POST /auth/login` work
- `POST /candidates/{id}/sources` with PDF creates source + triggers profile extraction
- `GET /candidates/{id}/profile` returns structured profile with evidence
- `pytest tests/` passes, ≥70% coverage on new code
- `docker compose up -d` starts without errors (worker/beat/flower removed)
- CI: `ruff check .` + `mypy .` + `pytest` all pass

**Tasks:**
1. `alembic` setup + migration 001 (existing schema)
2. `requirements.txt` + dev deps
3. `users` model + migration 002
4. Auth routes + JWT + `get_current_user`
5. `Candidate` + `CandidateSource` + `CandidateProfile` + `EvidenceRecord` models + migration 003
6. `LLMProvider` protocol + `AnthropicProvider` + `CostTracker`
7. `ProfileAgent.extract_from_source` (structured output, replaces XML parse)
8. Candidate CRUD routes with auth scoping
9. Test infrastructure + test fixtures
10. Structlog setup
11. Docker Compose cleanup
