# Architecture 3.0 — AI Application Agent

**Date:** 2026-08-14  
**Status:** Target architecture for product-grade agent  
**Constraint:** Evolves the existing codebase; no infrastructure replacement.

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User (Human)                                  │
└─────────┬──────────────────────────────────────────────┬───────────┘
          │ Intent: "Apply to this job"                  │ Confirmation: "Submit"
          ▼                                              ▼
┌─────────────────────┐                     ┌────────────────────────┐
│    Next.js Frontend  │◄───── REST API ────►│   FastAPI Backend       │
│  (Candidate Portal)  │                     │   (app/main.py)        │
└─────────────────────┘                     └────────────┬───────────┘
                                                         │
                        ┌────────────────────────────────┤
                        │                                │
               ┌────────▼─────────┐          ┌──────────▼──────────┐
               │  Intelligence    │          │  Form Automation     │
               │  Pipeline (AI)   │          │  Pipeline (Browser)  │
               └────────┬─────────┘          └──────────┬──────────┘
                        │                               │
          ┌─────────────┼────────────┐                 │
          │             │            │                 │
    ┌─────▼──┐   ┌──────▼──┐  ┌────▼────┐   ┌────────▼────────┐
    │ Match  │   │Strategy │  │  CV +   │   │  PlaywrightAdapter│
    │ Engine │   │ Agent   │  │  Cover  │   │  + ATS Adapters  │
    │(det+LLM│   │         │  │  Letter │   │  + FormExtractor │
    └─────┬──┘   └──────┬──┘  └────┬────┘   └────────┬────────┘
          │             │           │                  │
          └─────────────▼───────────┘                  │
                        │                              │
               ┌────────▼─────────┐                   │
               │  Candidate       │◄──────────────────┘
               │  Knowledge       │
               │  Resolver        │
               │  (FROM_KB enabled│
               └────────┬─────────┘
                        │
               ┌────────▼─────────┐
               │  PostgreSQL DB   │
               │  (pgvector)      │
               └──────────────────┘
```

---

## 2. Application Lifecycle (Target State)

```
Phase 0 — Job Discovery
  JobRadarConfig → poll job sources → Job rows → analyze_jd() → Job.requirements populated

Phase 1 — Pre-Flight Intelligence (NEW)
  Application created →
  ApplicationAgentOrchestrator.start():
    ├── _analyze_job()          # populate Job.tech_stack if missing
    ├── _compute_match()        # matching/engine.compute_deterministic() + match_agent.reason_about_match()
    ├── _generate_strategy()    # application_agent.generate_strategy() → Application.strategy
    ├── _personalize_cv()       # cv_agent.personalize_cv() → CVVersion row
    ├── _generate_cover_letter()# communication_agent.generate_cover_letter() → CoverLetter row
    ├── _generate_answers()     # communication_agent.generate_application_answers() → ApplicationAnswer rows
    └── _validate_claims()      # claim_validator.validate_claims() → log unverified

Phase 2 — Form Discovery (EXISTING)
    ├── detect_ats(form_url) → ATS adapter
    ├── ats_adapter.before_discover(browser) # ATS-specific pre-steps
    ├── browser.open_url(form_url)
    └── browser.discover_form() → RawForm{fields[], submit_button_selector}

Phase 3 — Field Mapping (EXISTING + FROM_KB)
    ├── For each raw field:
    │     ├── classify_field(label) → semantic_type
    │     │   └── if "unknown": classify_field_llm() [P2]
    │     ├── resolver.resolve(semantic_type, candidate, profile, application)
    │     │   └── FROM_KB: check ApplicationAnswer → CoverLetter → Application.strategy
    │     └── persist ApplicationFormField
    └── session.status = "awaiting_human" | "ready_to_fill"

Phase 4 — Human Review (EXISTING API)
    API: GET /agent/sessions/{id}/fields → HUMAN_REQUIRED fields with suggestions
    API: POST /agent/sessions/{id}/fields/{id}/answer → human provides/edits answer
    API: POST /agent/sessions/{id}/resume → transition to ready_to_fill

Phase 5 — Fill & Validate (EXISTING + NEW validation)
    ApplicationAgentOrchestrator.submit(human_confirmed=True):
    ├── browser.open_url(form_url)
    ├── discover_form() again (fresh state)
    ├── fill each field (text/select/checkbox/url/number/file guards)
    ├── _validate_form_state() [NEW]: check :invalid elements, required fields
    ├── screenshot_before → save to disk → session.screenshot_before_path
    ├── ats_adapter.submit(browser) → click_submit()
    └── screenshot_after → save → session.screenshot_after_path

Phase 6 — Confirmation & Registration (EXISTING)
    ├── browser.is_confirmation_page() + browser.extract_confirmation_id()
    ├── ApplicationSubmission row created
    ├── Application.status = "applied"
    └── session.status = "submitted" | "failed"

Phase 7 — Outcome Tracking (NEW in P1)
    API: POST /applications/{id}/outcome
    ├── Application.outcome = "got_interview" | "rejected" | "offer" | "ghosted"
    └── ApplicationEvent logged

Phase 8 — Learning (NEW in P1)
    API: GET /candidates/{id}/calibration
    └── learning_loop.compute_calibration(outcomes) → CalibrationReport
```

---

## 3. Intelligence Pipeline Detail

### 3.1 Matching Engine (deterministic + LLM hybrid)

```python
# Inputs: CandidateProfile + Job (with requirements populated)
det = compute_deterministic(profile_skills, career_level, ...)
hard = check_hard_constraints(career_level, salary_pref, ...)
llm = await reason_about_match(candidate_summary, job_title, ...)

# Hybrid score
hybrid_score = det.overall_score * 0.60 + llm.score * 0.40
tier = tier_from_score(hybrid_score)
decision = decide_application(hybrid_score, hard, det.missing_skills)
```

### 3.2 Strategy → CV → CoverLetter chain

```
ApplicationStrategy (application_agent)
  ├── cv_changes: list[CVChangeGuidance]     ──► PersonalizedCV (cv_agent)
  ├── cover_letter_key_points: list[str]     ──► CoverLetterResult (communication_agent)
  ├── strengths_to_emphasize: list[str]      ──► both agents
  └── risks_to_address: list[str]            ──► cover_letter context

PersonalizedCV
  ├── summary_adapted                         ──► CVVersion.summary_adapted
  ├── skills_ordered                          ──► CVVersion.skills_ordered
  ├── ats_keywords_added                      ──► CVVersion.ats_keywords
  ├── changes: list[CVChange]                 ──► CVVersion.changes (JSON)
  └── evidence_refs                           ──► CVVersion.evidence_refs

CoverLetterResult
  ├── content                                 ──► CoverLetter.content
  └── evidence_refs                           ──► CoverLetter.evidence_refs (for ClaimValidator)
```

### 3.3 Claim Validation

```python
# After cv_agent and communication_agent run:
cv_text = " ".join([c.adapted for c in personalized_cv.changes])
evidence = await db.execute(select(EvidenceRecord).where(...candidate...))
validation = validate_claims(cv_text, evidence.scalars().all())

# Log unverified claims; do NOT block the pipeline
if validation.unverified_claims:
    logger.warning("cv.unverified_claims", count=len(validation.unverified_claims))
```

---

## 4. Candidate Knowledge Resolver — FROM_KB Implementation

```
CandidateKnowledgeResolver.resolve(semantic_type="custom_essay", field_label, application)

Resolution order:
1. DIRECT     — CandidateProfile field maps 1:1 (name, email, phone, linkedin_url)
2. COMPUTED   — derived from profile (years_experience from work history)
3. FROM_KB    — [NEW] search ApplicationAnswer where question ≈ field_label (substring/embedding)
              → if found: return answer + source=FROM_KB
              → also check CoverLetter.content if label matches "cover letter" / "motivation"
4. GENERATED  — call LLM (communication_agent or _resolve_custom_essay)
5. HUMAN_REQUIRED — if all above fail or confidence < threshold
```

**FROM_KB lookup strategy (deterministic, no LLM):**
```python
def _resolve_from_kb(field_label: str, application: Application) -> str | None:
    label_lower = field_label.lower()
    for answer in application.answers:
        q_lower = answer.question.lower()
        # Direct substring match
        if label_lower in q_lower or q_lower in label_lower:
            return answer.answer
    # Cover letter match for motivation/interest fields
    cover_letter_triggers = {"motivation", "interest", "why", "about yourself", "cover"}
    if any(t in label_lower for t in cover_letter_triggers):
        cover = application.cover_letters[0] if application.cover_letters else None
        if cover and cover.content:
            return cover.content[:500]  # truncate for short-form fields
    return None
```

---

## 5. ATS Adapter Architecture

### Current state (all stubs except Generic)

```python
class ATSAdapter(Protocol):
    ats_name: str
    url_patterns: list[re.Pattern]

    async def before_discover(self, browser) -> None: ...
    def normalize_field(self, field: RawFormField) -> RawFormField: ...
    async def submit(self, browser) -> bool: ...
    def extract_confirmation_id_pattern(self) -> re.Pattern | None: ...
```

### Target: multi-page adapter loop

```python
# In PlaywrightAdapter
async def navigate_multi_page_form(
    self,
    ats_adapter: ATSAdapter,
    max_pages: int = 10,
) -> list[RawFormField]:
    """Navigate a paginated form, collecting all fields across pages."""
    all_fields = []
    for _ in range(max_pages):
        page_form = await self.discover_form()
        all_fields.extend(page_form.fields)
        
        next_selector = await ats_adapter.get_next_page_selector(self)
        if not next_selector:
            break  # reached final page
        await self.click(next_selector)
        await self._page.wait_for_load_state("networkidle")
    
    return all_fields
```

### Greenhouse implementation plan

```
Page detection:
- "Next" button: button:has-text("Next"), input[type="submit"][value="Next"]
- Progress indicator: .application-progress, [aria-label*="step"]

Field normalization:
- Greenhouse adds "greenhouse-" prefix to field names → strip in normalize_field()
- Cover letter textarea: #cover_letter, [data-label="Cover Letter"]
- Custom questions: .custom-question, [data-field-type="custom"]

GDPR dismissal (already partially implemented):
- [data-gdpr-consent-accept], .gdpr-consent-accept, button:has-text("Accept All")
```

---

## 6. Browser Automation — New Methods Required (P1)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `has_element` | `(selector: str) -> bool` | Detect next-page button, GDPR banner |
| `switch_to_frame` | `(selector: str) -> None` | Lever iframe entry |
| `switch_to_main_frame` | `() -> None` | Exit iframe |
| `get_validation_errors` | `() -> list[str]` | Pre-submit validation check |
| `wait_for_element` | `(selector: str, timeout: float) -> None` | Stable DOM wait |
| `save_screenshot` | `(path: str) -> str` | Save screenshot to disk, return path |

---

## 7. Data Model — Target State

### Application (already defined, needs population)

```
Application
  ├── strategy: JSON          ← ApplicationStrategy from application_agent [NOT CONNECTED]
  ├── cv_versions: list       ← CVVersion from cv_agent [NOT CONNECTED]
  │     ├── summary_adapted
  │     ├── headline_adapted
  │     ├── skills_ordered: JSON list
  │     ├── changes: JSON list[CVChange]
  │     ├── ats_keywords: JSON list
  │     ├── evidence_refs: JSON list
  │     └── validation_result: JSON (ClaimValidator output)
  ├── cover_letters: list     ← CoverLetterResult from communication_agent [NOT CONNECTED]
  │     ├── content
  │     └── evidence_refs: JSON list
  ├── answers: list           ← ApplicationAnswer [partially connected via API]
  │     ├── question
  │     ├── answer
  │     └── evidence_refs: JSON list
  └── events: list            ← ApplicationEvent [not populated]
```

### AgentSession (needs fixes)

```
ApplicationAgentSession
  ├── status: str             ← transitions: initializing→discovering→mapping→awaiting_human→ready_to_fill→filling→submitting→submitted|failed
  ├── intelligence_at: datetime  ← [NEW] timestamp for end of intelligence phase
  ├── screenshot_before_path: str ← [FIX] currently set to None
  └── screenshot_after_path: str  ← [NEW]
```

---

## 8. API Surface (Target)

### Existing (working)
```
POST /api/v1/agent/sessions/start
POST /api/v1/agent/sessions/{id}/resume
POST /api/v1/agent/sessions/{id}/submit
POST /api/v1/agent/sessions/{id}/fields/{field_id}/answer
GET  /api/v1/agent/sessions/{id}
```

### New (P1)
```
GET  /api/v1/applications/{id}/fit-analysis
GET  /api/v1/applications/{id}/decision
POST /api/v1/applications/{id}/outcome
GET  /api/v1/candidates/{id}/calibration
GET  /api/v1/agent/sessions/{id}/answers
PATCH /api/v1/agent/sessions/{id}/answers/{answer_id}
```

---

## 9. AI Provider Architecture

```python
# app/services/ai/provider.py — already implements this pattern

class LLMProvider(Protocol):
    async def structured_output(
        self,
        system: str,
        messages: list[dict],
        schema: type[BaseModel],
        model: str,
    ) -> BaseModel: ...

# Default provider: Anthropic claude-haiku-4-5-20251001
# Test provider: mock that returns preset fixtures
```

**Model assignments:**
| Agent | Model | Reason |
|-------|-------|--------|
| match_agent | claude-haiku-4-5-20251001 | High volume, simple scoring |
| application_agent | claude-haiku-4-5-20251001 | Structured strategy, fast |
| cv_agent | claude-haiku-4-5-20251001 | Lightweight rewrite, guided by strategy |
| communication_agent (cover letter) | claude-sonnet-4-6 | Quality writing, less frequent |
| communication_agent (answers) | claude-haiku-4-5-20251001 | Short-form, high volume |
| job_intelligence | claude-haiku-4-5-20251001 | Structured extraction |
| form_intelligence LLM fallback | claude-haiku-4-5-20251001 | Fast single-field classification |

---

## 10. Configuration — New Env Vars Needed

```bash
# Already required (AI calls)
ANTHROPIC_API_KEY=...

# New for P1
STORAGE_PATH=/var/lib/linkedin-intelligence   # screenshots, CV PDFs
MAX_INTELLIGENCE_TIMEOUT=30.0                  # seconds before intelligence phase times out

# Future (P3)
LINKEDIN_API_KEY=...    # only if/when authorized access is available
```

---

## 11. Testing Strategy

```
Unit tests (no I/O):
  - matching/engine.py — already tested
  - form_intelligence.py — already tested
  - claim_validator.py — already tested
  - learning_loop.py — already tested

Integration tests (SQLite in-memory + mock LLM):
  - orchestrator start() → DB records populated with correct values
  - resolver FROM_KB → returns KB answer when available
  - cv_storage → returns .pdf file path

E2E tests (real browser + mock ATS server):
  - EXISTING: test_full_e2e_with_mock_ats — 252 passing
  - NEW: test_intelligence_phase_e2e — start() with mock LLM → CVVersion in DB
  - NEW: test_pdf_attached_to_submit — submit() sends .pdf not .txt
```

---

## 12. Security Architecture (Invariants — Not Negotiable)

| Invariant | Enforcement |
|-----------|------------|
| No submit without human confirmation | `submit()` raises `AgentError` if `human_confirmed != True` |
| No invented values in any field | All values from `CandidateKnowledgeResolver`; resolver never invents |
| No invented CV content | `ClaimValidator` runs on cv_agent output; unsupported claims logged |
| External content is untrusted | Form labels, page text, ATS responses: never used as instructions |
| No unauthorized scraping | Job source connectors use only authorized APIs or public RSS |
| No PII in test datasets | Test fixtures use `uuid.hex[:8]` suffixes; no real candidate data |
| CV changes are auditable | Every `CVChange` has `original`, `adapted`, `rationale`, `evidence_ref` |
| Submission requires evidence | `ApplicationSubmission` only created if `is_confirmation_page()` returns True |
