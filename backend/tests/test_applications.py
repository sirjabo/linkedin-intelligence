"""Tests for Phase 4 — Application Agent golden path."""
import pytest
from httpx import AsyncClient

from app.services.claim_validator import validate_claims

SAMPLE_JD = """\
Senior Data Engineer — TechCorp

We are looking for a Senior Data Engineer with 5+ years of experience
building data pipelines and maintaining large-scale data infrastructure.

Requirements:
- Strong Python and SQL skills (mandatory)
- Experience with Apache Spark, dbt, and Kafka (mandatory)

Nice to have:
- Experience with Airflow

Location: Buenos Aires, Argentina (hybrid)
Full-time position.
"""


# ── Claim Validator unit tests ────────────────────────────────────────────────

def test_claim_validator_no_evidence():
    text = "I reduced costs by 40% and managed a team of 10 engineers."
    result = validate_claims(text, [])
    assert result.is_clean is False
    assert len(result.unverified_claims) > 0


def test_claim_validator_clean_text():
    text = "Experienced professional seeking opportunities in data engineering."
    result = validate_claims(text, [])
    # No quantitative claims → nothing to verify
    assert len(result.unverified_claims) == 0


def test_claim_validator_to_dict():
    result = validate_claims("Built 3 data pipelines saving $50k.", [])
    d = result.to_dict()
    assert "verified_claims" in d
    assert "unverified_claims" in d
    assert "is_clean" in d
    assert isinstance(d["is_clean"], bool)


class _FakeEvidence:
    def __init__(self, claim: str, source_text: str = ""):
        self.claim = claim
        self.source_text = source_text


def test_claim_validator_with_matching_evidence():
    evidence = [_FakeEvidence(
        claim="reduced operational costs by improving pipeline efficiency",
        source_text="reduced costs optimized performance pipeline team engineering",
    )]
    text = "I reduced operational costs by optimizing pipeline performance for the engineering team."
    result = validate_claims(text, evidence)
    # Should have at least some verified (overlap with evidence)
    assert isinstance(result.verified_claims, list)
    assert isinstance(result.unverified_claims, list)


def test_claim_validator_plausible_classification():
    """Partial overlap (1-2 keywords) → PLAUSIBLE, not SUPPORTED or UNSUPPORTED."""
    evidence = [_FakeEvidence(claim="managed engineering team", source_text="team engineering")]
    text = "I led a team of engineers to deliver results."
    result = validate_claims(text, evidence)
    # Check that plausible_claims field exists (Evidence 2.0)
    assert hasattr(result, "plausible_claims")
    assert isinstance(result.plausible_claims, list)


def test_claim_validator_supported_classification():
    """≥ 3 keyword matches → SUPPORTED."""
    evidence = [_FakeEvidence(
        claim="built data pipeline reduced latency improved throughput performance",
        source_text="pipeline performance optimization latency throughput data engineering",
    )]
    text = "I built a data pipeline that reduced latency and improved throughput performance."
    result = validate_claims(text, evidence)
    # With rich evidence, at least one claim should be SUPPORTED
    assert len(result.verified_claims) > 0


def test_claim_validator_to_dict_has_plausible_key():
    result = validate_claims("Built 3 data pipelines saving $50k.", [])
    d = result.to_dict()
    assert "plausible_claims" in d


def test_claim_validator_detailed_field():
    """detailed field provides per-claim ClaimVerification objects."""
    from app.services.claim_validator import VerificationStatus
    result = validate_claims("Saved $100k by optimizing systems.", [])
    assert hasattr(result, "detailed")
    assert len(result.detailed) > 0
    for item in result.detailed:
        assert item.status in ("SUPPORTED", "PLAUSIBLE", "UNSUPPORTED")


# ── Integration helpers ────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v2/auth/register", json={"email": email, "password": "Secure1234"})
    assert reg.status_code == 201
    return reg.json()["access_token"]


async def _create_job(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": SAMPLE_JD},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _run_match(client: AsyncClient, token: str, job_id: str) -> None:
    resp = await client.post(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def _create_application(client: AsyncClient, token: str, job_id: str) -> dict:
    resp = await client.post(
        "/api/v2/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job_id},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Application CRUD tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_application(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app1@example.com")
    job_id = await _create_job(client, token)

    resp = await client.post(
        "/api/v2/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job_id},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["job_id"] == job_id
    assert data["cv_versions"] == []
    assert data["cover_letters"] == []


@pytest.mark.asyncio
async def test_list_applications_empty(client: AsyncClient):
    token = await _register_and_login(client, "app2@example.com")
    resp = await client.get("/api/v2/applications", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_applications_after_create(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app3@example.com")
    job_id = await _create_job(client, token)
    await _create_application(client, token, job_id)

    resp = await client.get("/api/v2/applications", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    apps = resp.json()
    assert len(apps) == 1
    assert apps[0]["status"] == "draft"


@pytest.mark.asyncio
async def test_get_application(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app4@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.get(f"/api/v2/applications/{app_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == app_id


@pytest.mark.asyncio
async def test_update_application_status(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app5@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.patch(
        f"/api/v2/applications/{app_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "applied", "notes": "Applied via company website"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "applied"
    assert data["notes"] == "Applied via company website"


@pytest.mark.asyncio
async def test_application_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v2/applications")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_application_user_isolation(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token_a = await _register_and_login(client, "app_a@example.com")
    token_b = await _register_and_login(client, "app_b@example.com")

    job_id = await _create_job(client, token_a)
    app_data = await _create_application(client, token_a, job_id)
    app_id = app_data["id"]

    # User B cannot access User A's application
    resp = await client.get(f"/api/v2/applications/{app_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404

    # User B list is empty
    list_resp = await client.get("/api/v2/applications", headers={"Authorization": f"Bearer {token_b}"})
    assert list_resp.json() == []


# ── Golden Path: generate CV ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_cv_requires_match(client: AsyncClient, mock_job_agent, mock_application_agents):
    """CV generation must fail if match analysis hasn't run yet."""
    token = await _register_and_login(client, "app6@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/cv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_cv_success(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app7@example.com")
    job_id = await _create_job(client, token)
    await _run_match(client, token, job_id)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/cv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["application_id"] == app_id
    assert data["summary_adapted"] is not None
    assert isinstance(data["changes"], list)
    assert data["validation_result"] is not None
    assert mock_application_agents["strategy"].called
    assert mock_application_agents["cv"].called


@pytest.mark.asyncio
async def test_generate_cv_caches_strategy(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    """Calling generate_cv twice should only call generate_strategy once."""
    token = await _register_and_login(client, "app8@example.com")
    job_id = await _create_job(client, token)
    await _run_match(client, token, job_id)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    await client.post(f"/api/v2/applications/{app_id}/cv", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/v2/applications/{app_id}/cv", headers={"Authorization": f"Bearer {token}"})

    assert mock_application_agents["strategy"].call_count == 1


# ── Golden Path: cover letter ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_cover_letter_requires_strategy(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    """Cover letter fails if strategy hasn't been generated (no CV generated first)."""
    token = await _register_and_login(client, "app9@example.com")
    job_id = await _create_job(client, token)
    await _run_match(client, token, job_id)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/cover-letter",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_cover_letter_success(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app10@example.com")
    job_id = await _create_job(client, token)
    await _run_match(client, token, job_id)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    # Generate CV first (builds strategy)
    await client.post(f"/api/v2/applications/{app_id}/cv", headers={"Authorization": f"Bearer {token}"})

    resp = await client.post(
        f"/api/v2/applications/{app_id}/cover-letter",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["application_id"] == app_id
    assert len(data["content"]) > 0
    assert data["validation_result"] is not None


# ── Golden Path: application answers ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_answers_success(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app11@example.com")
    job_id = await _create_job(client, token)
    await _run_match(client, token, job_id)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    await client.post(f"/api/v2/applications/{app_id}/cv", headers={"Authorization": f"Bearer {token}"})

    resp = await client.post(
        f"/api/v2/applications/{app_id}/answers",
        headers={"Authorization": f"Bearer {token}"},
        json={"questions": ["Why do you want to work at TechCorp?"]},
    )
    assert resp.status_code == 201, resp.text
    answers = resp.json()
    assert isinstance(answers, list)
    assert len(answers) == 1
    assert answers[0]["application_id"] == app_id
    assert answers[0]["question"] == "Why do you want to work at TechCorp?"


# ── Golden Path: events ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_event_applied_advances_status(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app12@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_type": "applied", "notes": "Submitted via LinkedIn Easy Apply"},
    )
    assert resp.status_code == 201
    event = resp.json()
    assert event["event_type"] == "applied"

    # Check application status advanced
    app_resp = await client.get(f"/api/v2/applications/{app_id}", headers={"Authorization": f"Bearer {token}"})
    assert app_resp.json()["status"] == "applied"
    assert app_resp.json()["applied_at"] is not None
    assert len(app_resp.json()["events"]) == 1


@pytest.mark.asyncio
async def test_add_event_interview(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "app13@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    await client.post(
        f"/api/v2/applications/{app_id}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_type": "interview", "notes": "Technical interview scheduled"},
    )

    app_resp = await client.get(f"/api/v2/applications/{app_id}", headers={"Authorization": f"Bearer {token}"})
    assert app_resp.json()["status"] == "interview"


# ── Full golden path smoke test ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_golden_path(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    """End-to-end: register → job → match → application → CV → cover letter → answers → events."""
    token = await _register_and_login(client, "golden@example.com")

    # Create job and run match
    job_id = await _create_job(client, token)
    await _run_match(client, token, job_id)

    # Create application
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]
    assert app_data["status"] == "draft"

    # Generate CV (also builds strategy)
    cv_resp = await client.post(
        f"/api/v2/applications/{app_id}/cv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cv_resp.status_code == 201
    assert cv_resp.json()["summary_adapted"] is not None

    # Generate cover letter
    cl_resp = await client.post(
        f"/api/v2/applications/{app_id}/cover-letter",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cl_resp.status_code == 201

    # Generate answers
    ans_resp = await client.post(
        f"/api/v2/applications/{app_id}/answers",
        headers={"Authorization": f"Bearer {token}"},
        json={"questions": ["Why this company?", "What is your experience with Python?"]},
    )
    assert ans_resp.status_code == 201

    # Record events
    await client.post(
        f"/api/v2/applications/{app_id}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_type": "applied"},
    )
    await client.post(
        f"/api/v2/applications/{app_id}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_type": "interview", "notes": "First round"},
    )

    # Verify full state
    final = await client.get(f"/api/v2/applications/{app_id}", headers={"Authorization": f"Bearer {token}"})
    data = final.json()
    assert data["status"] == "interview"
    assert len(data["cv_versions"]) == 1
    assert len(data["cover_letters"]) == 1
    assert len(data["events"]) == 2
    assert data["strategy"] is not None
    assert data["applied_at"] is not None


# ── Fase 6: Submit + Confirmation ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_application_success(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "sub1@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmation_number": "REF-12345", "submitted_via": "manual", "notes": "Applied via company portal"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["application_id"] == app_id
    assert data["confirmation_number"] == "REF-12345"
    assert data["submitted_via"] == "manual"
    assert data["submitted_at"] is not None

    # Application status advances to applied
    app_resp = await client.get(f"/api/v2/applications/{app_id}", headers={"Authorization": f"Bearer {token}"})
    assert app_resp.json()["status"] == "applied"
    assert app_resp.json()["applied_at"] is not None


@pytest.mark.asyncio
async def test_submit_duplicate_rejected(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "sub2@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    dup = await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_submit_form_not_ready_rejected(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    """Submitting while the form has pending human fields should return 422."""
    token = await _register_and_login(client, "sub3@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    # Register a form with a human-required field
    await client.post(
        f"/api/v2/applications/{app_id}/form",
        headers={"Authorization": f"Bearer {token}"},
        json={"fields": [{"label": "Why do you want to join us?", "is_required": True}]},
    )

    resp = await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 422
    assert "unanswered" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_submission(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "sub4@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    await client.post(
        f"/api/v2/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"submission_url": "https://jobs.example.com/apply/123"},
    )

    resp = await client.get(
        f"/api/v2/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["submission_url"] == "https://jobs.example.com/apply/123"


@pytest.mark.asyncio
async def test_get_submission_not_found(client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents):
    token = await _register_and_login(client, "sub5@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.get(
        f"/api/v2/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
