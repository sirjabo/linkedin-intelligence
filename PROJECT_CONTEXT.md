# LinkedIn Intelligence — Contexto completo del proyecto

> Documento generado el 2026-08-13. Pegalo en ChatGPT o Claude para tener todo el contexto en una sola sesión.

---

## 1. Qué es esto

**LinkedIn Intelligence** es una plataforma de inteligencia de mercado laboral que ayuda a profesionales tech a:
- Analizar ofertas de trabajo con IA
- Comparar su perfil contra los requisitos (Match Score)
- Generar CVs y cartas de presentación personalizadas por oferta
- Recibir recomendaciones de trabajos externos rankeados por fit
- Prepararse para entrevistas con preguntas técnicas, behavioral, STAR stories

**Repositorio:** `sirjabo/linkedin-intelligence`  
**Branch activo:** `claude/new-session-ce0sct`

---

## 2. Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy 2.0 async |
| Base de datos | PostgreSQL (producción) + SQLite in-memory (tests) |
| ORM / Migrations | SQLAlchemy async + Alembic |
| Auth | JWT manual (hmac/hashlib/base64, sin cffi) + passlib pbkdf2_sha256 |
| AI | Anthropic claude-haiku-4-5-20251001 via tool_use structured output |
| HTTP client externo | httpx 0.28.0 |
| Frontend | Next.js 15 + React 19 + TypeScript + Tailwind CSS + lucide-react |
| Tests | pytest-asyncio + httpx AsyncClient + SQLite StaticPool |

---

## 3. Arquitectura del backend

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py              # get_current_user (JWT decode)
│   │   └── routes/
│   │       ├── auth.py          # POST /auth/register, /auth/login
│   │       ├── candidates.py    # POST /candidates/sources, GET /candidates/profile
│   │       ├── jobs.py          # POST /jobs, GET /jobs, GET /jobs/{id}
│   │       ├── match.py         # POST /jobs/{id}/match, GET /jobs/{id}/match
│   │       ├── applications.py  # CRUD + /cv, /cover-letter, /answers, /events
│   │       ├── interview.py     # POST/GET /applications/{id}/interview-prep
│   │       └── recommendations.py # POST /recommendations
│   ├── core/
│   │   ├── config.py            # Settings (DATABASE_URL, ANTHROPIC_API_KEY, SECRET_KEY)
│   │   ├── security.py          # JWT create/verify, password hash/verify
│   │   └── logging.py           # structlog config
│   ├── db/
│   │   ├── base.py              # SQLAlchemy Base
│   │   ├── session.py           # async engine + get_db()
│   │   └── models/
│   │       ├── user.py          # User
│   │       ├── candidate.py     # Candidate, CandidateSource, CandidateProfile, EvidenceRecord
│   │       ├── job.py           # Job, JobRequirement
│   │       ├── match.py         # MatchAnalysis
│   │       ├── application.py   # Application, CVVersion, CoverLetter, ApplicationAnswer, ApplicationEvent
│   │       ├── interview.py     # InterviewPrep
│   │       └── cv_session.py    # CVSession, ChatMessage (legacy)
│   ├── schemas/                 # Pydantic response models
│   │   ├── auth.py
│   │   ├── candidate.py
│   │   ├── job.py
│   │   ├── match.py
│   │   ├── application.py
│   │   ├── interview.py
│   │   └── recommendation.py
│   └── services/
│       ├── ai/
│       │   └── provider.py      # LLMProvider Protocol + AnthropicProvider
│       ├── agents/
│       │   ├── profile_agent.py     # ExtractedProfile, consolidate_profiles
│       │   ├── job_agent.py         # ParsedJob, parse_job_description
│       │   ├── match_agent.py       # LLMMatchResult, reason_about_match
│       │   ├── application_agent.py # ApplicationStrategy, generate_strategy
│       │   ├── cv_agent.py          # PersonalizedCV, personalize_cv
│       │   ├── communication_agent.py # CoverLetterResult, AnswerResult, generate_*
│       │   └── interview_agent.py   # InterviewPrepResult, generate_interview_prep
│       ├── matching/
│       │   └── engine.py        # deterministic scoring engine
│       ├── job_sources/
│       │   ├── base.py          # JobRaw dataclass + JobSource Protocol
│       │   └── remotive.py      # RemotiveSource (httpx → remotive.com/api/remote-jobs)
│       ├── job_recommender.py   # rank_jobs (keyword overlap scoring)
│       └── claim_validator.py   # validate_claims (deterministic, no LLM)
└── alembic/
    └── versions/
        ├── 001_foundation.py    # users, candidates, candidate_sources, candidate_profiles, evidence_records
        ├── 002_jobs.py          # jobs, job_requirements
        ├── 003_match.py         # match_analyses
        ├── 004_applications.py  # applications, cv_versions, cover_letters, application_answers, application_events
        └── 005_interview.py     # interview_preps
```

---

## 4. API v2 — Contratos completos

### Auth
```
POST /api/v2/auth/register   { email, password } → { access_token, token_type }
POST /api/v2/auth/login      { email, password } → { access_token, token_type }
```

### Candidates
```
POST /api/v2/candidates/sources  { source_type, raw_content|source_url }
GET  /api/v2/candidates/profile
GET  /api/v2/candidates/evidence
```

### Jobs
```
POST /api/v2/jobs            { raw_jd } → Job
GET  /api/v2/jobs            → Job[]
GET  /api/v2/jobs/{id}       → Job
```

### Match
```
POST /api/v2/jobs/{id}/match  → MatchAnalysis
GET  /api/v2/jobs/{id}/match  → MatchAnalysis
```

MatchAnalysis fields:
- `overall_score` (0.0–1.0): `det_score * 0.60 + llm_score * 0.40`
- `tier`: excellent≥0.85 | strong≥0.70 | moderate≥0.55 | weak≥0.40 | poor≥0.00
- `deterministic_score`: skill_overlap×0.40 + experience×0.30 + location×0.20 + education×0.10
- `strengths`, `gaps`, `recommendation`: from LLM

### Applications
```
POST   /api/v2/applications              { job_id } → Application (status=draft)
GET    /api/v2/applications              → Application[]
GET    /api/v2/applications/{id}         → Application (with cv_versions, cover_letters, events, strategy)
PATCH  /api/v2/applications/{id}         { status?, notes?, follow_up_date? }
POST   /api/v2/applications/{id}/cv      → CVVersion  (generates strategy if not cached)
POST   /api/v2/applications/{id}/cover-letter → CoverLetter  (requires strategy)
POST   /api/v2/applications/{id}/answers { questions: str[] } → AnswerResult[]
POST   /api/v2/applications/{id}/events  { event_type, notes? } → ApplicationEvent
```

Application status flow: `draft → applied → phone_screen → interview → offer | rejected | withdrawn`

Events auto-advance status and set `applied_at` on first "applied" event.

### Interview Prep
```
POST /api/v2/applications/{id}/interview-prep  → InterviewPrepResponse (upsert)
GET  /api/v2/applications/{id}/interview-prep  → InterviewPrepResponse
```

InterviewPrepResponse contains:
- `technical_questions`: [{question, rationale}] ×5
- `behavioral_questions`: [{question, competency}] ×5
- `star_stories`: [{competency, situation, task, action, result}] ×3
- `questions_to_ask`: str[] ×5
- `company_research`: {culture, mission, values}

### Recommendations
```
POST /api/v2/recommendations  { query?, limit?, category? } → RecommendedJob[]
```

RecommendedJob:
- `external_id`, `title`, `company`, `location`, `remote_type`, `url`
- `tech_tags`, `salary_range`, `published_at`
- `score` (0.0–1.0): jaccard-like keyword overlap vs. candidate profile
- `matched_keywords`: list of matching keywords

---

## 5. LLM Provider

```python
# Protocol
class LLMProvider(Protocol):
    async def generate(self, prompt: str, tools: list[dict], tool_choice: dict) -> dict:
        ...

# Implementation: AnthropicProvider
# Model: claude-haiku-4-5-20251001
# All agents use tool_use structured output (never free text parsing)
```

### Patrón de agentes

Cada agente:
1. Define un JSON Schema como tool (`input_schema`)
2. Llama `provider.generate(prompt, tools=[schema], tool_choice={"type": "tool", "name": "..."})`
3. La respuesta es siempre un dict validado contra un Pydantic BaseModel

---

## 6. Modelo de datos clave

### User → Candidate (1:1, auto-created on register)
### Candidate → CandidateProfile (1:1, created after source processing)
### Candidate → Job (1:N)
### Job → MatchAnalysis (1:1 per candidate, unique constraint on candidate_id+job_id)
### Candidate → Application (1:N)
### Application → [CVVersion, CoverLetter, ApplicationAnswer, ApplicationEvent, InterviewPrep]

### Application.strategy (JSON)
Se genera una sola vez (primer POST /cv), se cachea en `Application.strategy`. Las llamadas subsiguientes a `/cover-letter` y `/answers` lo leen del caché.

---

## 7. Matching Engine (determinístico)

```python
DET_WEIGHT = 0.60
LLM_WEIGHT = 0.40

# Deterministic weights
skill_overlap = 0.40  # Jaccard: shared_skills / union_skills
experience    = 0.30  # seniority distance: 1.0 if match, 0.60 if ±1, 0.30 if ±2, 0.0 if >2
location      = 0.20  # 1.0 same city, 0.80 same country/remote, 0.60 hybrid, 0.40 remote, 0.0 mismatch
education     = 0.10  # 1.0 CS degree, 0.80 STEM, 0.60 other, 0.50 bootcamp, 0.30 none listed

# Seniority rank
SENIORITY_RANK = {intern:1, junior:2, mid:3, senior:4, staff/lead/manager:5, principal:6, director:7, vp:8, c-level:9}
```

---

## 8. ClaimValidator

```python
# Deterministic, no LLM
# Extracts sentences containing quantitative claims (regex: \d+\s*(%|years?|months?|x|\+|k|M|B|$))
# Checks keyword overlap between claim sentence and EvidenceRecord.source_text
# Requires ≥3 matching tokens to consider claim "verified"

result.is_clean       # True if all claims verified
result.verified_claims
result.unverified_claims
result.to_dict()
```

---

## 9. Frontend (Next.js 15)

```
frontend/src/
├── lib/
│   ├── api.ts        # Legacy v1 client (CV coaching chatbot)
│   ├── api-v2.ts     # v2 client (auth, jobs, match, applications, recommendations)
│   └── auth.tsx      # AuthContext + AuthProvider (localStorage JWT)
├── components/
│   ├── MatchScoreCard.tsx   # Score bar + tier + strengths/gaps
│   ├── Navbar.tsx           # Legacy
│   ├── CVUpload.tsx         # Legacy
│   ├── CVPreview.tsx        # Legacy
│   └── ChatInterface.tsx    # Legacy
└── app/
    ├── layout.tsx           # Root layout con AuthProvider
    ├── page.tsx             # Landing page (dark slate-950)
    ├── login/page.tsx       # Login form
    ├── register/page.tsx    # Register form
    ├── dashboard/page.tsx   # Job list + create job form
    ├── jobs/[id]/page.tsx   # Job detail + match score + create application
    ├── applications/page.tsx          # Application list
    └── applications/[id]/page.tsx     # Application workspace (CV, cover letter, events)
```

**Tema:** `bg-slate-950` (fondo), `bg-slate-900` (cards), `border-slate-800`, `text-blue-600/400/300` (accents)

---

## 10. Tests

| Suite | Tests | Qué cubre |
|-------|-------|-----------|
| test_auth.py | ~10 | register, login, JWT, protección |
| test_candidates.py | ~15 | sources, profile building, evidence |
| test_jobs.py | ~10 | create, list, parse |
| test_match.py | 14 | engine unit (5) + integration (9) |
| test_applications.py | 20 | CRUD, golden path, CV, cover letter, answers, events |
| test_recommendations.py | 14 | unit scoring + integration (Remotive mocked) |
| test_interview.py | 8 | success, shape, upsert, isolation |
| **Total** | **90** | **90 passing** |

Configuración clave del conftest:
- `TEST_DB_URL = "sqlite+aiosqlite:///:memory:"` con `StaticPool`
- Todos los agentes LLM mocked (no hay llamadas reales a Anthropic en tests)
- `mock_remotive` mockea `RemotiveSource.fetch` (sin HTTP real)
- Fixtures: `mock_job_agent`, `mock_match_agent`, `mock_application_agents`, `mock_interview_agent`, `mock_remotive`, `mock_profile_agent`

---

## 11. Decisiones arquitectónicas importantes

| Decisión | Razón |
|----------|-------|
| JWT manual (sin PyJWT/jose) | cffi no disponible en el entorno |
| passlib pbkdf2_sha256 (sin bcrypt) | bcrypt incompatible con el entorno |
| `Uuid(as_uuid=True)` y `JSON` (no JSONB) | Compatibilidad SQLite/PostgreSQL |
| Upsert via SELECT+update/insert | Compatibilidad SQLite (no ON CONFLICT DO UPDATE para UUID primary keys) |
| `selectinload()` explícito en todas las queries | Evitar MissingGreenlet en async SQLAlchemy |
| Strategy cacheada en Application.strategy | ApplicationStrategy es caro de generar (1 llamada LLM); se reutiliza para CV, cover letter, answers |
| `DET_WEIGHT = 0.60` | El scoring determinístico es más confiable que el LLM para match técnico |
| claude-haiku-4-5-20251001 para todos los agentes | Volumen alto, latencia baja, costo bajo |

---

## 12. Variables de entorno requeridas

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/linkedin_intel
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=your-secret-key-min-32-chars
ENVIRONMENT=development
```

---

## 13. Comandos de desarrollo

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

# Build
npm run build
```

---

## 14. Qué falta / próximos pasos sugeridos

- **Candidatos**: UI para subir CV / LinkedIn / GitHub (actualmente solo API)
- **Perfil**: Dashboard de skills gap con gráfico radar
- **Recomendaciones**: UI page `/recommendations` para explorar trabajos externos
- **Interview Prep**: UI page en `/applications/[id]/interview-prep`
- **Notifications**: Email cuando hay match alto
- **Docker Compose**: Actualizar para incluir backend v2 con las variables correctas
- **CI/CD**: GitHub Actions con `pytest` + `npm run build`
- **Vectorstore (pgvector)**: Búsqueda semántica de evidencias para el ClaimValidator
- **Candidate onboarding**: Flow guiado post-registro para subir CV/LinkedIn

---

## 15. Historial de commits (feature branches)

```
2b996ef feat: Phase 5 (Job Discovery), Phase 6 (Interview Prep), Frontend v2 UI
67fa5ab feat: Phase 4 — Application Agent golden path end-to-end
0324a25 feat: Phase 3 — hybrid matching engine with deterministic + LLM scoring
d6d75ec feat: Phase 2 — Job Intelligence (JobAgent, routes, migration, tests)
863199a feat: Phase 1 — auth, candidate model, Alembic, LLM provider, tests
70337d4 docs: Phase 0 audit — AUDIT, ARCHITECTURE_2.0, MIGRATION_PLAN, IMPLEMENTATION_PLAN
```
