# Product Completion Gap Analysis

**Date:** 2026-08-14  
**Branch:** claude/new-session-ce0sct  
**Purpose:** Audit actual implementation state against the 22-capability Definition of Done before beginning product-grade evolution.

---

## 1. Definition of Done — Status Summary

| # | Capability | Status | Notes |
|---|-----------|--------|-------|
| 1 | Find suitable job | PARTIAL | `job_recommender.py` exists; no job source connectors wired |
| 2 | Understand JD | MISSING | No deep JD analysis service; `Job.tech_stack / requirements` never populated by parser |
| 3 | Explain Job Fit | MISSING | No "why should you apply" explainer wired to user-facing API |
| 4 | Explain Career Fit | PARTIAL | `compute_career_fit()` exists in `matching/engine.py`; never surfaced to user |
| 5 | Decide whether to apply | PARTIAL | `decide_application()` + `check_hard_constraints()` exist; not called in any user flow |
| 6 | Create Application Strategy | NOT_CONNECTED | `application_agent.generate_strategy()` fully implemented; orchestrator never calls it |
| 7 | Create personalized CV | NOT_CONNECTED | `cv_agent.personalize_cv()` fully implemented; `cv_storage.py` generates `.txt` placeholder |
| 8 | Create personalized Cover Letter | NOT_CONNECTED | `communication_agent.generate_cover_letter()` fully implemented; never called |
| 9 | Resolve application questions | NOT_CONNECTED | `communication_agent.generate_application_answers()` fully implemented; never called |
| 10 | Open real form | IMPLEMENTED | `PlaywrightAdapter.open_url()` + headless Chromium |
| 11 | Detect all fields | PARTIAL | `form_extractor.js` works for generic forms; ATS-specific adapters are stubs |
| 12 | Auto-resolve known fields | PARTIAL | `CandidateKnowledgeResolver` works; `FROM_KB` source declared but never implemented |
| 13 | Show only fields requiring confirmation | PARTIAL | `awaiting_human` status exists; no frontend to show human-required fields |
| 14 | Complete the form | IMPLEMENTED | fill_text, select_option, check_checkbox, upload_file all work |
| 15 | Attach documents | PARTIAL | File upload works; attached file is a `.txt` placeholder, not real PDF CV |
| 16 | Validate before submit | MISSING | No pre-submit validation pass; browser HTML5 validation is the only guard |
| 17 | Wait for human confirmation | IMPLEMENTED | `human_confirmed=True` required; raises `AgentError` without it |
| 18 | Submit | IMPLEMENTED | `click_submit()` + fallback wait |
| 19 | Detect confirmation | IMPLEMENTED | `CONFIRMATION_DETECTOR_JS` with false-positive guard |
| 20 | Register application | IMPLEMENTED | `ApplicationSubmission` record + `Application.status = "applied"` |
| 21 | Track outcome | PARTIAL | Models exist (`Application.outcome`, `ApplicationEvent`); no feedback endpoint |
| 22 | Learn from outcome | PARTIAL | `learning_loop.compute_calibration()` fully implemented; never called; no wiring |

---

## 2. Component-Level Classification

### IMPLEMENTED (working, tested)

| Component | File | What it does |
|-----------|------|-------------|
| Orchestrator 3-phase | `application_agent_orchestrator.py` | start / resume / submit |
| Field resolver | `candidate_knowledge_resolver.py` | 21 typed resolvers, DIRECT/COMPUTED/GENERATED/HUMAN_REQUIRED |
| Semantic classifier | `form_intelligence.py` | regex-based field type classifier |
| Browser adapter | `playwright_adapter.py` | fill, select, check, upload, screenshot, submit |
| Form extractor | `browser/form_extractor.py` | JS extractor + CONFIRMATION_DETECTOR_JS |
| Deterministic matching | `matching/engine.py` | skill overlap, experience, location, education, salary, career fit, hard constraints, decision |
| Match agent | `agents/match_agent.py` | LLM qualitative scoring + recommendation |
| Strategy agent | `agents/application_agent.py` | ApplicationStrategy with CV guidance + cover letter key points |
| CV agent | `agents/cv_agent.py` | PersonalizedCV with CVChange audit trail (original/adapted/rationale/evidence) |
| Cover letter agent | `agents/communication_agent.py` | CoverLetterResult + ApplicationAnswers |
| Claim validator | `claim_validator.py` | SUPPORTED/PLAUSIBLE/UNSUPPORTED without LLM |
| Learning loop | `learning_loop.py` | CalibrationReport from outcome data |
| PDF generator | `pdf_generator.py` | Full A4 PDF with ReportLab (header, summary, experience, skills, education, projects, certifications) |
| DB models | `db/models/*.py` | 13 migrations; CVVersion, CoverLetter, ApplicationAnswer, ApplicationEvent, EvidenceRecord all defined |
| API agent routes | `api/routes/agent.py` | start, resume, submit, answer_field, get_session |
| Test suite | `tests/` | 252 passing, including Golden E2E with real Playwright + mock ATS |

### PARTIAL (exists, incomplete logic)

| Component | File | Gap |
|-----------|------|-----|
| CV storage | `cv_storage.py` | Generates `.txt` placeholder; `pdf_generator.py` exists but is never called |
| CandidateKnowledgeResolver | `candidate_knowledge_resolver.py` | `FROM_KB` source declared in docstring but never implemented in any resolver; falls back to HUMAN_REQUIRED for knowledge base fields |
| Agent session transitions | `db/models/agent_session.py` | `transition_to("discovering")` is a `pass` — no timestamp written |
| Greenhouse adapter | `ats/greenhouse.py` | Tries GDPR banner dismissal; `submit()` is generic (no multi-page logic) |
| Job Intelligence | `db/models/job.py` | `tech_stack`, `requirements`, `seniority`, `salary_*` fields exist; no service populates them from raw JD text |
| Answer field route | `api/routes/agent.py:47` | Path param `field_id` declared but lookup uses `payload.field_id` from body — one works, the other is dead |

### STUB (skeleton only, no behavior)

| Component | File | State |
|-----------|------|-------|
| Lever adapter | `ats/lever.py` | All methods `pass` or delegate to generic |
| Ashby adapter | `ats/ashby.py` | All methods `pass` |
| Workday adapter | `ats/workday.py` | All methods `pass` |
| SmartRecruiters adapter | `ats/smart_recruiters.py` | All methods `pass` |
| Multi-step form nav | (any adapter) | No concept of paginated forms; all forms assumed single-page |
| iframe handling | (any adapter) | No iframe switching logic anywhere |
| Session auth / cookies | (any adapter) | No cookie jar management; each run starts fresh |

### NOT CONNECTED (fully implemented, zero wiring)

| Component | Implemented in | Connected to | Should connect to |
|-----------|---------------|-------------|------------------|
| ApplicationStrategy | `agents/application_agent.py` | Nothing | Orchestrator pre-start |
| PersonalizedCV | `agents/cv_agent.py` | Nothing | CVVersion model + cv_storage + orchestrator |
| CoverLetter generation | `agents/communication_agent.py` | Nothing | CoverLetter model + orchestrator |
| Application answers | `agents/communication_agent.py` | Nothing | ApplicationAnswer model + resolver FROM_KB |
| Matching engine | `matching/engine.py` | Nothing | Orchestrator pre-start / job radar |
| LLM match reasoning | `agents/match_agent.py` | Nothing | Orchestrator pre-start |
| ClaimValidator | `claim_validator.py` | Nothing | cv_agent output + communication_agent output |
| LearningLoop | `learning_loop.py` | Nothing | Application outcome feedback endpoint |
| PDF generator | `pdf_generator.py` | Nothing | `cv_storage.generate_cv_file()` |
| CVVersion fields | `db/models/application.py` | Nothing | `cv_agent.PersonalizedCV` result |
| CoverLetter model | `db/models/application.py` | Nothing | `communication_agent.CoverLetterResult` |
| ApplicationAnswer model | `db/models/application.py` | Human answers only | `communication_agent.AnswerResult` |
| Application.strategy | `db/models/application.py` | Nothing | `application_agent.ApplicationStrategy` |
| EvidenceRecord graded | `db/models/evidence.py` | Ungraded | `claim_validator.validate_claims()` |

### MISSING (not in codebase at all)

| Gap | Required for DoD | Priority |
|----|-----------------|---------|
| Job Intelligence service | DoD 2 — Understand JD | P0 |
| Job Fit / Career Fit explainer API | DoD 3, 4 | P1 |
| Application Decision API endpoint | DoD 5 | P1 |
| FROM_KB in resolver | DoD 12 — better auto-resolve | P0 |
| Pre-submit form validation | DoD 16 | P1 |
| Submission screenshot saved to disk | DoD 19+ | P1 |
| Outcome feedback endpoint | DoD 21 | P1 |
| Frontend (Next.js) | DoD 13, 21 | P2 |
| Multi-step form navigation | DoD 10, 14 (Greenhouse, Lever) | P1 |
| Greenhouse multi-page logic | DoD 14 | P1 |
| Lever iframe handling | DoD 14 | P2 |
| Workday session auth | DoD 14 | P2 |

---

## 3. The Biggest Architectural Gap

**The orchestrator `start()` phase skips all intelligence.**

Today's flow:
```
start() → open browser → extract form → classify fields → resolve values → save → done
```

The intended flow:
```
start() → analyze JD → compute match → generate strategy → personalize CV → 
          generate cover letter → generate answers → open browser → extract form →
          classify fields → resolve values (FROM_KB) → save → done
```

**Every AI agent is fully implemented and disconnected from the orchestrator.** The single highest-value change is wiring `application_agent → cv_agent → communication_agent → resolver FROM_KB` into `orchestrator.start()`.

---

## 4. Exact Files That Must Change

### P0 — Maximum impact, minimum new code (wire existing agents)

| File | Change |
|------|--------|
| `app/services/application_agent_orchestrator.py` | Add pre-start intelligence phase: match scoring → strategy → CV personalization → cover letter → answers |
| `app/services/candidate_knowledge_resolver.py` | Implement FROM_KB: use ApplicationAnswer + CoverLetter + Application.strategy as knowledge base |
| `app/services/cv_storage.py` | Connect to `pdf_generator.generate_cv_pdf()`; populate from PersonalizedCV result |
| `app/db/models/application.py` | Add helper to persist PersonalizedCV → CVVersion, CoverLetterResult → CoverLetter |
| `app/db/models/agent_session.py` | Fix `transition_to("discovering")` to write `discovered_at` timestamp |

### P0 — Job Intelligence (new service, small)

| File | Change |
|------|--------|
| `app/services/job_intelligence.py` | NEW: parse raw JD text → extract tech_stack, requirements, seniority, salary_range, benefits |
| `app/services/agents/job_agent.py` | EXISTS: check content; wire to job_intelligence if it's a stub |
| `app/db/models/job.py` | Populate `tech_stack`, `requirements`, `seniority` from parsed JD |

### P1 — API completions

| File | Change |
|------|--------|
| `app/api/routes/agent.py` | Fix `field_id` path/body mismatch; add `/explain-fit` endpoint; add `/outcome` endpoint |
| `app/schemas/agent.py` | Add `JobFitResponse`, `OutcomeFeedbackRequest` schemas |
| `app/api/routes/candidates.py` | Verify CRUD routes for CandidateProfile (needed by intelligence phase) |

### P1 — ATS adapters (Greenhouse priority)

| File | Change |
|------|--------|
| `app/services/ats/greenhouse.py` | Implement multi-page navigation: detect next-page button, loop until submit page |
| `app/services/ats/lever.py` | Implement iframe detection and switching |
| `app/services/browser/playwright_adapter.py` | Add `switch_to_iframe(selector)` method |

### P1 — Pre-submit validation

| File | Change |
|------|--------|
| `app/services/application_agent_orchestrator.py` | Add validation phase before `click_submit()`: check required fields are filled, types match |

### P1 — Outcome tracking

| File | Change |
|------|--------|
| `app/api/routes/applications.py` | Add `/applications/{id}/outcome` feedback endpoint |
| `app/services/learning_loop.py` | Wire `compute_calibration()` to be called on demand and surfaced to user |

### P2 — Frontend

| Location | Change |
|---------|--------|
| `frontend/` | Next.js app: candidate dashboard, pending fields panel, application history |

---

## 5. Risks

### High

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM calls in `start()` add 5–15 seconds of latency | Poor UX if user expects instant start | Run strategy+CV+cover letter in parallel with `asyncio.gather()`; add progress events |
| Anthropic API key required for all intelligence phases | Tests fail without real API key | Guard with `try/except`; fall back gracefully; mock in tests |
| `cv_agent` output is not validated against actual candidate data | Risk of hallucination despite system prompt | `ClaimValidator` exists but is not connected; wire it to validate PersonalizedCV before persisting |
| ATS DOM changes break field extraction | Adapters silently fail | `form_extractor.js` is the single point of failure; add field count sanity check |

### Medium

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Multi-step forms (Greenhouse, Lever) need navigation state | Single-pass browser run fails on page 2+ | Adapter loop pattern: detect "next" button, advance, extract new fields |
| `FROM_KB` requires candidate to have written knowledge base entries | Falls back to HUMAN_REQUIRED if no KB | Acceptable degradation; document that KB improves coverage |
| SQLite in tests vs PostgreSQL in prod | Type mismatches on JSONB columns | Already using aiosqlite in tests; watch for JSON column compatibility |

### Low

| Risk | Impact | Mitigation |
|------|--------|-----------|
| PDF generation adds `reportlab` dependency | Build size increase | Already installed (`pdf_generator.py` imports it) |
| `CONFIRMATION_DETECTOR_JS` misses ATS-specific confirmation patterns | False negative on "submitted" | Each adapter can override `extract_confirmation_id_pattern()` — hook already exists |

---

## 6. Acceptance Criteria for P0

### Job Intelligence
- [ ] `analyze_jd(raw_jd_text)` returns structured `{tech_stack: [], requirements: [], seniority: str, salary_range: {min, max}}`
- [ ] `Job` model fields populated after ingestion

### Strategy + CV + Cover Letter in Orchestrator
- [ ] `orchestrator.start()` calls `generate_strategy()`, `personalize_cv()`, `generate_cover_letter()` before browser phase
- [ ] `Application.strategy` JSON column populated with `ApplicationStrategy` result
- [ ] `CVVersion` row created with `summary_adapted`, `skills_ordered`, `changes`, `ats_keywords`, `evidence_refs`
- [ ] `CoverLetter` row created with generated content
- [ ] ClaimValidator called on CV changes; `unverified_claims` count logged
- [ ] If LLM call fails, orchestrator continues (graceful degradation, not error)

### PDF CV
- [ ] `cv_storage.generate_cv_file()` returns a `.pdf` file
- [ ] PDF contains personalized summary (adapted content from cv_agent)
- [ ] PDF contains ordered skills (from PersonalizedCV.skills_ordered)

### FROM_KB in Resolver
- [ ] `CandidateKnowledgeResolver._resolve_custom_essay()` checks `ApplicationAnswer` table before generating
- [ ] Cover letter content available for resolver if communication_agent ran first

### Answer Engine
- [ ] HUMAN_REQUIRED essay fields auto-attempted via `communication_agent.generate_application_answers()`
- [ ] Generated answers stored as `ApplicationAnswer` rows with `evidence_refs`
- [ ] Human can override before submit

### Tests
- [ ] All 252 existing tests still pass
- [ ] New test: `test_start_populates_strategy_and_cv()` — verify Intelligence phase populates DB
- [ ] New test: `test_pdf_cv_generated()` — verify `.pdf` extension and non-zero file size
