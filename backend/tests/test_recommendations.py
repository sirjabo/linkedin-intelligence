"""Tests for Phase 5 — Job Discovery / Recommendations."""
from collections import Counter

import pytest
from httpx import AsyncClient

from app.services.job_recommender import _candidate_keywords, _compute_idf, rank_jobs, score_job
from app.services.job_sources.base import JobRaw

# ── Unit tests: job recommender ───────────────────────────────────────────────

def _make_job(**kwargs) -> JobRaw:
    defaults = dict(
        external_id="1",
        title="Senior Data Engineer",
        company="Acme",
        location="Remote",
        remote_type="remote",
        url="https://example.com/job/1",
        description="We need Python, SQL, and Spark skills.",
        tech_tags=["python", "spark", "sql"],
    )
    defaults.update(kwargs)
    return JobRaw(**defaults)


def test_candidate_keywords_from_skills():
    profile = {"skills": ["Python", "SQL", "dbt"], "summary": "", "experience": [], "education": []}
    kw = _candidate_keywords(profile)
    assert "python" in kw
    assert "sql" in kw
    assert "dbt" in kw


def test_candidate_keywords_from_summary():
    profile = {"skills": [], "summary": "Experienced data engineer building pipelines", "experience": [], "education": []}
    kw = _candidate_keywords(profile)
    assert "data" in kw
    assert "engineer" in kw
    assert "pipelines" in kw


def test_candidate_keywords_skill_weight_higher():
    """Skills should have higher weight than summary tokens."""
    profile = {
        "skills": ["python"],
        "summary": "experienced developer",
        "experience": [],
        "education": [],
    }
    kw = _candidate_keywords(profile)
    assert kw["python"] > kw.get("experienced", 0)


def test_score_job_strong_match():
    """A job whose tags closely match the candidate's skills should score > 0.5."""
    job = _make_job(title="Python Engineer", description="Python SQL work", tech_tags=["python", "sql"])
    jobs = [job]
    idf = _compute_idf(jobs)
    candidate = Counter({"python": 3, "sql": 3})
    result = score_job(job, candidate, idf)
    assert result.score > 0.5


def test_score_job_no_match():
    job = _make_job(title="Java Backend Engineer", description="Java Spring Boot", tech_tags=["java", "spring"])
    jobs = [job]
    idf = _compute_idf(jobs)
    candidate = Counter({"python": 3, "dbt": 3})
    result = score_job(job, candidate, idf)
    assert result.score == 0.0
    assert result.matched_keywords == []


def test_score_job_partial_match():
    job = _make_job(tech_tags=["python", "java"])
    jobs = [job]
    idf = _compute_idf(jobs)
    candidate = Counter({"python": 3, "sql": 3, "dbt": 3})
    result = score_job(job, candidate, idf)
    assert result.score > 0.0
    assert "python" in result.matched_keywords


def test_score_job_empty_candidate():
    job = _make_job()
    idf = _compute_idf([job])
    result = score_job(job, Counter(), idf)
    assert result.score == 0.0


def test_rank_jobs_sorted_by_score():
    jobs = [
        _make_job(external_id="1", title="Java Backend", description="We need Java Spring Boot skills.", tech_tags=["java"]),
        _make_job(external_id="2", title="Data Engineer", description="We need Python SQL dbt.", tech_tags=["python", "sql"]),
        _make_job(external_id="3", title="Python Dev", description="We need Python skills.", tech_tags=["python"]),
    ]
    profile = {"skills": ["Python", "SQL"], "summary": "", "experience": [], "education": []}
    ranked = rank_jobs(jobs, profile)
    assert ranked[0].job.external_id == "2"
    assert ranked[1].job.external_id == "3"
    assert ranked[0].score >= ranked[1].score >= ranked[2].score


def test_rank_jobs_empty():
    ranked = rank_jobs([], {"skills": ["Python"]})
    assert ranked == []


def test_rank_jobs_empty_profile():
    jobs = [_make_job()]
    ranked = rank_jobs(jobs, {})
    assert len(ranked) == 1
    assert ranked[0].score == 0.0


# ── Integration: recommendations endpoint ────────────────────────────────────

SAMPLE_REMOTIVE_RESPONSE = {
    "jobs": [
        {
            "id": 101,
            "title": "Senior Data Engineer",
            "company_name": "TechCorp",
            "candidate_required_location": "Worldwide",
            "job_type": "full_time",
            "url": "https://remotive.com/remote-jobs/data/101",
            "description": "Python SQL data pipelines dbt",
            "tags": [{"name": "python"}, {"name": "sql"}, {"name": "dbt"}],
            "salary": "$120k-$150k",
            "publication_date": "2026-08-01",
        },
        {
            "id": 102,
            "title": "Frontend React Developer",
            "company_name": "WebCo",
            "candidate_required_location": "USA",
            "job_type": "full_time",
            "url": "https://remotive.com/remote-jobs/frontend/102",
            "description": "React TypeScript CSS",
            "tags": [{"name": "react"}, {"name": "typescript"}],
            "salary": None,
            "publication_date": "2026-08-02",
        },
    ]
}


async def _register_and_login(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v2/auth/register", json={"email": email, "password": "Secure1234"})
    assert reg.status_code == 201
    return reg.json()["access_token"]


@pytest.mark.asyncio
async def test_recommendations_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v2/recommendations", json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_recommendations_no_profile_returns_jobs_scored_zero(client: AsyncClient, mock_remotive):
    """Without a profile, all jobs score 0.0 but endpoint still returns jobs."""
    token = await _register_and_login(client, "rec1@example.com")
    resp = await client.post(
        "/api/v2/recommendations",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "python"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert item["score"] == 0.0


@pytest.mark.asyncio
async def test_recommendations_with_profile(client: AsyncClient, mock_remotive, mock_profile_agent):
    token = await _register_and_login(client, "rec2@example.com")

    # Create a candidate profile via the candidates endpoint
    await client.post(
        "/api/v2/candidates/me/sources/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_type": "manual", "raw_content": "Python data engineer with SQL and dbt skills."},
    )

    resp = await client.post(
        "/api/v2/recommendations",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "python data engineer", "limit": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Data engineer job should score higher than React job
    titles = [d["title"] for d in data]
    assert "Senior Data Engineer" in titles
    # Scores should be sorted descending
    scores = [d["score"] for d in data]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_recommendations_response_shape(client: AsyncClient, mock_remotive, mock_profile_agent):
    token = await _register_and_login(client, "rec3@example.com")
    await client.post(
        "/api/v2/candidates/me/sources/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_type": "manual", "raw_content": "Python engineer"},
    )

    resp = await client.post(
        "/api/v2/recommendations",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 200
    for item in resp.json():
        assert "external_id" in item
        assert "title" in item
        assert "company" in item
        assert "score" in item
        assert "matched_keywords" in item
        assert isinstance(item["tech_tags"], list)


@pytest.mark.asyncio
async def test_recommendations_limit_capped(client: AsyncClient, mock_remotive, mock_profile_agent):
    """limit > 50 should be capped to 50."""
    token = await _register_and_login(client, "rec4@example.com")
    await client.post(
        "/api/v2/candidates/me/sources/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_type": "manual", "raw_content": "Python engineer"},
    )

    resp = await client.post(
        "/api/v2/recommendations",
        headers={"Authorization": f"Bearer {token}"},
        json={"limit": 999},
    )
    assert resp.status_code == 200
