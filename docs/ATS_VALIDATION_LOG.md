# ATS Validation Log

Tracks empirical accuracy measurements for the ATS Score Engine and Match Scorer,
including false positive/negative rates, blocker detection, and calibration results.

Updated automatically as test suites run. Manual entries are marked `[MANUAL]`.

---

## Calibration Dataset (v1) — 2026-08-17

**File**: `backend/tests/fixtures/matching_calibration.py`  
**Pairs**: 20 labeled (candidate, job, expected_decision) triples  
**Test file**: `backend/tests/test_matching_calibration.py`

### Dataset composition

| Decision | Count | % |
|----------|-------|---|
| apply    | 6     | 30% |
| skip     | 11    | 55% |
| stretch  | 3     | 15% |
| **Total**| **20**|    |

### Candidate archetypes

| Name | Seniority | Yrs | Auth | Skills |
|------|-----------|-----|------|--------|
| Alice Smith | senior | 7 | visa_required | Python, SQL, Spark, Airflow, AWS, PostgreSQL, dbt |
| Bob Jones | mid | 3 | visa_required | Python, SQL, Pandas, Docker |
| Carlos Ruiz | junior | 1 | authorized | Python, SQL |
| Diana Wang | staff | 9 | citizen | Python, SQL, Spark, Airflow, Kubernetes, dbt, Snowflake |
| Elena Torres | senior | 5 | authorized | React, TypeScript, CSS, GraphQL, Next.js |
| Felipe Moreno | senior | 6 | visa_required | Java, Spring Boot, Kafka, MySQL, Redis |
| Grace Kim | mid | 4 | citizen | Python, SQL, scikit-learn, TensorFlow, R, statistics |

### Scorer accuracy (rule-based, v1)

| Metric | Value | Threshold |
|--------|-------|-----------|
| Overall accuracy | **100%** (20/20) | ≥ 70% ✅ |
| False positive rate | **0%** (0/11 skip → apply) | < 20% ✅ |
| False negative rate | **0%** (0/6 apply → skip) | < 20% ✅ |
| Stretch recall | **100%** (3/3) | ≥ 30% ✅ |
| Blocker detection | 100% | 100% ✅ |

### Scorer rules (v1)

1. **HARD BLOCKER 1**: `visa_required` + no sponsorship → always `skip`
2. **HARD BLOCKER 2**: Skill domain completely different (0% overlap, ≥2 required skills) → `skip`
3. **HARD BLOCKER 3**: Salary ratio > 2× ceiling AND seniority gap ≥ 2 levels → `skip`
4. **SOFT SKIP A**: Skill ratio < 30% AND experience gap > 3 years → `skip`
5. **SOFT SKIP B**: Skill ratio < 60% AND underqualified in both exp and seniority → `skip`
6. **STRONG APPLY 1**: 100% skill match + not underqualified + salary ≤ 15% over ceiling → `apply`
7. **STRONG APPLY 2**: ≥60% skill match + exp gap ≤ 1yr + seniority within 1 level + salary close → `apply`
8. **APPLY**: Overqualified by exactly 1 seniority level + ≥60% skills + not underqualified → `apply`
9. **STRETCH**: Any remaining partial overlap (≥20% skills OR exp gap ≤ 4 years)
10. Default fallback: `skip`

### SQL normalization

`MySQL`, `PostgreSQL`, `SQLite`, `MSSQL`, `Oracle`, `TSQL` → normalized to `sql` for skill matching.
This ensures backend engineers with MySQL match roles requiring "SQL".

### Known calibration decisions

- `senior_de_nyc_relocation_required`: Changed `stretch` → `skip` (v1.0.1)
  - Rationale: `visa_required` + no sponsorship is a hard blocker regardless of skill match or relocation willingness. Consistent with `senior_de_no_sponsorship_remote_ok` which has the same blocker and expected `skip`.

- Salary treated as **soft signal** only:
  - Small overshoots ($65k candidate vs $50k max → `apply`) are acceptable per calibration rationale.
  - Hard salary block only when ratio > 2× AND seniority gap ≥ 2 (extreme mismatch).

---

## Mock ATS Lab — Scenario Coverage

**File**: `backend/tests/mock_ats/server.py`  
**Test files**: `tests/mock_ats/test_server.py`, `tests/mock_ats/test_new_scenarios.py`, `tests/test_golden_mock_ats.py`

### Scenarios implemented (v1)

| # | Endpoint | Field types | Status |
|---|----------|-------------|--------|
| 1 | `/apply` | text, email, tel, url, select, file, textarea, checkbox | ✅ |
| 5 | `/apply/radio` | radio buttons | ✅ |
| 6 | `/apply/multiselect` | multi-select | ✅ |
| 9 | `/apply/number` | number input | ✅ |
| 11 | `/apply/date` | date input | ✅ |
| 13 | `/apply/step1` + `/apply/step2` | two-step form | ✅ |
| 19 | `/apply/validation-error` | server-side validation | ✅ |
| 22 | `/apply/salary` | salary field | ✅ |
| 23 | `/apply/sponsorship` | sponsorship select | ✅ |
| 24 | `/apply` | work authorization (covered by scenario 1) | ✅ |
| 29 | `/apply/fail` | 500 error path | ✅ |
| 32 | `/apply/idempotent` | duplicate submit protection | ✅ |
| 33 | `/apply/fileupload` | file upload with filename echo | ✅ |

**Coverage**: 13/35 scenarios (37%) — target for Sprint PR-3+ is 70%.

---

## Golden E2E Test Results

**File**: `backend/tests/test_golden_mock_ats.py`  
**Tests**: 23 across 7 test classes  
**Status**: All passing ✅

| Test class | Scenarios | Tests |
|------------|-----------|-------|
| TestHealthAndLanding | 1 | 2 |
| TestGoldenSimpleForm | 1 | 4 |
| TestGoldenFileUpload | 33 | 3 |
| TestGoldenTwoStepForm | 13 | 3 |
| TestGoldenIdempotentSubmit | 32 | 3 |
| TestGoldenValidationError | 19 | 2 |
| TestGoldenFailScenario | 29 | 2 |
| TestGoldenSalaryAndSponsorship | 22, 23 | 4 |

---

## CV Differentiation Test Results

**File**: `backend/tests/test_cv_differentiation.py`  
**Tests**: 13  
**Status**: All passing ✅

Verifies that the CV agent produces meaningfully different personalizations
for 3 different job targets (data engineering, backend API, frontend):

- Summaries are distinct across all 3 CVs ✅
- Skills ordering differs between CVs (each job's stack leads) ✅
- ATS keywords are job-specific ✅
- Provider receives correct job title, company, and tech stack ✅

---

## Test Count History

| Date | Event | Tests |
|------|-------|-------|
| Sprint start | Baseline | 652 |
| 2026-08-17 | Mock ATS lab expansion (scenarios 5–32) | 680 |
| 2026-08-17 | PR-5: pause_metadata + crash simulation | 685 |
| 2026-08-17 | PR-7: error codes + sanitize + cost tracker | 723 |
| 2026-08-17 | PR-8: CI improvements + calibration fixture | 734 |
| 2026-08-17 | PR-8: calibration tests (11) | 734 |
| 2026-08-17 | Sanitize wiring | 734 |
| 2026-08-17 | PR-4/PR-8: file upload E2E + golden suite | 761 |
| 2026-08-17 | CV differentiation tests | 774 |

---

## Open Items

- [ ] Expand mock ATS lab from 13/35 to ≥25/35 scenarios (target: 70% coverage)
- [ ] AI evaluation suite with live LLM calls (blocked by proxy in CCR sandbox)
- [ ] Replace rule-based scorer with LLM-based match agent + keep calibration tests as regression guard
- [ ] Collect real application outcome data to validate FP/FN rates against ground truth
- [ ] Add form field classification calibration pairs (separate from job match calibration)
