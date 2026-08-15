# Roadmap 3.0 — AI Application Agent

**Date:** 2026-08-14  
**Horizon:** 6 months  
**Principle:** Wire existing code before writing new code. Every phase ships tests and does not break the prior test suite.

---

## Priority Model

| Tier | Definition |
|------|-----------|
| **P0** | Turns MVP-functional into product-real. Maximum DoD coverage per PR. Wires the disconnected AI agents. |
| **P1** | Fills the critical missing holes. Real ATS adapters, pre-submit validation, outcome tracking. |
| **P2** | Depth and reliability. Frontend, LLM fallback in form intelligence, multi-ATS coverage. |
| **P3** | Scale and market features. Job radar, profile optimization, multi-candidate support. |

---

## P0 — Wire the Intelligence Layer (2–3 weeks)

These phases require no new services — only connecting the implementations that already exist.

### Phase 1 — Intelligence Pipeline in Orchestrator

**What:** `orchestrator.start()` gains a pre-browser intelligence phase.

**Flow:**
```
orchestrator.start(application_id, form_url)
  ├── [NEW] load Job → call analyze_jd() if tech_stack is empty
  ├── [NEW] compute_deterministic() + reason_about_match()
  ├── [NEW] generate_strategy() → Application.strategy
  ├── [NEW] personalize_cv() → CVVersion row
  ├── [NEW] generate_cover_letter() → CoverLetter row
  ├── [NEW] generate_application_answers(essay_questions) → ApplicationAnswer rows
  ├── [NEW] validate_claims(cv_changes, evidence_records)
  ├── [EXISTING] open browser → extract form → classify fields
  └── [EXISTING] resolve values → save → return session
```

**Files changed:**
- `app/services/application_agent_orchestrator.py` — add `_run_intelligence_phase()`
- `app/db/models/application.py` — add `persist_cv_version()`, `persist_cover_letter()`
- `app/db/models/agent_session.py` — fix `transition_to("discovering")` timestamp

**Tests:**
- `test_start_populates_strategy_and_cv()` — with mocked LLM (provider pattern already supports injection)
- All 252 existing tests still pass

**DoD coverage:** 6, 7, 8, 9

---

### Phase 2 — FROM_KB in Resolver

**What:** `CandidateKnowledgeResolver` checks the candidate's existing `ApplicationAnswer` rows and `CoverLetter` content before falling back to HUMAN_REQUIRED.

**Changes:**
- `candidate_knowledge_resolver.py` — implement `_resolve_from_kb(field_label, application)`: query `ApplicationAnswer` where question is similar to the field label; return best match
- Resolver gains a 5th source: `FROM_KB` (was declared but never implemented)

**Impact:** Reduces HUMAN_REQUIRED fields significantly for candidates who have applied before; cover letter auto-fills "Tell us about yourself" fields.

**DoD coverage:** 12

---

### Phase 3 — Real PDF CV

**What:** `cv_storage.generate_cv_file()` produces a `.pdf` containing the personalized CV content.

**Changes:**
- `app/services/cv_storage.py` — call `pdf_generator.generate_cv_pdf(cv_dict)` where `cv_dict` is built from `CVVersion` + `CandidateProfile`
- `cv_storage._render_cv()` → `cv_storage._build_cv_dict(candidate, profile, cv_version)` → feeds `pdf_generator`

**Tests:**
- `test_pdf_cv_generated()` — assert file ends in `.pdf`, `os.path.getsize() > 0`
- `test_pdf_cv_is_personalized()` — assert adapted summary appears in generated dict

**DoD coverage:** 7, 15

---

## P1 — Fill Critical Holes (3–5 weeks)

### Phase 4 — Job Intelligence Service

**What:** Parse raw JD text into structured data the matching engine and AI agents can use.

**New file:** `app/services/job_intelligence.py`

```python
async def analyze_jd(raw_jd: str, job_title: str | None) -> JobIntelligenceResult:
    # LLM extraction: tech_stack, requirements, seniority, salary_range, benefits, location, remote_type
```

**Wiring:**
- Called during job ingestion (job creation endpoint or background task)
- Result populates `Job.tech_stack`, `Job.requirements`, `Job.seniority`
- Matching engine already reads these fields — no matching engine changes needed

**DoD coverage:** 2

---

### Phase 5 — Job Fit & Career Fit Explainer API

**What:** REST endpoints that explain fit in plain language.

**New endpoints:**
```
GET /api/v1/applications/{id}/fit-analysis
  → { job_fit_score, career_fit_score, tier, strengths[], gaps[], recommendation, llm_reasoning }

GET /api/v1/applications/{id}/decision
  → { decision: APPLY|STRETCH|DO_NOT_APPLY|BLOCKED, blockers[], overall_approach }
```

**Changes:**
- `app/api/routes/applications.py` — add fit-analysis and decision endpoints
- `app/schemas/applications.py` — add response schemas

**DoD coverage:** 3, 4, 5

---

### Phase 6 — Pre-Submit Validation

**What:** Before `click_submit()`, validate that filled values pass expected constraints.

**Logic in orchestrator:**
1. Re-extract form state from browser after filling
2. Compare filled values against expected values from DB
3. Check for visible validation errors (JS: `document.querySelectorAll(':invalid')`)
4. If validation fails: mark `session.status = "validation_failed"`, surface which fields failed

**DoD coverage:** 16

---

### Phase 7 — Submission Evidence

**What:** Capture a screenshot before and after submit; store paths.

**Changes:**
- `orchestrator.submit()` already captures screenshot but stores it in `session.screenshot_before_path = None` (explicit null)
- Fix: save screenshot bytes to `{STORAGE_PATH}/screenshots/{session_id}_before.png`; store path in DB
- Same for post-submit: `session.screenshot_after_path`
- Add `STORAGE_PATH` to config

**DoD coverage:** 19 (supporting evidence)

---

### Phase 8 — Outcome Feedback & Learning Loop

**What:** API endpoint for recording application outcomes; calibration report.

**New endpoint:**
```
POST /api/v1/applications/{id}/outcome
  body: { outcome: "got_interview" | "rejected" | "offer" | "ghosted" | "withdrew" }

GET /api/v1/candidates/{id}/calibration
  → CalibrationReport (from learning_loop.compute_calibration())
```

**Changes:**
- `app/api/routes/applications.py` — add outcome endpoint
- `app/api/routes/candidates.py` — add calibration endpoint
- Wire `learning_loop.compute_calibration()` to read `Application` outcomes grouped by `match_tier`

**DoD coverage:** 21, 22

---

### Phase 9 — Greenhouse Adapter (Real)

**What:** Multi-page form navigation for Greenhouse ATS.

**Greenhouse form pattern:**
1. Page 1: Personal info (name, email, phone, location)
2. Page 2: Resume upload + cover letter
3. Page 3: Custom questions
4. Page 4: EEO / diversity (optional)
5. Submit

**Logic:**
- `greenhouse.py.before_discover()`: dismiss GDPR/cookie banner (existing), wait for stable DOM
- `greenhouse.py.navigate_to_submit()`: detect "Next" button → click → wait for new page → repeat until Submit visible
- `discover_form()`: call after each page advance, merge field lists

**Files:**
- `app/services/ats/greenhouse.py` — implement multi-page loop
- `app/services/browser/playwright_adapter.py` — add `has_element(selector)` helper

**DoD coverage:** 10, 11, 14

---

## P2 — Depth & Reliability (4–6 weeks)

### Phase 10 — Form Intelligence 2.0 (LLM Fallback)

**What:** When `classify_field()` returns `"unknown"`, call LLM to classify the field.

**Trigger:** `sem_type == "unknown"` in orchestrator mapping loop.

**LLM call:** Single structured output call with field label, placeholder, options → semantic type + suggested value format.

**Files:**
- `app/services/form_intelligence.py` — add `classify_field_llm(label, options, provider) -> str`
- `orchestrator.py` — call LLM fallback when regex returns "unknown"

**DoD coverage:** 11

---

### Phase 11 — Lever Adapter

**What:** Lever uses iframes for the application form. Need iframe switching.

**Changes:**
- `app/services/browser/playwright_adapter.py` — add `switch_to_frame(selector)`, `switch_to_main_frame()`
- `app/services/ats/lever.py` — implement `before_discover()` to enter application iframe

**DoD coverage:** 14 (Lever)

---

### Phase 12 — Answer Engine Polish

**What:** When an essay field is detected during `start()` but the strategy/answers phase ran first, those answers are already in `ApplicationAnswer`. Wire them into the resolver.

**Also:** Human-facing endpoint to review and edit generated answers before submit.

**New endpoint:**
```
GET /api/v1/agent/sessions/{id}/answers
  → list of ApplicationAnswer rows with generated content

PATCH /api/v1/agent/sessions/{id}/answers/{field_id}
  body: { answer: "corrected answer" }
```

**DoD coverage:** 9, 13

---

### Phase 13 — Frontend MVP (Next.js)

**What:** Minimum viable UI for the human-in-the-loop flow.

**Views:**
1. **Application dashboard** — list of active applications with status
2. **Pending fields panel** — show HUMAN_REQUIRED fields with generated suggestions; candidate edits and approves
3. **Strategy view** — show ApplicationStrategy, JobFit, CareerFit before committing to apply
4. **Application history** — list of submitted applications with outcomes

**Tech:** Next.js + shadcn/ui (existing in repo). API integration with existing backend.

**DoD coverage:** 13, 5, 4, 3, 21

---

## P3 — Scale & Market (ongoing)

### Phase 14 — Job Radar

**What:** Background job that polls configured job sources, scores against candidate profile, surfaces matches above threshold.

**Status:** `job_recommender.py` and `JobRadarConfig` model exist; no job source connectors.

**Priority job sources (no auth required):**
1. LinkedIn Jobs search via HTTP API (requires auth token)
2. Indeed RSS feeds (public)
3. Company career pages (Greenhouse/Lever/Ashby — public job listings endpoints)

### Phase 15 — Workday Adapter

**What:** Workday requires session-based auth and handles forms via dynamic React state. Needs cookie jar + page wait strategy.

### Phase 16 — SmartRecruiters Adapter

**What:** Similar to Greenhouse but different pagination pattern.

### Phase 17 — pgvector-based Job Matching

**What:** Replace keyword-based skill matching with embedding similarity. `pgvector` is already installed; no new infrastructure needed.

### Phase 18 — Profile Optimizer

**What:** Given match history, suggest profile improvements: add skills, update summary.

---

## Delivery Timeline

```
Week 1-2    Phase 1 — Intelligence Pipeline in Orchestrator
Week 2      Phase 2 — FROM_KB in Resolver
Week 3      Phase 3 — Real PDF CV
Week 4-5    Phase 4 — Job Intelligence Service
Week 5      Phase 5 — Fit & Career API
Week 6      Phase 6 — Pre-Submit Validation
Week 6      Phase 7 — Submission Evidence
Week 7      Phase 8 — Outcome Feedback & Learning Loop
Week 8-9    Phase 9 — Greenhouse Adapter
Week 10     Phase 10 — Form Intelligence 2.0
Week 11     Phase 11 — Lever Adapter
Week 12     Phase 12 — Answer Engine Polish
Week 13-16  Phase 13 — Frontend MVP
Week 17+    P3 phases
```

---

## DoD Coverage by Phase End

| Phase | New DoD Items Covered | Cumulative |
|-------|--------------------|-----------|
| After P0 (Phases 1-3) | 6, 7, 8, 9, 12, 15 | 10/22 = 45% |
| After P1 (Phases 4-9) | 2, 3, 4, 5, 10, 11, 14, 16, 19, 21, 22 | 21/22 = 95% |
| After P2 (Phases 10-13) | 13 (UI), 9 (polish), full 11, 14 | 22/22 = 100% |

---

## What NOT to Build

- No scraping LinkedIn profiles or job listings without authorization
- No auto-submit without explicit `human_confirmed=True`
- No inventing skills, metrics, dates, or titles in any AI-generated content
- No re-implementing the orchestrator from scratch (start from what works)
- No new infrastructure before existing DB models are fully utilized
