# LinkedIn Intelligence — Contexto completo del proyecto

> Última actualización: 2026-08-14. Usalo en ChatGPT o Claude para tener todo el contexto del proyecto.
>
> **Branch activo:** `claude/new-session-ce0sct` del repo `sirjabo/linkedin-intelligence`

---

## 1. Qué es esto

**LinkedIn Intelligence** es una plataforma de inteligencia de mercado laboral que ayuda a profesionales tech a:

- Analizar ofertas de trabajo con IA y calcular un Match Score determinístico + LLM
- Generar CVs y cartas de presentación personalizadas por oferta
- Completar formularios de postulación automáticamente con un agente de browser
- Recibir recomendaciones de trabajos externos rankeados por fit (Remotive, Arbeitnow, RemoteOK)
- Prepararse para entrevistas con preguntas técnicas, behavioral, STAR stories
- Optimizar su perfil basándose en el historial de análisis de match

---

## 2. Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy 2.0 async |
| Base de datos | PostgreSQL (producción) + SQLite in-memory (tests) |
| ORM / Migrations | SQLAlchemy async + Alembic |
| Auth | JWT manual (hmac/hashlib/base64) + passlib pbkdf2_sha256 |
| AI | Anthropic claude-haiku-4-5-20251001 via tool_use structured output |
| Browser | Playwright async (headless Chromium) |
| HTTP client | httpx 0.28.0 |
| Frontend | Next.js 15 + React 19 + TypeScript + Tailwind CSS + lucide-react |
| Tests | pytest-asyncio + httpx AsyncClient + respx (HTTP mocking) + SQLite StaticPool |

---

## 3. Arquitectura del backend

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── auth.py              # POST /auth/register, /auth/login, /auth/refresh
│   │       ├── candidates.py        # /candidates/me (GET/PUT), /sources, /profile, /health, /profile-optimizer
│   │       ├── jobs.py              # POST /jobs, GET /jobs, GET /jobs/{id}
│   │       ├── match.py             # POST/GET /jobs/{id}/match, POST /jobs/{id}/match/feedback
│   │       ├── applications.py      # CRUD + /cv, /cover-letter, /answers, /events, /fit-analysis, /decision, /outcome
│   │       ├── agent.py             # /applications/{id}/agent/* (start, status, answer, preview, submit, answers CRUD)
│   │       ├── interview.py         # POST/GET /applications/{id}/interview-prep
│   │       └── recommendations.py  # POST /recommendations (multi-source), GET /recommendations/sources
│   ├── core/
│   │   ├── config.py                # Settings (DATABASE_URL, ANTHROPIC_API_KEY, SECRET_KEY, UPLOAD_DIR)
│   │   ├── security.py              # JWT create/verify, password hash/verify
│   │   ├── logging.py               # structlog config
│   │   ├── limiter.py               # slowapi rate limiter
│   │   └── ssrf.py                  # validate_url_not_private (block private IP ranges)
│   ├── db/
│   │   ├── base.py                  # SQLAlchemy Base
│   │   ├── session.py               # async engine + get_db()
│   │   └── models/
│   │       ├── user.py              # User
│   │       ├── candidate.py         # Candidate, CandidateSource, CandidateProfile, EvidenceRecord
│   │       ├── job.py               # Job, JobRequirement
│   │       ├── match.py             # MatchAnalysis
│   │       ├── application.py       # Application, CVVersion, CoverLetter, ApplicationAnswer, ApplicationEvent, ApplicationSubmission
│   │       ├── form.py              # ApplicationForm, ApplicationFormField
│   │       ├── agent_session.py     # ApplicationAgentSession (10-state machine)
│   │       └── interview.py         # InterviewPrep
│   ├── schemas/
│   │   ├── auth.py, candidate.py, job.py, match.py, application.py
│   │   ├── agent.py                 # AgentSessionResponse, AgentFieldAnswerRequest, ApplicationAnswerResponse
│   │   ├── interview.py, recommendation.py
│   ├── services/
│   │   ├── ai/provider.py           # LLMProvider Protocol + AnthropicProvider
│   │   ├── agents/
│   │   │   ├── profile_agent.py
│   │   │   ├── job_agent.py
│   │   │   ├── match_agent.py
│   │   │   ├── application_agent.py
│   │   │   ├── cv_agent.py
│   │   │   ├── communication_agent.py
│   │   │   └── interview_agent.py
│   │   ├── ats/
│   │   │   ├── base.py              # ATSAdapter Protocol
│   │   │   ├── registry.py          # detect_ats(url) → ATSAdapter
│   │   │   ├── greenhouse.py        # GreenhouseAdapter
│   │   │   ├── lever.py             # LeverAdapter (iframe + /apply navigation)
│   │   │   ├── workday.py           # WorkdayAdapter (Apply button + aria_label normalization)
│   │   │   ├── smart_recruiters.py  # SmartRecruitersAdapter (GDPR banner + Apply)
│   │   │   └── ashby.py             # AshbyAdapter (/application URL check)
│   │   ├── browser/
│   │   │   ├── adapter.py           # BrowserAutomationAdapter Protocol (includes switch_to_frame, get_current_url)
│   │   │   └── playwright_adapter.py # PlaywrightAdapter (frame support, _active_frame)
│   │   ├── job_sources/
│   │   │   ├── base.py              # JobRaw dataclass + JobSource Protocol
│   │   │   ├── remotive.py          # RemotiveSource
│   │   │   ├── arbeitnow.py         # ArbeitnowSource (arbeitnow.com/api/job-board-api)
│   │   │   └── remoteok.py          # RemoteOKSource (remoteok.com/api, skips legal notice)
│   │   ├── matching/engine.py       # deterministic scoring engine
│   │   ├── job_recommender.py       # rank_jobs — TF-IDF cosine similarity (field-weighted IDF corpus)
│   │   ├── form_intelligence.py     # classify_field() + classify_field_llm() (LLM fallback for "unknown")
│   │   ├── candidate_knowledge_resolver.py # CandidateKnowledgeResolver
│   │   ├── application_agent_orchestrator.py # 3-phase: start (discover+map) → resume → submit
│   │   ├── profile_optimizer.py     # generate_optimization_report, _aggregate_skill_gaps, _deterministic_tips
│   │   ├── learning_loop.py         # compute_calibration (outcome feedback → scoring adjustment)
│   │   └── claim_validator.py       # validate_claims (deterministic, no LLM)
└── alembic/versions/
    ├── 001_foundation.py    # users, candidates, candidate_sources, candidate_profiles, evidence_records
    ├── 002_jobs.py          # jobs, job_requirements
    ├── 003_match.py         # match_analyses
    ├── 004_applications.py  # applications, cv_versions, cover_letters, application_answers, application_events, application_submissions
    ├── 005_interview.py     # interview_preps
    └── 006_agent.py         # application_forms, application_form_fields, application_agent_sessions
```

---

## 4. API v2 — Endpoints completos

### Auth

```
POST /api/v2/auth/register   { email, password }         → { access_token, refresh_token, token_type }
POST /api/v2/auth/login      { email, password }         → { access_token, refresh_token, token_type }
POST /api/v2/auth/refresh    { refresh_token }           → { access_token, refresh_token, token_type }
```

### Candidates

```
GET  /api/v2/candidates/me                  → Candidate
PUT  /api/v2/candidates/me                  { name?, email?, location?, target_roles? } → Candidate
GET  /api/v2/candidates/me/sources          → CandidateSource[]
POST /api/v2/candidates/me/sources/text     { source_type, raw_text }  → CandidateSource
POST /api/v2/candidates/me/sources/file     (multipart: file, source_type)            → CandidateSource
GET  /api/v2/candidates/me/profile          → CandidateProfile
POST /api/v2/candidates/me/profile/rebuild  → CandidateProfile (re-runs LLM extraction)
GET  /api/v2/candidates/me/health           → ProfileHealth { score, passed, total, checks, tips }
GET  /api/v2/candidates/me/profile-optimizer → OptimizationReport (ver § Profile Optimizer)
```

### Jobs

```
POST /api/v2/jobs            { raw_jd }  → Job (triggers LLM parse)
GET  /api/v2/jobs            → Job[]
GET  /api/v2/jobs/{id}       → Job
```

Job fields: `id, title, company, location, remote_type, seniority, tech_stack, status, created_at`

### Match

```
POST /api/v2/jobs/{id}/match          → MatchAnalysis  (deterministic + LLM, stores result)
GET  /api/v2/jobs/{id}/match          → MatchAnalysis  (last stored)
POST /api/v2/jobs/{id}/match/feedback { outcome }     → MatchAnalysis  (records interview/offer/rejected outcome)
```

MatchAnalysis fields:
- `overall_score` (0.0–1.0): `det_score × 0.60 + llm_score × 0.40`
- `match_tier`: `excellent≥0.85 | strong≥0.70 | moderate≥0.55 | weak≥0.40 | poor<0.40`
- `deterministic_score`: skill_overlap×0.40 + experience×0.30 + location×0.20 + education×0.10
- `llm_score`, `llm_reasoning`, `llm_strengths[]`, `llm_gaps[]`
- `matched_skills[]`, `missing_skills[]`, `recommendation`

### Applications

```
POST   /api/v2/applications                 { job_id }          → Application (status=draft)
GET    /api/v2/applications                 → Application[]
GET    /api/v2/applications/stats/summary   → ApplicationStats { total, funnel, active, offers, rejected }
GET    /api/v2/applications/{id}            → Application (with cv_versions, cover_letters, events, strategy)
PATCH  /api/v2/applications/{id}            { status?, notes?, follow_up_date?, applied_at? } → Application
POST   /api/v2/applications/{id}/cv         → CVVersion
POST   /api/v2/applications/{id}/cover-letter → CoverLetter
POST   /api/v2/applications/{id}/answers    { questions: str[] } → ApplicationAnswer[]
POST   /api/v2/applications/{id}/events     { event_type, notes? } → AppEvent
GET    /api/v2/applications/{id}/fit-analysis → FitAnalysis
GET    /api/v2/applications/{id}/decision   → DecisionResult { decision, blockers, overall_approach }
POST   /api/v2/applications/{id}/outcome    { outcome }          → OutcomeResult
```

Application status flow: `draft → applied → phone_screen → interview → offer | rejected | withdrawn`

### Interview Prep

```
POST /api/v2/applications/{id}/interview-prep → InterviewPrepResponse (upsert)
GET  /api/v2/applications/{id}/interview-prep → InterviewPrepResponse
```

InterviewPrepResponse:
- `technical_questions`: [{question, rationale}] ×5
- `behavioral_questions`: [{question, competency}] ×5
- `star_stories`: [{competency, situation, task, action, result}] ×3
- `questions_to_ask`: str[] ×5
- `company_research`: {culture, mission, values}

### Application Agent (Browser Automation)

```
POST /api/v2/applications/{id}/agent/start                   { form_url }       → AgentSession
GET  /api/v2/applications/{id}/agent/status                  → AgentSession
POST /api/v2/applications/{id}/agent/answer/{field_id}       { field_id, value } → AgentSession
POST /api/v2/applications/{id}/agent/preview                 → AgentSession (with fields)
POST /api/v2/applications/{id}/agent/submit                  { human_confirmed: true } → AgentSession
GET  /api/v2/applications/{id}/agent/answers                 → ApplicationAnswer[]
PATCH /api/v2/applications/{id}/agent/answers/{answer_id}   { answer }          → ApplicationAnswer
```

AgentSession fields: `session_id, application_id, status, ats_name, form_url, fields_total, fields_auto_filled, fields_human_pending, fields_confirmed, avg_confidence, confirmation_id, final_url, error_message, fields[]`

Agent status machine: `initializing → discovering → mapping → awaiting_human → ready_to_fill → filling → submitting → submitted | failed`

**Invariante de seguridad:** `submit` requiere `human_confirmed: true`. Sin confirmación explícita → 400 error. El agente nunca envía un formulario sin aprobación humana.

### Recommendations

```
GET  /api/v2/recommendations/sources → { sources: ["remotive", "arbeitnow", "remoteok"] }
POST /api/v2/recommendations         { query?, limit?, sources? } → RecommendedJob[]
```

RecommendedJob: `external_id, title, company, location, remote_type, url, tech_tags, salary_range, score, matched_keywords`

Las fuentes se consultan en paralelo (`asyncio.gather`). Deduplicación por URL. Score por TF-IDF cosine similarity vs. perfil del candidato.

---

## 5. ATS Adapters

El sistema detecta automáticamente el ATS en base a la URL del formulario y aplica lógica específica antes de descubrir el formulario.

| Adapter | URL Pattern | before_discover() | normalize_field() |
|---------|-------------|-------------------|-------------------|
| `GreenhouseAdapter` | `greenhouse.io` | No-op | Default |
| `LeverAdapter` | `jobs.lever.co` | Navega a `/apply`, cambia a iframe | Default |
| `WorkdayAdapter` | `myworkdayjobs.com` | Clickea botón Apply | Prefiere `aria_label` > `label` |
| `SmartRecruitersAdapter` | `smartrecruiters.com` | Descarta banner GDPR, clickea Apply | Default |
| `AshbyAdapter` | `jobs.ashbyhq.com` | Navega a `/application` si no está ahí | Default |

**BrowserAutomationAdapter Protocol** (implementado por `PlaywrightAdapter`):
- `open_url(url)`, `discover_form()`, `fill_text()`, `select_option()`, `check_checkbox()`, `upload_file()`
- `click_next()`, `has_element(selector)`, `capture_screenshot()`, `is_confirmation_page()`
- `switch_to_frame(selector)`, `switch_to_main_frame()`, `get_current_url()`

---

## 6. Form Intelligence

```python
# Clasificación determinística por label regex
classify_field(label: str) → SemanticType

# Fallback LLM cuando classify_field devuelve "unknown"
classify_field_llm(label, placeholder, options, field_type) → SemanticType
# Usa claude-haiku-4-5-20251001 · max_tokens=20 · respuesta single-token
# Falla silenciosamente → devuelve "unknown"

# SemanticTypes incluyen:
# first_name, last_name, full_name, email, phone, linkedin_url, github_url,
# portfolio_url, cover_letter, resume_file, work_authorization, salary_expectation,
# years_of_experience, availability, location, gender, ethnicity, veteran_status,
# disability_status, referral, custom_text, unknown
```

---

## 7. Profile Optimizer

```
GET /api/v2/candidates/me/profile-optimizer → OptimizationReport
```

```python
OptimizationReport:
  total_analyses_reviewed: int
  summary: str                  # LLM-generated si hay gaps, sino determinístico
  top_skill_gaps: SkillGap[]   # [{ skill: "kafka", frequency: 3 }, ...]
  tips: OptimizationTip[]       # [{ priority, category, tip, evidence, impact }]

# Categorías de tips: "skill" | "experience" | "summary" | "profile_completeness"
# Impact: "high" | "medium" | "low"
# Fuente: _aggregate_skill_gaps() cuenta missing_skills de todos los MatchAnalysis
```

---

## 8. Job Recommender — TF-IDF

```python
# Sin dependencias externas. IDF calculado sobre el corpus de trabajos en tiempo real.
# Pesos por campo: tech_tags (×3), title (×2), description (×1)
# Pesos candidato: skills (×3), summary/experience (×1)
# Score: cosine similarity entre vectores TF-IDF ponderados

rank_jobs(jobs: list[JobRaw], profile_data: dict) → list[ScoredJob]
# ScoredJob: { job, score (0.0–1.0), matched_keywords }
```

---

## 9. Matching Engine (determinístico)

```python
DET_WEIGHT = 0.60   # peso del score determinístico
LLM_WEIGHT = 0.40   # peso del score LLM

# Subescores determinísticos
skill_overlap = 0.40  # Jaccard: skills compartidas / unión
experience    = 0.30  # distancia de seniority (1.0 si match, 0.6 si ±1, 0.3 si ±2)
location      = 0.20  # 1.0 misma ciudad, 0.8 remoto/mismo país, 0.0 mismatch
education     = 0.10  # 1.0 CS degree, 0.8 STEM, 0.6 other, 0.5 bootcamp, 0.3 none

# Seniority rank
SENIORITY_RANK = {intern:1, junior:2, mid:3, senior:4, staff/lead/manager:5, principal:6, director:7, vp:8, c_level:9}
```

---

## 10. LLM Provider

```python
class LLMProvider(Protocol):
    async def generate(self, prompt: str, tools: list[dict], tool_choice: dict) -> dict: ...

# Implementación: AnthropicProvider
# Modelo: claude-haiku-4-5-20251001
# Todos los agentes usan tool_use structured output (sin free text parsing)
# Patrón: define JSON Schema como tool → llama generate → parsea con Pydantic
```

---

## 11. Modelo de datos

```
User (1:1) → Candidate
Candidate (1:1) → CandidateProfile
Candidate (1:N) → CandidateSource
Candidate (1:N) → Job
Job (1:1 per candidate) → MatchAnalysis    # unique(candidate_id, job_id)
Candidate (1:N) → Application
Application → Job  (FK)
Application (1:N) → [CVVersion, CoverLetter, ApplicationAnswer, ApplicationEvent]
Application (1:1) → ApplicationForm → ApplicationFormField[]
Application (1:N) → ApplicationAgentSession
Application (0:N) → ApplicationSubmission
Application (0:1) → InterviewPrep
```

`Application.strategy` (JSON): se genera una sola vez y se cachea. Las llamadas a `/cv`, `/cover-letter` y `/answers` lo reutilizan.

---

## 12. Decisions arquitectónicas

| Decisión | Razón |
|----------|-------|
| JWT manual (sin PyJWT/jose) | cffi no disponible en el entorno de deploy |
| passlib pbkdf2_sha256 (sin bcrypt) | bcrypt incompatible con el entorno |
| `Uuid(as_uuid=True)` y `JSON` (no JSONB) | Compatibilidad SQLite/PostgreSQL en tests |
| Upsert via SELECT+update/insert | Compatibilidad SQLite (no ON CONFLICT para UUID PKs) |
| `selectinload()` explícito | Evitar MissingGreenlet en async SQLAlchemy |
| Strategy cacheada en Application.strategy | Generar strategy es caro (1 LLM call); se reutiliza para CV/cover-letter/answers |
| `DET_WEIGHT = 0.60` | Scoring determinístico más confiable que LLM para match técnico |
| TF-IDF sobre Jaccard para job ranking | IDF penaliza términos genéricos, boost para skills raros/específicos |
| before_discover() después de open_url() | ATS adapters necesitan ver la página cargada para detectar botones/banners |
| human_confirmed=true requerido para submit | Invariante de seguridad: ningún formulario se envía sin aprobación explícita |

---

## 13. Tests

| Suite | Tests | Qué cubre |
|-------|-------|-----------|
| test_auth.py | ~10 | register, login, JWT, protección |
| test_candidates.py | ~15 | sources, profile building, evidence |
| test_jobs.py | ~10 | create, list, parse |
| test_match.py | 14 | engine unit + integration |
| test_applications.py | 20 | CRUD, CV, cover letter, answers, events, stats |
| test_recommendations.py | 18 | unit scoring TF-IDF + integration (mocked HTTP) |
| test_interview.py | 8 | success, shape, upsert, isolation |
| test_p2_form_intelligence_llm.py | 7 | classify_field_llm (mocked Anthropic) |
| test_p2_lever_adapter.py | 7 | Lever before_discover, iframe, url patterns |
| test_p2_agent_answers.py | 6 | list/update agent answers endpoints |
| test_p3_job_sources.py | 6 | Arbeitnow + RemoteOK fetch (respx mocked) |
| test_p3_profile_optimizer.py | 10 | _aggregate_skill_gaps, _deterministic_tips, generate_optimization_report |
| test_p3_ats_adapters.py | 12 | Workday, SmartRecruiters, Ashby adapters |
| test_p3_job_recommender_tfidf.py | 16 | TF-IDF keywords, IDF computation, cosine scoring |
| **Total** | **~344** | **344 passed, 5 skipped** |

Configuración del conftest:
- `TEST_DB_URL = "sqlite+aiosqlite:///:memory:"` con `StaticPool`
- Todos los agentes LLM mocked (sin llamadas reales a Anthropic en tests)
- `respx` mockea llamadas HTTP externas (Remotive, Arbeitnow, RemoteOK)
- Fixtures: `mock_job_agent`, `mock_match_agent`, `mock_application_agents`, `mock_interview_agent`, `mock_remotive`, `mock_profile_agent`

---

## 14. Variables de entorno

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/linkedin_intel
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=your-secret-key-min-32-chars
ENVIRONMENT=development
UPLOAD_DIR=/tmp/uploads
```

---

## 15. Comandos de desarrollo

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Tests
pytest --cov=app tests/ -q

# Frontend
cd frontend
npm install
npm run dev    # → http://localhost:3000
```

---

## 16. Frontend (Next.js 15)

```
frontend/src/
├── lib/
│   ├── api-v2.ts     # Cliente completo v2 (auth, jobs, match, applications, agent, recommendations, profile optimizer)
│   └── auth.tsx      # AuthContext + AuthProvider (localStorage JWT + token refresh)
├── components/
│   ├── MatchScoreCard.tsx
│   └── Navbar.tsx    # Links: Mi Perfil, Skills Radar, Mercado, Postulaciones
└── app/
    ├── layout.tsx
    ├── page.tsx                          # Landing
    ├── login/page.tsx, register/page.tsx
    ├── dashboard/page.tsx                # Job list + crear job
    ├── jobs/[id]/page.tsx                # Match score + crear application
    ├── applications/page.tsx             # Application list
    └── applications/[id]/page.tsx        # Workspace: CV, cover letter, events, agent UI
```

Interfaces TypeScript en `api-v2.ts`:
- `Job`, `MatchResult`, `Application`, `CVVersion`, `CoverLetter`, `AppEvent`
- `AgentSession`, `AgentField`, `ApplicationAnswer`
- `FitAnalysis`, `DecisionResult`, `OutcomeResult`
- `InterviewPrep`, `TechnicalQuestion`, `BehavioralQuestion`, `STARStory`
- `Recommendation`, `Candidate`, `CandidateProfile`, `ProfileHealth`
- `SkillGap`, `OptimizationTip`, `OptimizationReport`

---

## 17. Historial de fases completadas

| Fase | Descripción | Tests |
|------|-------------|-------|
| P0 | Auth, Candidate model, Alembic, LLM provider | 10 |
| P1 | Job Intelligence (JobAgent, parse, routes) | +10 |
| P2 | Hybrid matching engine (deterministic + LLM) | +14 |
| P3 | Application CRUD + AI pipeline (CV, cover letter, answers) | +20 |
| P4 | Application Agent browser automation (PlaywrightAdapter) | — |
| P5 | Job Discovery (Remotive source, recommendations) | +14 |
| P6 | Interview Prep | +8 |
| P7 | Frontend v2 UI | — |
| P8-P9 | Fit Analysis, Decision, Outcome, Application Stats | — |
| P10 | Form Intelligence LLM fallback (`classify_field_llm`) | +7 |
| P11 | Browser Protocol (frame support), Lever Adapter | +7 |
| P12 | Agent Answer endpoints (list + edit) | +6 |
| P13 | Frontend Agent UI (Postulaciones nav, api-v2 agent functions) | — |
| P14 | Job Radar: Arbeitnow + RemoteOK sources (multi-source parallel) | +6 |
| P15-P16 | ATS Adapters: Workday, SmartRecruiters, Ashby | +12 |
| P18 | Profile Optimizer (skill gap aggregation + deterministic tips) | +10 |
| P17 | TF-IDF cosine similarity job recommender (field-weighted IDF) | +16 |
