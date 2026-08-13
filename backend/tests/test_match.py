"""Tests for the matching engine and match endpoints."""
import pytest
from httpx import AsyncClient

from app.services.matching.engine import (
    compute_deterministic,
    tier_from_score,
    DeterministicResult,
)

SAMPLE_JD = """\
Senior Data Engineer — TechCorp

We are looking for a Senior Data Engineer with 5+ years of experience
building data pipelines and maintaining large-scale data infrastructure.

Requirements:
- Strong Python and SQL skills (mandatory)
- Experience with Apache Spark, dbt, and Kafka (mandatory)
- Familiarity with AWS or GCP

Nice to have:
- Experience with Airflow
- Knowledge of machine learning pipelines

Location: Buenos Aires, Argentina (hybrid)
Full-time position.
"""

SAMPLE_PROFILE = {
    "email": "match_test@example.com",
    "password": "Secure1234",
}


# ── Deterministic engine unit tests ───────────────────────────────────────────

class _FakeRequirement:
    """Minimal stand-in for JobRequirement ORM objects."""
    def __init__(self, description: str, requirement_type: str, category: str):
        self.description = description
        self.requirement_type = requirement_type
        self.category = category


def _make_req(desc: str, req_type: str = "must_have", cat: str = "technical") -> _FakeRequirement:
    return _FakeRequirement(desc, req_type, cat)


def test_tier_from_score_thresholds():
    assert tier_from_score(1.00) == "excellent"
    assert tier_from_score(0.85) == "excellent"
    assert tier_from_score(0.84) == "strong"
    assert tier_from_score(0.70) == "strong"
    assert tier_from_score(0.69) == "moderate"
    assert tier_from_score(0.55) == "moderate"
    assert tier_from_score(0.54) == "weak"
    assert tier_from_score(0.40) == "weak"
    assert tier_from_score(0.39) == "poor"
    assert tier_from_score(0.00) == "poor"


def test_compute_deterministic_perfect_match():
    skills = [{"canonical_name": "python"}, {"canonical_name": "sql"}, {"canonical_name": "spark"}]
    requirements = [
        _make_req("python"),
        _make_req("sql"),
        _make_req("spark"),
    ]
    result = compute_deterministic(
        profile_skills=skills,
        profile_career_level="senior",
        profile_education=[{"degree": "BS Computer Science"}],
        candidate_location="Buenos Aires, Argentina",
        job_seniority="senior",
        job_location="Buenos Aires, Argentina",
        job_remote_type=None,
        job_tech_stack=None,
        requirements=requirements,
    )
    assert isinstance(result, DeterministicResult)
    assert result.skill_overlap_score == 1.0
    assert result.experience_score == 1.0
    assert result.location_score == 1.0
    assert result.education_score == 1.0
    assert result.overall_score == pytest.approx(1.0, abs=0.01)
    assert "python" in result.matched_skills
    assert result.missing_skills == []


def test_compute_deterministic_no_skills():
    result = compute_deterministic(
        profile_skills=[],
        profile_career_level="junior",
        profile_education=None,
        candidate_location=None,
        job_seniority="senior",
        job_location="New York, USA",
        job_remote_type=None,
        job_tech_stack=["Python", "Spark"],
        requirements=[],
    )
    assert 0 <= result.overall_score <= 1.0
    assert result.skill_overlap_score == 0.0
    assert result.experience_score == 0.60  # junior=2, senior=4, distance=2 → 0.60
    assert result.location_score == 0.35


def test_compute_deterministic_remote_job():
    result = compute_deterministic(
        profile_skills=[],
        profile_career_level="mid",
        profile_education=None,
        candidate_location="Tokyo, Japan",
        job_seniority="mid",
        job_location="San Francisco, USA",
        job_remote_type="remote",
        job_tech_stack=[],
        requirements=[],
    )
    assert result.location_score == 1.0


def test_compute_deterministic_experience_distance_one():
    result = compute_deterministic(
        profile_skills=[],
        profile_career_level="senior",
        profile_education=None,
        candidate_location=None,
        job_seniority="staff",
        job_location=None,
        job_remote_type=None,
        job_tech_stack=[],
        requirements=[],
    )
    assert result.experience_score == 0.85  # senior=4, staff=5, distance=1


def test_compute_deterministic_nice_to_have_bonus():
    skills = [{"canonical_name": "airflow"}, {"canonical_name": "python"}]
    requirements = [
        _make_req("python", "must_have"),
        _make_req("airflow", "nice_to_have"),
    ]
    result = compute_deterministic(
        profile_skills=skills,
        profile_career_level="senior",
        profile_education=None,
        candidate_location=None,
        job_seniority="senior",
        job_location=None,
        job_remote_type=None,
        job_tech_stack=None,
        requirements=requirements,
    )
    # must_have: python matched = 1/1 = 1.0, bonus from airflow: +0.10
    assert result.skill_overlap_score == pytest.approx(1.0, abs=0.01)


# ── Integration tests ─────────────────────────────────────────────────────────

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


@pytest.mark.asyncio
async def test_run_match_success(client: AsyncClient, mock_job_agent, mock_match_agent):
    token = await _register_and_login(client, "match1@example.com")
    job_id = await _create_job(client, token)

    resp = await client.post(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "overall_score" in data
    assert "deterministic_score" in data
    assert "llm_score" in data
    assert data["llm_score"] == pytest.approx(0.80)
    assert data["match_tier"] in {"excellent", "strong", "moderate", "weak", "poor"}
    assert data["job_id"] == job_id
    assert mock_match_agent.called


@pytest.mark.asyncio
async def test_run_match_hybrid_score(client: AsyncClient, mock_job_agent, mock_match_agent):
    """Hybrid score = det * 0.60 + llm * 0.40."""
    token = await _register_and_login(client, "match2@example.com")
    job_id = await _create_job(client, token)

    resp = await client.post(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    det = data["deterministic_score"]
    llm = data["llm_score"]
    expected = round(det * 0.60 + llm * 0.40, 3)
    assert data["overall_score"] == pytest.approx(expected, abs=0.001)


@pytest.mark.asyncio
async def test_run_match_upsert(client: AsyncClient, mock_job_agent, mock_match_agent):
    """Running match twice returns the same match id (upsert behavior)."""
    token = await _register_and_login(client, "match3@example.com")
    job_id = await _create_job(client, token)

    r1 = await client.post(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    r2 = await client.post(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_get_match_after_run(client: AsyncClient, mock_job_agent, mock_match_agent):
    token = await _register_and_login(client, "match4@example.com")
    job_id = await _create_job(client, token)

    await client.post(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["llm_reasoning"] is not None
    assert isinstance(data["llm_strengths"], list)
    assert isinstance(data["llm_gaps"], list)


@pytest.mark.asyncio
async def test_get_match_not_found(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "match5@example.com")
    job_id = await _create_job(client, token)

    resp = await client.get(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_match_job_not_found(client: AsyncClient):
    token = await _register_and_login(client, "match6@example.com")
    resp = await client.post(
        "/api/v2/jobs/00000000-0000-0000-0000-000000000000/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_match_requires_auth(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "match7@example.com")
    job_id = await _create_job(client, token)

    resp = await client.post(f"/api/v2/jobs/{job_id}/match")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_match_user_isolation(client: AsyncClient, mock_job_agent, mock_match_agent):
    """User B cannot access or match User A's jobs."""
    token_a = await _register_and_login(client, "match_a@example.com")
    token_b = await _register_and_login(client, "match_b@example.com")

    job_id = await _create_job(client, token_a)

    # User B tries to run match on User A's job
    r_post = await client.post(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_post.status_code == 404

    # User B tries to get match on User A's job
    r_get = await client.get(
        f"/api/v2/jobs/{job_id}/match",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_get.status_code == 404
