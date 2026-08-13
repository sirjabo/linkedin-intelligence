# LinkedIn Intelligence 2.0 — Migration Plan

**Date**: 2026-08-13  
**From**: v1 CV coaching chatbot  
**To**: AI Job Application Agent  

---

## Migration Principles

1. **No data destruction.** Existing `cv_sessions` and `chat_messages` are migrated, not deleted.
2. **Alembic from day one.** All schema changes from this point happen via versioned migrations.
3. **Additive first.** Add new tables and columns before removing old ones.
4. **Feature parity checkpoint.** Before removing v1 code, confirm the 2.0 equivalent works end-to-end.
5. **No big bang.** Each phase delivers working, tested functionality.

---

## What Gets Migrated

### Data Migration

| v1 Entity | v2.0 Equivalent | Migration Strategy |
|-----------|----------------|-------------------|
| `CVSession` | `CandidateSource` (type: `cv`) | Alembic data migration: create `candidate_sources` row from each `cv_session` |
| `CVSession.cv_data` | `CVVersion.content` (master, no job) | Migrate JSONB content to `cv_versions` |
| `CVSession.original_text` | `CandidateSource.raw_content` | Direct copy |
| `ChatMessage` | Archive in `application_events` or keep as-is | Keep `chat_messages` table; add nullable `application_id` FK |

Because there is no auth in v1, migrated sessions will be associated with a **system seed user** for development. Production launch starts fresh.

### Code Migration

| v1 Code | v2.0 Destination | Action |
|---------|-----------------|--------|
| `pdf_extractor.py` | `services/pdf_extractor.py` | Keep as-is, reuse |
| `pdf_generator.py` | `services/pdf_generator.py` | Adapt for `CVVersion.content` schema |
| `ai_service.parse_cv_text` | `agents/profile_agent.py` | Migrate to structured output; expand schema |
| `ai_service.stream_cv_chat` | `agents/cv_agent.py` + route handler | Migrate from XML tags to tool_use events |
| `CVUpload.tsx` | `/onboarding/cv` step | Reuse component, update API call target |
| `ChatInterface.tsx` | `ApplicationCopilot.tsx` | Reuse SSE infrastructure, update event schema |
| `CVPreview.tsx` | `CVVersionPreview.tsx` | Reuse renderer, adapt to `CVVersion` schema |

---

## Migration Sequence

### Step 1: Alembic Setup (Phase 1, Week 1)

```bash
cd backend
pip install alembic
alembic init alembic
# Configure env.py for async SQLAlchemy
alembic revision --autogenerate -m "001_initial_cv_sessions"
# This captures the existing schema as migration 001
alembic upgrade head
```

Remove `init_db()` call that does `create_all`. Replace with Alembic at deploy time.

### Step 2: User + Candidate Tables (Phase 1, Week 1)

```
alembic revision -m "002_add_users_and_candidates"
```

- Add `users` table
- Add `candidates` table with `user_id FK`
- Add `candidate_sources` table
- Add `candidate_profiles` table
- Add `evidence_records` table

### Step 3: Auth Middleware (Phase 1, Week 1)

- Add JWT auth endpoints: `POST /auth/register`, `POST /auth/login`
- Add `get_current_user` dependency in `api/deps.py`
- Scope all existing CV routes to authenticated user
- Add `user_id` column to `cv_sessions` (nullable for backward compat during migration)

### Step 4: Migrate cv_sessions → candidate_sources (Phase 1, Week 2)

```
alembic revision -m "003_migrate_cv_sessions_to_sources"
```

Data migration: for each `cv_session`, create a `candidate_source` record. The `CVSession` table is kept for 2 phases as a fallback, then removed.

### Step 5: New AI Layer (Phase 1, Week 2)

- Create `services/ai/provider.py` with `LLMProvider` protocol
- Create `AnthropicProvider` implementation
- Create `cost_tracker.py`
- Migrate `parse_cv_text` → `ProfileAgent.extract_from_cv_text` using structured output
- Migrate `stream_cv_chat` → structured SSE events (JSON, not XML tags)

### Step 6: Job + Match Tables (Phase 2)

```
alembic revision -m "004_add_jobs_and_matches"
```

- Add `jobs` table
- Add `job_requirements` table
- Add `match_analyses` table

### Step 7: Application Tables (Phase 4)

```
alembic revision -m "005_add_applications"
```

- Add `applications` table
- Add `cv_versions` table
- Add `cover_letters` table
- Add `application_answers` table
- Add `application_events` table

### Step 8: Remove Legacy Code (Phase 4, after end-to-end verification)

- Drop `CVSession` model and table (after all data migrated)
- Drop old chat routes (replaced by application copilot)
- Archive v1 docs
- Update frontend to remove `/cv` direct route

---

## Breaking Changes

The following changes are breaking and must be coordinated:

| Change | Impact | When |
|--------|--------|------|
| Auth required on all endpoints | All existing API calls fail without JWT | Phase 1 |
| `/api/v1/cv/upload` → `/api/v1/candidates/{id}/sources` | Frontend must update | Phase 1 |
| `/api/v1/cv/{id}/chat` → `/api/v1/applications/{id}/chat` | Frontend must update | Phase 4 |
| `CVData` schema → `CVVersion.content` schema | Frontend CV renderer must update | Phase 2 |
| SSE event schema: XML tags → JSON tool_use events | Frontend `ChatInterface.tsx` must update | Phase 1 |

---

## Rollback Plan

Each Alembic migration is reversible. If a phase fails:

```bash
alembic downgrade -1   # Roll back one migration
```

v1 code is kept on the `main` branch until Phase 4 passes end-to-end verification. The working branch `claude/new-session-ce0sct` contains 2.0 code.

---

## Dependency Changes

### Add to `requirements.txt`

```
# Core additions
alembic==1.13.2
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
slowapi==0.1.9
structlog==24.4.0
redis==5.2.0

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==5.0.0
respx==0.21.1  # HTTP mocking for tests

# Dev only
ruff==0.7.4
mypy==1.13.0
```

### Remove from `requirements.txt`

None yet. Dependencies are only removed when the code that uses them is removed.

---

## Acceptance Criteria for Migration Complete

Migration is complete when:

1. All Phase 1-4 tables exist and have Alembic migrations
2. `GET /health` checks DB + confirms Alembic head is applied
3. Auth works end-to-end (register → login → JWT on all protected routes)
4. The Golden User Journey (spec section 58) works end-to-end
5. `cv_sessions` table is empty or removed (all data migrated)
6. All API calls in `frontend/src/lib/api.ts` target 2.0 endpoints
7. Test coverage ≥ 70% on all new code
8. No `create_all` calls remain in the codebase
