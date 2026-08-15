# LinkedIn Intelligence 2.0 — Architecture

**Version**: 2.0  
**Date**: 2026-08-13  
**Status**: Approved for implementation

---

## 1. Core Concept Shift

| Aspect | v1 (current) | v2.0 |
|--------|-------------|------|
| Primary entity | `CVSession` | `Candidate + Job + Application` |
| User model | Anonymous session | Authenticated user with isolated data |
| AI role | CV editing coach | Job Application Agent |
| Data model | JSONB blob | Normalized relational + JSONB for unstructured |
| Schema management | `create_all` at startup | Alembic migrations |
| AI protocol | XML tag parsing | Structured output (tool_use) |
| Background work | None | Redis + Celery (Phase 5+) |
| Tests | None | pytest + pytest-asyncio from Phase 1 |

---

## 2. Domain Model

### Entities and Relationships

```
User
 └── Candidate (1:1)
      ├── CandidateSource[] (CV, LinkedIn, GitHub, portfolio, manual)
      ├── CandidateProfile (consolidated master profile)
      │    ├── Experience[]
      │    ├── Skill[] (with Evidence[])
      │    ├── Achievement[]
      │    ├── Project[]
      │    ├── Education[]
      │    └── Certification[]
      ├── CVVersion[] (versioned CV snapshots)
      └── Application[]
           ├── Job
           │    └── JobRequirement[]
           ├── MatchAnalysis
           ├── CVVersion (personalized for this job)
           ├── CoverLetter
           ├── ApplicationAnswer[]
           └── ApplicationEvent[]
```

### Key Design Decisions

1. **Evidence is the atomic unit of truth.** Every skill, achievement, and bullet point must reference an `Evidence` record. The AI can reformat evidence but cannot create it.

2. **CVVersion is immutable after creation.** The master CV is always the latest `CVVersion` where `job_id IS NULL`. Job-specific versions fork from it.

3. **MatchAnalysis records its own model version and scoring weights.** This enables the learning loop to compare results across algorithm versions.

4. **Application is the operational record.** Every action taken toward a job opportunity is recorded as an `ApplicationEvent`.

---

## 3. Data Model

### Core Tables

```sql
-- Authentication
users (id, email, hashed_password, is_active, created_at)

-- Candidate identity
candidates (id, user_id FK, name, email, location, target_roles JSONB,
            preferences JSONB, created_at, updated_at)

-- Raw sources ingested by the candidate
candidate_sources (id, candidate_id FK, source_type ENUM, source_url,
                   raw_content TEXT, extracted_content JSONB,
                   extraction_confidence FLOAT, created_at, updated_at)

-- Consolidated master profile (rebuilt from sources)
candidate_profiles (id, candidate_id FK, summary TEXT,
                    professional_identity JSONB, career_level VARCHAR,
                    competencies JSONB, skills JSONB, experience JSONB,
                    education JSONB, projects JSONB, certifications JSONB,
                    achievements JSONB, rebuilt_at, version INT)

-- Individual evidence records (traceable claims)
evidence_records (id, candidate_id FK, claim TEXT, evidence_type VARCHAR,
                  source_ref VARCHAR, source_text TEXT, strength FLOAT,
                  created_at)

-- Job opportunities
jobs (id, title, company, url, location, remote BOOL, salary_range JSONB,
      source VARCHAR, description_raw TEXT, description_structured JSONB,
      discovered_at, status VARCHAR)

-- Parsed job requirements
job_requirements (id, job_id FK, requirement TEXT, req_type ENUM,
                  category VARCHAR, skill VARCHAR, years_required INT,
                  importance FLOAT, confidence FLOAT)

-- Match analysis between candidate and job
match_analyses (id, candidate_id FK, job_id FK, overall_score FLOAT,
                technical_score FLOAT, experience_score FLOAT,
                seniority_score FLOAT, domain_score FLOAT,
                keyword_score FLOAT, preference_score FLOAT,
                strengths JSONB, gaps JSONB, blockers JSONB,
                recommendation VARCHAR, explanation TEXT,
                scoring_weights JSONB, algorithm_version VARCHAR,
                model_version VARCHAR, generated_at)

-- Application record (one per candidate+job)
applications (id, candidate_id FK, job_id FK, status ENUM,
              applied_at, source VARCHAR, cv_version_id FK,
              cover_letter_id FK, notes TEXT, follow_up_date DATE,
              outcome VARCHAR, rejection_reason TEXT, response_date)

-- Versioned CV snapshots
cv_versions (id, candidate_id FK, job_id FK NULLABLE,
             base_version_id FK NULLABLE, content JSONB,
             changes JSONB, rationale TEXT, evidence_refs JSONB,
             ats_analysis JSONB, created_at)

-- Cover letters
cover_letters (id, application_id FK, content TEXT, evidence_refs JSONB,
               generated_at, version INT)

-- Application answers (free-form questions)
application_answers (id, application_id FK, question TEXT, answer TEXT,
                     evidence_refs JSONB, created_at)

-- Full audit trail of events
application_events (id, application_id FK, event_type VARCHAR,
                    payload JSONB, created_at)

-- Experiments for the learning loop
experiments (id, name VARCHAR, hypothesis TEXT, variant JSONB, metric VARCHAR,
             sample_size INT, result FLOAT, confidence FLOAT,
             decision VARCHAR, created_at, concluded_at)
```

### Application Status State Machine

```
discovered → saved → analyzing → recommended
                              → rejected_by_agent
         → preparing → ready → applied → screening → interview → offer
                                      → rejected
                                      → withdrawn
                                      → archived
```

---

## 4. Backend Architecture

```
backend/app/
├── main.py                    # FastAPI app, lifespan, middleware
├── core/
│   ├── config.py              # Pydantic Settings v2
│   ├── security.py            # JWT, password hashing
│   └── logging.py             # structlog config
├── api/
│   ├── deps.py                # get_db, get_current_user
│   └── routes/
│       ├── auth.py            # POST /auth/register, /auth/login, /auth/refresh
│       ├── candidates.py      # CRUD + profile rebuild
│       ├── sources.py         # CV/LinkedIn/GitHub ingestion
│       ├── jobs.py            # Job CRUD + JD analysis
│       ├── matches.py         # Match analysis
│       ├── applications.py    # Application lifecycle
│       ├── cv_versions.py     # CV generation + export
│       └── analytics.py       # Outcomes, learning insights
├── db/
│   ├── base.py                # DeclarativeBase
│   ├── session.py             # Async session factory
│   └── models/
│       ├── user.py
│       ├── candidate.py
│       ├── job.py
│       ├── match.py
│       ├── application.py
│       └── experiment.py
├── schemas/
│   ├── auth.py
│   ├── candidate.py
│   ├── job.py
│   ├── match.py
│   └── application.py
├── services/
│   ├── ai/
│   │   ├── provider.py        # LLMProvider protocol + Anthropic implementation
│   │   ├── structured.py      # Structured output helpers
│   │   └── cost_tracker.py    # Token + cost accounting
│   ├── agents/
│   │   ├── profile_agent.py   # Understands the candidate
│   │   ├── job_agent.py       # Parses job descriptions
│   │   ├── match_agent.py     # Candidate × Job matching
│   │   ├── application_agent.py # Strategy: what to write, how
│   │   ├── cv_agent.py        # Generates personalized CV versions
│   │   └── communication_agent.py # Cover letter, application answers
│   ├── pdf_extractor.py       # (existing, reused)
│   ├── pdf_generator.py       # (existing, adapted for CVVersion)
│   └── claim_validator.py     # Anti-hallucination: checks evidence
├── matching/
│   ├── deterministic.py       # Skill/seniority/location/salary matching
│   ├── semantic.py            # Embedding-based similarity (Phase 3)
│   └── scoring.py             # Weighted score composition
└── alembic/
    ├── env.py
    └── versions/
        └── 001_foundation.py
```

### AI Provider Layer

```python
class LLMProvider(Protocol):
    async def generate(self, system: str, messages: list, model: str,
                       max_tokens: int) -> str: ...
    async def structured_output(self, system: str, messages: list,
                                schema: type[BaseModel], model: str) -> BaseModel: ...
    async def stream(self, system: str, messages: list,
                     model: str) -> AsyncGenerator[str, None]: ...
```

All agents use `LLMProvider` — never the Anthropic SDK directly. This enables:
- Model swapping without agent changes
- Centralized cost tracking
- Centralized retry / backoff
- Mock provider for tests

### Model Selection Policy

| Operation | Model | Reason |
|-----------|-------|--------|
| CV/JD parsing, extraction | `claude-haiku-4-5-20251001` | Fast, cheap, structured |
| Skill normalization, dedup | `claude-haiku-4-5-20251001` | High volume |
| Match analysis, gap reasoning | `claude-sonnet-5` | Reasoning quality |
| CV personalization, cover letter | `claude-sonnet-5` | Quality of generation |
| Strategy agent | `claude-sonnet-5` | Complex reasoning |

---

## 5. Frontend Architecture

### Route Map

```
/                        → Dashboard (candidate overview, job matches, active apps)
/onboarding              → Multi-step profile setup
/onboarding/cv           → CV upload
/onboarding/linkedin     → LinkedIn paste
/onboarding/goals        → Target roles, preferences
/onboarding/review       → "This is what we understood about you"
/jobs                    → Job inbox (discovered, saved, recommended)
/jobs/[id]               → Job detail + fit analysis
/jobs/[id]/apply         → Application workspace
/applications            → Application tracker (kanban/table)
/applications/[id]       → Application detail + all generated materials
/applications/[id]/cv    → Personalized CV viewer/editor
/applications/[id]/cover → Cover letter viewer
/analytics               → Learning insights, outcome tracking
/profile                 → Candidate profile editor
```

### Component Strategy

- Preserve `ChatInterface.tsx` → rename to `ApplicationCopilot.tsx`, adapt SSE for 2.0 agent events
- Preserve `CVPreview.tsx` → rename to `CVVersionPreview.tsx`, adapt for `CVVersion` schema
- Preserve `CVUpload.tsx` → move to `/onboarding/cv` step, adapt for source ingestion
- Replace landing page with authenticated dashboard
- Add `JobCard.tsx`, `MatchScoreCard.tsx`, `ApplicationKanban.tsx`, `FitBadge.tsx`

---

## 6. Agent Architecture

Each agent is a stateless async function that takes typed inputs and returns typed outputs. No global state. Agents call the `LLMProvider` protocol.

```
ProfileAgent(candidate_sources[]) → CandidateProfile

JobAgent(job_description_raw: str) → JobStructured + JobRequirement[]

MatchAgent(candidate_profile, job_structured) → MatchAnalysis

ApplicationAgent(candidate_profile, job, match_analysis) → ApplicationStrategy

CVAgent(master_cv_version, job, match_analysis, strategy) → CVVersion

CommunicationAgent(candidate_profile, job, match_analysis, strategy) →
    CoverLetter + ApplicationAnswer[]
```

Agents do NOT persist to DB. The route handlers orchestrate agents and persist results. This keeps agents testable in isolation.

---

## 7. Anti-Hallucination Architecture

The system enforces that generated content can be traced to evidence.

```python
class Evidence(BaseModel):
    claim: str
    evidence_type: Literal["experience", "skill", "project", "education", "achievement"]
    source_ref: str       # e.g. "experience:bbva:2021-2024"
    source_text: str      # verbatim text from the candidate's profile
    strength: float       # 0.0-1.0

class ClaimValidator:
    def validate(self, generated_text: str, evidence: list[Evidence]) -> ValidationResult:
        # Returns: valid claims, claims_needing_review, rejected_claims
```

The `CVAgent` and `CommunicationAgent` are required to return `evidence_refs` alongside every generated section. The route handler calls `ClaimValidator` before persisting to DB. Content without evidence support is rejected.

---

## 8. Scoring Architecture

### Match Score Components

| Component | Default Weight | Configurable |
|-----------|---------------|-------------|
| Mandatory requirements coverage | 30% | Yes |
| Skills match | 20% | Yes |
| Relevant experience | 20% | Yes |
| Seniority alignment | 10% | Yes |
| Semantic similarity | 10% | Yes |
| Domain match | 5% | Yes |
| Preference alignment | 5% | Yes |

Scores are always presented with a `confidence` alongside the score. The system never presents a score as ground truth.

### Recommendation Levels

| Score | Confidence | Output |
|-------|-----------|--------|
| ≥80 | ≥70 | `APPLY` |
| 65-79 | ≥60 | `APPLY_WITH_CUSTOMIZATION` |
| 50-64 | any | `STRETCH` |
| 30-49 | any | `LOW_FIT` |
| <30 | any | `DO_NOT_APPLY` |
| any | <50 | `INSUFFICIENT_DATA` |

---

## 9. Security

| Requirement | Implementation |
|-------------|---------------|
| Authentication | JWT (HS256), 1h access token, 7d refresh token |
| Authorization | All DB queries scoped with `WHERE candidate.user_id = current_user.id` |
| File uploads | MIME validation, 10MB limit, path traversal protection, temp-only storage |
| Secrets | Environment variables only, never committed |
| Rate limiting | SlowAPI, 30 req/min unauthenticated, 120 req/min authenticated |
| Input validation | Pydantic on all inputs |
| SQL injection | SQLAlchemy ORM only, no raw string queries |

---

## 10. Observability

| Layer | Tool | What's captured |
|-------|------|----------------|
| Structured logs | structlog | request_id, user_id, model, tokens, latency, cost |
| Request IDs | middleware | UUID per request, propagated through async calls |
| LLM calls | cost_tracker | model, input_tokens, output_tokens, cost_usd, prompt_version |
| Errors | structlog | error code, trace_id, retryable flag |

Never log: API keys, raw CV text, personal data in log messages.

---

## 11. Background Jobs (Phase 5+)

Until Celery is genuinely needed, long operations run as `asyncio.create_task` within the request lifecycle or as async endpoints that return a job ID immediately.

When Celery is added:
- Job discovery / crawling
- Batch match analysis
- Embedding generation
- Nightly learning analytics

---

## 12. Key ADRs

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-2.1 | Anthropic SDK directly (not LangChain) | LangChain not installed; Anthropic SDK is simpler for this use case |
| ADR-2.2 | Alembic from Phase 1 | `create_all` is not acceptable for production |
| ADR-2.3 | Structured output over XML tags | Tool use is more reliable than string parsing |
| ADR-2.4 | Agents are stateless functions | Easier to test, easier to compose |
| ADR-2.5 | Evidence model from Phase 1 | Anti-hallucination is a core invariant, not an add-on |
| ADR-2.6 | Defer Celery to Phase 5 | Don't add infrastructure before it's needed |
| ADR-2.7 | JWT auth with user isolation | Security is non-negotiable from Phase 1 |
