# LinkedIn Intelligence — Audit Report
**Date**: 2026-08-13  
**Branch**: `claude/new-session-ce0sct`  
**Spec**: LinkedIn Intelligence 2.0 Master Brief

---

## Executive Summary

The repository contains a functional **CV coaching chatbot**, not the AI Job Application Agent described in the new spec. The gap between documentation and implementation is large. What exists is ~15% of what is documented, but that 15% is fully functional and worth preserving as the basis for 2.0.

The new spec requires a fundamental shift:
- **From**: `CVSession` (upload CV → chat to improve it → download PDF)  
- **To**: `Candidate + Job + Application` (build profile → analyze jobs → generate applications → track outcomes → learn)

---

## 1. Repository Structure

```
linkedin-intelligence/
├── backend/         # FastAPI app — partially implemented
├── frontend/        # Next.js app — mostly implemented for current scope
├── docs/            # 21 docs — mostly aspirational, not synchronized with code
├── agents/          # 4 AI agent instruction files — no executable code
├── tasks/           # 1 sprint file — uncompleted, describes a different feature
├── infra/           # postgres/init.sql — only installs extensions, no tables
├── docker-compose.yml
└── .github/         # issue templates + PR template — NO CI/CD workflows
```

---

## 2. Backend Audit

### 2.1 What is Implemented (Real Code)

#### Database Models (`app/db/models.py`)
Two models, created via `Base.metadata.create_all` at startup (no Alembic):

| Model | Table | Key Fields |
|-------|-------|-----------|
| `CVSession` | `cv_sessions` | `id` (UUID), `original_filename`, `original_text`, `cv_data` (JSONB), timestamps |
| `ChatMessage` | `chat_messages` | `id`, `session_id` (FK), `role`, `content`, `created_at` |

No user ownership, no auth scope, no pgvector usage despite the image supporting it.

#### API Endpoints

| Method | Path | Status |
|--------|------|--------|
| `GET` | `/health` | Implemented |
| `POST` | `/api/v1/cv/upload` | Implemented — PDF → extract text → Claude Haiku → structured JSON → DB |
| `POST` | `/api/v1/cv/from-text` | Implemented — raw text → same pipeline |
| `GET` | `/api/v1/cv/{id}` | Implemented |
| `GET` | `/api/v1/cv/{id}/pdf` | Implemented — generates ReportLab PDF |
| `GET` | `/api/v1/cv/{id}/messages` | Implemented |
| `POST` | `/api/v1/cv/{id}/chat` | Implemented — SSE streaming, Claude Sonnet, XML tag protocol |

#### Services

| Service | File | Status |
|---------|------|--------|
| CV parsing | `ai_service.py` | Working. Uses `claude-haiku-4-5-20251001`. Returns JSON. |
| CV coaching chat | `ai_service.py` | Working. Uses `claude-sonnet-5`. SSE streaming. XML `<cv_update>` tags. |
| PDF extraction | `pdf_extractor.py` | Working. Uses PyMuPDF (`fitz`). |
| PDF generation | `pdf_generator.py` | Working. ~384 lines. ReportLab styled PDF. |

#### Dependencies Installed
`fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `pymupdf`, `reportlab`, `anthropic`, `python-multipart`, `aiofiles`, `pydantic-settings`, `python-dotenv`, `httpx`, `pillow`

### 2.2 What is Missing (Documented Only)

| Category | Items Missing |
|----------|--------------|
| **Database** | Alembic migrations, 7 documented tables (`job_postings`, `skills_catalog`, `skill_demand`, `profile_analyses`, `cv_analyses`, `users`, `trend_alerts`) |
| **Dependencies** | `alembic`, `celery`, `redis`, `langchain`, `langgraph`, `pgvector` Python client, `structlog`, `slowapi`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `openai`, `passlib`, `python-jose` |
| **API Routes** | Auth (`/auth/*`), Market (`/market/*`), Optimize (`/optimize/*`), Generate (`/generate/*`), Radar (`/radar/*`) — ~14 endpoints documented, 0 implemented |
| **Services** | ATS Engine, LinkedIn analyzer, job crawlers, ETL pipeline, RAG retriever, embeddings |
| **Celery** | `app/worker.py` doesn't exist — docker-compose `worker` and `beat` services will crash on start |
| **Tests** | Zero test files, no `tests/` directory |
| **CI/CD** | No GitHub Actions workflows |
| **Auth** | No authentication or user isolation anywhere |

### 2.3 Critical Bugs / Issues

1. **Worker crash**: `docker compose up` will fail for `worker`, `beat`, `flower` services because `app.worker` module doesn't exist and Celery isn't installed.
2. **No auth**: Any user can access any session by UUID. `GET /api/v1/cv/{any_uuid}` returns any user's CV.
3. **No migrations**: Schema is created at startup with `create_all`. Adding columns requires dropping tables.
4. **XML tag parsing**: The `<cv_update>` streaming protocol is brittle. Anthropic structured output / tool use is the correct approach.
5. **No rate limiting**: The API has no protection against abuse.
6. **JSONB mutation**: `cv_data` is mutated in place on every chat turn. No versioning, no history, no rollback.
7. **Prompt leaks raw CV JSON** to Claude context without sanitization.

---

## 3. Frontend Audit

### 3.1 What is Implemented

| Page/Component | Status |
|---------------|--------|
| `/` Landing | Implemented. 3 feature cards. |
| `/cv` CV Analyzer | Fully implemented — upload, chat, preview, PDF download. |
| `/profile` | Alias for `/cv` (just re-exports the same page). |
| `/skills` | Stub — "coming soon" banner + hardcoded blurred mock data. |
| `/market` | Stub — "coming soon" banner + hardcoded blurred mock stats. |
| `CVUpload.tsx` | Implemented. PDF drag-drop + text paste mode. |
| `ChatInterface.tsx` | Implemented. SSE consumer, react-markdown, 6 hardcoded suggestion chips. |
| `CVPreview.tsx` | Implemented. Live inline CV render + highlighted changed sections. |
| `Navbar.tsx` | Implemented. Active link detection. |
| `lib/api.ts` | Implemented. Typed API client matching current endpoints. |

### 3.2 What is Missing

- Auth UI (login, registration)
- Dashboard (job matches, applications, recommendations)
- Job analysis workspace
- Application workspace
- `shadcn/ui`, `zustand`, `react-query`, `recharts` (not installed)

---

## 4. Documentation Audit

| Doc | Accuracy vs Code |
|-----|-----------------|
| `06-DATABASE.md` | Describes 7 tables that don't exist. `cv_sessions` and `chat_messages` not mentioned. |
| `07-API_SPEC.md` | Describes ~20 endpoints. Only 7 exist and they don't match the spec. |
| `02-ROADMAP.md` | All items unchecked. Sprint 001 describes features different from what was built. |
| `03-ARCHITECTURE.md` | Describes LangChain/LangGraph/Celery/pgvector stack. None of this is implemented. |
| `12-AI_AGENTS.md` | Describes LangGraph agents. None implemented. App uses Anthropic SDK directly. |
| `19-DECISIONS.md` | 6 ADRs. ADR-005 (Claude primary + GPT-4o fallback) partially correct but no LangChain. |
| `17-CODING_STANDARDS.md` | Describes structlog — not installed. References Celery patterns — no worker exists. |

**Verdict**: Documentation describes a market intelligence platform. Code implements a CV coaching chatbot. They were never synchronized.

---

## 5. Infrastructure Audit

| Component | Status |
|-----------|--------|
| PostgreSQL 16 + pgvector | docker-compose works; extensions installed |
| Redis | docker-compose works |
| API service | Works when run with `uvicorn` directly; docker-compose volume mount OK |
| Frontend | Next.js builds and runs |
| Worker / Beat / Flower | **BROKEN** — `app.worker` module doesn't exist |
| GitHub Actions | **NONE** |
| Alembic | **NONE** |

---

## 6. What to Keep

| Asset | Reason |
|-------|--------|
| `pdf_extractor.py` | Good async PyMuPDF implementation. Reuse as `CandidateSource` CV parser. |
| `pdf_generator.py` | Functional PDF generation. Adapt for `CVVersion` export. |
| `ai_service.py` stream pattern | SSE streaming infrastructure is correct. Refactor to use structured outputs. |
| `ChatInterface.tsx` | Reuse as Application Copilot chat. |
| `CVUpload.tsx` | Adapt for candidate onboarding source upload. |
| `CVPreview.tsx` | Adapt for CVVersion viewer. |
| `docker-compose.yml` | Good base. Remove broken worker/beat/flower until Celery is actually implemented. |
| `infra/postgres/init.sql` | Extensions setup is correct. |

## 7. What to Change

| Asset | Action |
|-------|--------|
| `app/db/models.py` | Add new 2.0 models. Keep `CVSession` temporarily as migration source. |
| `app/db/session.py` | Replace `create_all` with Alembic lifecycle. |
| `app/services/ai_service.py` | Migrate from XML tag protocol to Anthropic tool_use / structured output. |
| `app/core/config.py` | Add `SECRET_KEY`, `REDIS_URL`, `OPENAI_API_KEY`. |
| `app/api/routes/cv.py` | Scope all queries to authenticated user. |
| `frontend/src/app/cv/page.tsx` | Repurpose as candidate onboarding flow. |
| `tasks/sprint-001.md` | Archive. Replace with 2.0 sprint plan. |

## 8. What to Discard

| Asset | Reason |
|-------|--------|
| Sprint 001 as written | Describes a different product. Archive it. |
| `docs/` as source of truth | 21 docs describe a different product. Update progressively with 2.0 docs. |
| `app/db/models.py` `CVSession` | Replace with `Candidate` + `CandidateSource` after migration. |

---

## 9. Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| No auth = data leakage | HIGH | Add auth in Phase 1 before any production use |
| No migrations = schema fragility | HIGH | Add Alembic immediately |
| No tests = regression blindness | HIGH | Add test infrastructure in Phase 1, mandate tests for all new code |
| LLM hallucination in CV generation | HIGH | Implement Evidence model and ClaimValidator in Phase 4 |
| Celery/worker architecture complexity | MEDIUM | Start with in-process background tasks, add Celery when scale demands it |
| `<cv_update>` XML protocol | MEDIUM | Migrate to structured output in Phase 1 |
| Cost blowout | MEDIUM | Implement token accounting in AI layer from day 1 |
