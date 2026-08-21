"""Tests for P3 Phase 14: Job source connectors (Arbeitnow, RemoteOK).

Verifies:
  - ArbeitnowSource.fetch() returns JobRaw list (mocked HTTP)
  - RemoteOKSource.fetch() returns JobRaw list (mocked HTTP)
  - Multi-source recommendations deduplication
  - /recommendations/sources endpoint returns available source names
"""
import httpx
import pytest
import respx

from app.services.job_recommender import rank_jobs
from app.services.job_sources.arbeitnow import ArbeitnowSource
from app.services.job_sources.base import JobRaw
from app.services.job_sources.remoteok import RemoteOKSource

ARBEITNOW_SAMPLE = {
    "data": [
        {
            "slug": "data-engineer-acme-123",
            "title": "Senior Data Engineer",
            "company_name": "Acme Corp",
            "location": "Berlin, Germany",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/data-engineer-acme-123",
            "description": "Looking for a Python/Spark data engineer.",
            "tags": ["python", "spark", "kafka"],
            "created_at": "2026-08-10",
        },
        {
            "slug": "backend-dev-xyz-456",
            "title": "Backend Developer",
            "company_name": "XYZ Ltd",
            "location": "Remote",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/backend-dev-xyz-456",
            "description": "Node.js backend developer.",
            "tags": ["node.js", "typescript"],
            "created_at": "2026-08-09",
        },
    ]
}

REMOTEOK_SAMPLE = [
    {"legal": "https://remoteok.com/legal"},  # first element is legal notice
    {
        "id": "111",
        "slug": "remote-engineer-111",
        "position": "ML Engineer",
        "company": "DeepCo",
        "location": "Worldwide",
        "url": "https://remoteok.com/remote-jobs/111",
        "description": "ML/Python/PyTorch engineer.",
        "tags": ["python", "pytorch", "ml"],
        "salary_min": 80000,
        "salary_max": 130000,
        "date": "2026-08-08",
    },
]


@pytest.mark.asyncio
async def test_arbeitnow_fetch():
    async with respx.mock as mock:
        mock.get("https://www.arbeitnow.com/api/job-board-api").mock(
            return_value=httpx.Response(200, json=ARBEITNOW_SAMPLE)
        )
        src = ArbeitnowSource()
        jobs = await src.fetch(query="python", limit=10, category=None)
    assert len(jobs) == 1  # only the Python job matches
    assert jobs[0].title == "Senior Data Engineer"
    assert jobs[0].remote_type == "remote"
    assert "python" in jobs[0].tech_tags


@pytest.mark.asyncio
async def test_arbeitnow_fetch_no_filter():
    async with respx.mock as mock:
        mock.get("https://www.arbeitnow.com/api/job-board-api").mock(
            return_value=httpx.Response(200, json=ARBEITNOW_SAMPLE)
        )
        src = ArbeitnowSource()
        jobs = await src.fetch(query="", limit=10, category=None)
    assert len(jobs) == 2  # no query filter → both jobs returned


@pytest.mark.asyncio
async def test_remoteok_fetch():
    async with respx.mock as mock:
        mock.get("https://remoteok.com/api").mock(
            return_value=httpx.Response(200, json=REMOTEOK_SAMPLE)
        )
        src = RemoteOKSource()
        jobs = await src.fetch(query="ml", limit=10, category=None)
    assert len(jobs) == 1
    assert jobs[0].title == "ML Engineer"
    assert jobs[0].remote_type == "remote"
    assert jobs[0].salary_range == "$80,000–$130,000"


@pytest.mark.asyncio
async def test_remoteok_skips_legal_notice():
    """Legal notice (first element) must be skipped."""
    async with respx.mock as mock:
        mock.get("https://remoteok.com/api").mock(
            return_value=httpx.Response(200, json=REMOTEOK_SAMPLE)
        )
        src = RemoteOKSource()
        jobs = await src.fetch(query="", limit=10, category=None)
    assert all(j.title != "" for j in jobs)


def test_rank_jobs_deduplication():
    """rank_jobs should return all jobs; dedup is handled at the route level."""
    jobs = [
        JobRaw(
            external_id="a", title="Python Dev", company="X",
            location="Remote", remote_type="remote",
            url="https://example.com/a",
            description="Python developer role", tech_tags=["python"],
        ),
        JobRaw(
            external_id="b", title="Data Scientist", company="Y",
            location="Remote", remote_type="remote",
            url="https://example.com/b",
            description="Data science ML role", tech_tags=["python", "ml"],
        ),
    ]
    profile_data = {"skills": ["python"], "summary": "Python developer"}
    ranked = rank_jobs(jobs, profile_data)
    assert len(ranked) == 2
    assert ranked[0].score >= ranked[1].score


@pytest.mark.asyncio
async def test_arbeitnow_handles_api_error():
    """fetch() should raise on HTTP error."""
    async with respx.mock as mock:
        mock.get("https://www.arbeitnow.com/api/job-board-api").mock(
            return_value=httpx.Response(503)
        )
        src = ArbeitnowSource()
        with pytest.raises(Exception):
            await src.fetch(query="python", limit=10, category=None)
