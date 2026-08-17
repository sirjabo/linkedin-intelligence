"""Golden E2E test: full pipeline from registration to confirmed submission.

Covers every implemented phase:
  1. Auth: register + login
  2. Candidate KB: profile enrichment (name, salary, work_authorization)
  3. Job Intelligence: create job (parsed by mock agent)
  4. Matching 2.0: run match (deterministic engine + mocked LLM reasoning)
  5. Application: create application
  6. Application Agent: generate CV + cover letter
  7. Form Intelligence: register form, auto-fill, answer human fields
  8. Submission: submit with confirmation, verify final state
"""
import pytest
from httpx import AsyncClient


SAMPLE_JD = """\
Senior Data Engineer — TechCorp
We are looking for a Senior Data Engineer with 5+ years of experience.
Location: Buenos Aires, Argentina (hybrid)
Full-time position. Mandatory: Python, SQL.
"""


@pytest.mark.asyncio
async def test_golden_e2e(
    client: AsyncClient,
    mock_job_agent,
    mock_match_agent,
    mock_application_agents,
):
    """End-to-end pipeline: register → candidate KB → job → match →
    application → CV → cover letter → form → answer → submit → verify.
    """
    # ── Phase 1: Auth ──────────────────────────────────────────────────────────
    reg = await client.post(
        "/api/v2/auth/register",
        json={"email": "e2e@example.com", "password": "Secure1234"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ── Phase 2: Candidate KB — enrich profile ─────────────────────────────────
    upd = await client.put(
        "/api/v2/candidates/me",
        headers=headers,
        json={
            "name": "Alice Smith",
            "email": "e2e@example.com",
            "salary_min_usd": 90_000,
            "work_authorization": "authorized",
            "availability": "2_weeks",
        },
    )
    assert upd.status_code == 200
    cand = upd.json()
    assert cand["name"] == "Alice Smith"
    assert cand["email"] == "e2e@example.com"
    assert cand["salary_min_usd"] == 90_000
    assert cand["work_authorization"] == "authorized"

    # ── Phase 3: Job Intelligence — parse JD ──────────────────────────────────
    job_resp = await client.post(
        "/api/v2/jobs",
        headers=headers,
        json={"raw_jd": SAMPLE_JD},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]
    assert job_resp.json()["title"] == "Senior Data Engineer"

    # ── Phase 4: Matching 2.0 — run match ─────────────────────────────────────
    match_resp = await client.post(f"/api/v2/jobs/{job_id}/match", headers=headers)
    assert match_resp.status_code == 200
    match_data = match_resp.json()
    assert match_data["overall_score"] > 0
    assert "application_decision" in match_data  # Fase 1 field

    # ── Phase 5: Application — create draft ───────────────────────────────────
    app_resp = await client.post(
        "/api/v2/applications",
        headers=headers,
        json={"job_id": job_id},
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]
    assert app_resp.json()["status"] == "draft"

    # ── Phase 5b: Application Agent — generate CV ─────────────────────────────
    cv_resp = await client.post(f"/api/v2/applications/{app_id}/cv", headers=headers)
    assert cv_resp.status_code == 201
    cv_data = cv_resp.json()
    assert cv_data["summary_adapted"] is not None
    assert cv_data["validation_result"] is not None

    # ── Phase 5c: Cover Letter ─────────────────────────────────────────────────
    cl_resp = await client.post(
        f"/api/v2/applications/{app_id}/cover-letter",
        headers=headers,
    )
    assert cl_resp.status_code == 201
    assert len(cl_resp.json()["content"]) > 0

    # ── Phase 6: Form Intelligence — register form ─────────────────────────────
    form_resp = await client.post(
        f"/api/v2/applications/{app_id}/form",
        headers=headers,
        json={
            "form_url": "https://apply.techcorp.com/job/42",
            "fields": [
                {"label": "Full Name", "is_required": True},
                {"label": "Email Address", "is_required": True},
                {"label": "Expected Salary", "is_required": False},
                {"label": "Phone Number", "is_required": True},
                {"label": "Why do you want to join us?", "is_required": True},
            ],
        },
    )
    assert form_resp.status_code == 201, form_resp.text
    form_data = form_resp.json()
    assert len(form_data["fields"]) == 5

    # Auto-filled fields
    full_name_f = next(f for f in form_data["fields"] if f["semantic_type"] == "full_name")
    assert full_name_f["auto_fill_value"] == "Alice Smith"
    assert full_name_f["human_required"] is False

    salary_f = next(f for f in form_data["fields"] if f["semantic_type"] == "salary_expectation")
    assert salary_f["human_required"] is True  # salary is sensitive, must not be auto-filled
    assert salary_f["auto_fill_value"] is None

    # Human-required fields
    phone_f = next(f for f in form_data["fields"] if f["semantic_type"] == "phone")
    assert phone_f["human_required"] is True
    essay_f = next(f for f in form_data["fields"] if f["semantic_type"] == "custom_essay")
    assert essay_f["human_required"] is True

    # 3 human fields pending (phone + essay + salary)
    assert form_data["human_fields_pending"] == 3

    # ── Phase 6b: Answer human fields ─────────────────────────────────────────
    # Submitting while form has pending human fields should be blocked
    early_submit = await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers=headers,
        json={},
    )
    assert early_submit.status_code == 422

    # Answer the essay field
    await client.patch(
        f"/api/v2/applications/{app_id}/form/answer",
        headers=headers,
        json={"field_id": essay_f["id"], "human_answer": "I admire TechCorp's data-driven culture."},
    )
    # Answer the salary field (sensitive — always requires human confirmation)
    await client.patch(
        f"/api/v2/applications/{app_id}/form/answer",
        headers=headers,
        json={"field_id": salary_f["id"], "human_answer": "90000"},
    )
    # Answer the phone field — still 1 pending
    form_after_essay = await client.patch(
        f"/api/v2/applications/{app_id}/form/answer",
        headers=headers,
        json={"field_id": phone_f["id"], "human_answer": "+1-555-0100"},
    )
    assert form_after_essay.status_code == 200
    assert form_after_essay.json()["human_fields_pending"] == 0
    assert form_after_essay.json()["status"] == "ready"

    # ── Phase 7: Submit ────────────────────────────────────────────────────────
    sub_resp = await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers=headers,
        json={
            "confirmation_number": "TECHCORP-2026-001",
            "submission_url": "https://apply.techcorp.com/confirmation/001",
            "submitted_via": "manual",
            "notes": "Submitted after completing all form fields",
        },
    )
    assert sub_resp.status_code == 201, sub_resp.text
    sub_data = sub_resp.json()
    assert sub_data["confirmation_number"] == "TECHCORP-2026-001"
    assert sub_data["submitted_via"] == "manual"

    # ── Phase 8: Verify final state ────────────────────────────────────────────
    # Application status → applied
    final_app = await client.get(f"/api/v2/applications/{app_id}", headers=headers)
    assert final_app.status_code == 200
    app_state = final_app.json()
    assert app_state["status"] == "applied"
    assert app_state["applied_at"] is not None
    assert len(app_state["cv_versions"]) == 1
    assert len(app_state["cover_letters"]) == 1

    # Application event recorded
    events = app_state["events"]
    assert any(e["event_type"] == "applied" for e in events)

    # Submission retrievable via GET
    get_sub = await client.get(f"/api/v2/applications/{app_id}/submit", headers=headers)
    assert get_sub.status_code == 200
    assert get_sub.json()["confirmation_number"] == "TECHCORP-2026-001"

    # Duplicate submission blocked
    dup = await client.post(f"/api/v2/applications/{app_id}/submit", headers=headers, json={})
    assert dup.status_code == 409

    # Stats reflect the submission
    stats = await client.get("/api/v2/applications/stats/summary", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["funnel"]["applied"] == 1
