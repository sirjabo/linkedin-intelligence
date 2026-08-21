"""Release v1.0 Golden Path validation.

Validates the full LinkedIn Intelligence pipeline against the v1 release criteria:
  1. Auth → Candidate KB → Job Intelligence → Matching → Application
  2. CV generation with evidence chain integrity
  3. Form: registration → auto-fill → human answers → submit
  4. Pre-submit safety gate: human_confirmed=False → HTTP 400 (non-bypassable)
  5. AI Evaluation: deterministic suite passes; LLM suite is present and skippable
  6. Duplicate-submission protection: second POST → 409
  7. Stats integrity: applied count increments exactly once

This file is the single authoritative test for declaring the system a v1 Release Candidate.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import AsyncClient

# ─── Synthetic fixtures ───────────────────────────────────────────────────────

SAMPLE_JD = """\
Senior Data Engineer — AcmeCorp
Full-time, remote-friendly.
Requirements: Python 3.9+, Apache Spark, dbt, 5+ years data engineering.
Nice to have: Kafka, Airflow.
"""

CANDIDATE_PROFILE = {
    "name": "Jane Release",
    "email": "release@golden.com",
    "salary_min_usd": 95_000,
    "work_authorization": "authorized",
    "availability": "immediate",
}


# ─── Main golden path ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_golden_path_full_pipeline(
    client: AsyncClient,
    mock_job_agent,
    mock_match_agent,
    mock_application_agents,
):
    """Full v1 pipeline: register → profile → job → match → application → form → submit."""

    # Phase 1: Auth
    reg = await client.post("/api/v2/auth/register",
                            json={"email": "release@golden.com", "password": "Release2026!"})
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # Phase 2: Candidate profile
    upd = await client.put("/api/v2/candidates/me", headers=headers, json=CANDIDATE_PROFILE)
    assert upd.status_code == 200
    assert upd.json()["name"] == "Jane Release"

    # Phase 3: Job parse
    job_resp = await client.post("/api/v2/jobs", headers=headers, json={"raw_jd": SAMPLE_JD})
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # Phase 4: Match
    match_resp = await client.post(f"/api/v2/jobs/{job_id}/match", headers=headers)
    assert match_resp.status_code == 200
    assert match_resp.json()["overall_score"] > 0

    # Phase 5: Application draft
    app_resp = await client.post("/api/v2/applications", headers=headers,
                                 json={"job_id": job_id, "notes": "Golden path test"})
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    # Phase 6a: Generate CV
    cv_resp = await client.post(f"/api/v2/applications/{app_id}/cv", headers=headers)
    assert cv_resp.status_code == 201, cv_resp.text
    cv_data = cv_resp.json()

    # CV evidence chain: all changes must carry evidence_refs
    for change in (cv_data.get("changes") or []):
        assert change.get("evidence_refs"), (
            f"CVChange '{change.get('section')}' has no evidence_refs — "
            "release criterion: all CV changes must cite evidence"
        )

    # Phase 6b: Generate cover letter
    cl_resp = await client.post(f"/api/v2/applications/{app_id}/cover-letter", headers=headers)
    assert cl_resp.status_code == 201, cl_resp.text
    assert cl_resp.json().get("content")

    # Phase 7: Form registration
    form_resp = await client.post(
        f"/api/v2/applications/{app_id}/form",
        headers=headers,
        json={
            "ats_url": "https://jobs.acmecorp.com/apply/123",
            "fields": [
                {"label": "Full Name", "field_type": "text", "is_required": True},
                {"label": "Phone", "field_type": "text", "is_required": True},
                {"label": "Why AcmeCorp?", "field_type": "textarea", "is_required": True},
            ],
        },
    )
    assert form_resp.status_code == 201, form_resp.text
    form_fields = form_resp.json()["fields"]

    phone_f = next((f for f in form_fields if "Phone" in f["label"]), None)
    essay_f = next((f for f in form_fields if "Why" in f["label"]), None)
    assert phone_f is not None and essay_f is not None

    # Phase 7a: Premature submit blocked (human fields still pending)
    early = await client.post(f"/api/v2/applications/{app_id}/submit",
                              headers=headers, json={})
    assert early.status_code == 422

    # Phase 7b: Answer human-required fields
    for fid, answer in [(phone_f["id"], "+1-555-0200"),
                        (essay_f["id"], "AcmeCorp's data platform is industry-leading.")]:
        r = await client.patch(f"/api/v2/applications/{app_id}/form/answer",
                               headers=headers,
                               json={"field_id": fid, "human_answer": answer})
        assert r.status_code == 200

    # Phase 8: Submit
    sub = await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers=headers,
        json={
            "confirmation_number": "ACME-GP-001",
            "submission_url": "https://jobs.acmecorp.com/confirmation/001",
            "submitted_via": "manual",
        },
    )
    assert sub.status_code == 201, sub.text
    assert sub.json()["confirmation_number"] == "ACME-GP-001"

    # Phase 9: Final state verification
    final = await client.get(f"/api/v2/applications/{app_id}", headers=headers)
    assert final.status_code == 200
    state = final.json()
    assert state["status"] == "applied"
    assert any(e["event_type"] == "applied" for e in state["events"])

    # Duplicate submit blocked → 409
    dup = await client.post(f"/api/v2/applications/{app_id}/submit",
                            headers=headers, json={})
    assert dup.status_code == 409

    # Stats reflect exactly one submission
    stats = await client.get("/api/v2/applications/stats/summary", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["funnel"]["applied"] == 1


# ─── P4: Pre-submit safety gate (HTTP layer) ──────────────────────────────────

@pytest.mark.asyncio
async def test_agent_submit_human_confirmed_false_blocked(client: AsyncClient, mock_job_agent):
    """human_confirmed=False → HTTP 400 before any submission logic runs."""
    reg = await client.post("/api/v2/auth/register",
                            json={"email": "safety@gatetest.com", "password": "Safety2026!"})
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # Create a real application so we pass the DB lookup
    job_resp = await client.post("/api/v2/jobs", headers=headers,
                                 json={"raw_jd": SAMPLE_JD})
    assert job_resp.status_code == 201
    app_resp = await client.post("/api/v2/applications", headers=headers,
                                 json={"job_id": job_resp.json()["id"]})
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    # Submit with human_confirmed=False → must return 400 NOT attempt submission
    resp = await client.post(
        f"/api/v2/applications/{app_id}/agent/submit",
        headers=headers,
        json={"human_confirmed": False, "dry_run": True},
    )
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "human_confirmed" in resp.text.lower()


@pytest.mark.asyncio
async def test_agent_submit_missing_human_confirmed_field(client: AsyncClient, mock_job_agent):
    """Omitting human_confirmed entirely → HTTP 422 (schema validation error)."""
    reg = await client.post("/api/v2/auth/register",
                            json={"email": "safety2@gatetest.com", "password": "Safety2026!"})
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    job_resp = await client.post("/api/v2/jobs", headers=headers, json={"raw_jd": SAMPLE_JD})
    assert job_resp.status_code == 201
    app_resp = await client.post("/api/v2/applications", headers=headers,
                                 json={"job_id": job_resp.json()["id"]})
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/agent/submit",
        headers=headers,
        json={"dry_run": True},  # no human_confirmed key
    )
    # Must fail before attempting any submission
    assert resp.status_code in (400, 422)


# ─── P4: Pre-submit safety gate (service layer) ───────────────────────────────

@pytest.mark.asyncio
async def test_orchestrator_submit_raises_without_human_confirmed():
    """ApplicationAgentOrchestrator.submit() raises AgentError when human_confirmed=False."""
    from app.services.application_agent_orchestrator import (
        AgentError,
        ApplicationAgentOrchestrator,
    )

    orch = ApplicationAgentOrchestrator()

    with pytest.raises(AgentError) as exc_info:
        # Pass human_confirmed=False — should raise AgentError immediately
        await orch.submit(session_id="fake-id", human_confirmed=False, db=None)

    assert "human_confirmed" in str(exc_info.value).lower()


# ─── P1: Sprint K deterministic AI evaluation ─────────────────────────────────

def test_ai_eval_deterministic_suite_passes():
    """Deterministic criteria in the AI eval framework always pass (no LLM required)."""
    from app.services.ai_evaluation import EvalCriterion, evaluate

    @dataclass
    class _FakeCV:
        score: float = 0.85
        summary: str = "Senior Data Engineer with 5+ years experience."

    output = _FakeCV()
    criteria = [
        EvalCriterion(
            name="score_in_range",
            check=lambda o: (0 <= o.score <= 1, f"score={o.score}"),
        ),
        EvalCriterion(
            name="summary_not_empty",
            check=lambda o: (bool(o.summary.strip()), "summary present"),
        ),
    ]

    report = evaluate(output, criteria)
    assert report.passed
    assert report.score == 1.0
    assert report.passed_count == 2


def test_cv_differentiation_score_distinct_cvs():
    """Two CVs with completely different bullets score 1.0 differentiation."""
    from app.services.ai_evaluation import cv_differentiation_score

    @dataclass
    class _Bullet:
        adapted: str

    @dataclass
    class _Exp:
        bullets_adapted: list

    @dataclass
    class _CV:
        experience_personalized: list

    cv_a = _CV([_Exp([_Bullet("built kafka streaming pipeline"),
                      _Bullet("designed dbt data models")])])
    cv_b = _CV([_Exp([_Bullet("led machine learning feature engineering"),
                      _Bullet("implemented airflow orchestration")])])

    score = cv_differentiation_score([cv_a, cv_b])
    assert score == 1.0, f"Expected 1.0, got {score}"


def test_cv_differentiation_score_identical_cvs_returns_zero():
    """Two CVs with identical bullets score 0.0 differentiation."""
    from app.services.ai_evaluation import cv_differentiation_score

    @dataclass
    class _Bullet:
        adapted: str

    @dataclass
    class _Exp:
        bullets_adapted: list

    @dataclass
    class _CV:
        experience_personalized: list

    shared_bullet = _Bullet("built python data pipelines")
    cv_a = _CV([_Exp([shared_bullet])])
    cv_b = _CV([_Exp([shared_bullet])])

    score = cv_differentiation_score([cv_a, cv_b])
    assert score == 0.0, f"Expected 0.0, got {score}"


def test_llm_eval_criteria_objects_are_importable():
    """All four LLM judge criteria can be imported and have required attributes."""
    from app.services.ai_evaluation import (
        CoverLetterClicheCriterion,
        CoverLetterCompanyHookCriterion,
        CVFactualityCriterion,
        CVPersonalizationCriterion,
    )
    for criterion in [
        CVFactualityCriterion,
        CVPersonalizationCriterion,
        CoverLetterClicheCriterion,
        CoverLetterCompanyHookCriterion,
    ]:
        assert criterion.name
        assert criterion.prompt_template
        assert criterion.weight > 0
        assert "{text}" in criterion.prompt_template


# ─── Pre-submit validator ──────────────────────────────────────────────────────

def test_pre_submit_validator_blocks_empty_required_field():
    """PreSubmitValidator rejects a form where a required field has no value."""
    from app.services.pre_submit_validator import PreSubmitValidator

    @dataclass
    class _F:
        label: str
        semantic_type: str = ""
        is_required: bool = True
        human_required: bool = False
        auto_fill_value: str | None = None
        human_answer: str | None = None

    validator = PreSubmitValidator()
    report = validator.validate([_F("Full Name", auto_fill_value=None, human_answer=None)])
    assert not report.passed
    assert len(report.errors) >= 1


def test_pre_submit_validator_passes_fully_answered_form():
    """PreSubmitValidator passes when all required fields have values."""
    from app.services.pre_submit_validator import PreSubmitValidator

    @dataclass
    class _F:
        label: str
        semantic_type: str = ""
        is_required: bool = True
        human_required: bool = False
        auto_fill_value: str | None = None
        human_answer: str | None = None

    validator = PreSubmitValidator()
    fields = [
        _F("Full Name", auto_fill_value="Jane Release"),
        _F("Email", auto_fill_value="jane@acme.com"),
        _F("Why us?", semantic_type="custom_essay", human_required=True,
           human_answer="I love the mission."),
    ]
    report = validator.validate(fields)
    assert report.passed, f"Expected pass but got errors: {report.errors}"


def test_pre_submit_validator_blocks_unconfirmed_sensitive_field():
    """A sensitive field (salary) without a human_answer blocks submission."""
    from app.services.pre_submit_validator import PreSubmitValidator

    @dataclass
    class _F:
        label: str
        semantic_type: str = ""
        is_required: bool = True
        human_required: bool = True
        auto_fill_value: str | None = None
        human_answer: str | None = None

    validator = PreSubmitValidator()
    fields = [
        _F("Salary Expectation", semantic_type="salary", auto_fill_value="95000", human_answer=None),
    ]
    report = validator.validate(fields)
    assert not report.passed
