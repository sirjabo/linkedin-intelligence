"""Tests for the /market/* endpoints (Phase: Skills Radar)."""
import pytest
from collections import Counter
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.job_sources.base import JobRaw
from app.api.routes.market import _slugify, _categorize, _aggregate_skills
import app.api.routes.market as market_module


@pytest.fixture(autouse=True)
def clear_market_cache():
    """Clear the in-memory market cache before every test to prevent state bleed."""
    market_module._CACHE.clear()
    yield
    market_module._CACHE.clear()


def _make_job(title="Python Engineer", company="Acme", tech_tags: list[str] | None = None) -> JobRaw:
    return JobRaw(
        external_id="jid-1",
        title=title,
        company=company,
        location="Remote",
        remote_type="remote",
        url=f"https://jobs.test/{title.replace(' ', '-').lower()}",
        tech_tags=tech_tags or ["python", "sql"],
        description="Build things with code",
        salary_range=None,
        published_at=None,
    )


class TestHelpers:
    def test_slugify_basic(self):
        assert _slugify("Python") == "python"

    def test_slugify_strips_spaces(self):
        assert _slugify("LangChain") == "langchain"

    def test_slugify_preserves_plus(self):
        assert _slugify("C++") == "c++"

    def test_categorize_known(self):
        assert _categorize("python") == "language"
        assert _categorize("react") == "frontend"
        assert _categorize("aws") == "cloud"
        assert _categorize("langchain") == "ai_ml"

    def test_categorize_unknown(self):
        assert _categorize("foobarxyz") == "other"


@pytest.mark.asyncio
async def test_list_roles():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v2/market/roles")
    assert r.status_code == 200
    data = r.json()
    assert "roles" in data
    assert "ai_engineer" in data["roles"]
    assert "data_engineer" in data["roles"]


@pytest.mark.asyncio
async def test_skills_radar_returns_structure():
    fake_jobs = [
        _make_job(company="A", tech_tags=["python", "fastapi"]),
        _make_job(company="B", tech_tags=["python", "sql"]),
        _make_job(company="C", tech_tags=["python", "docker"]),
    ]

    async def mock_fetch(*args, **kwargs):
        return fake_jobs

    with patch("app.api.routes.market._fetch_safe", new=mock_fetch):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v2/market/skills/ai_engineer?limit=10")

    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "ai_engineer"
    assert data["total_jobs_analyzed"] >= 0
    assert isinstance(data["skills"], list)
    if data["skills"]:
        first = data["skills"][0]
        assert "rank" in first
        assert "name" in first
        assert "frequency_pct" in first
        assert "job_count" in first


@pytest.mark.asyncio
async def test_skills_radar_python_is_top():
    """Python should rank first when it appears in all jobs."""
    fake_jobs = [
        _make_job(company=f"Co{i}", tech_tags=["python", "sql" if i % 2 == 0 else "dbt"])
        for i in range(6)
    ]

    async def mock_fetch(*args, **kwargs):
        return fake_jobs

    with patch("app.api.routes.market._fetch_safe", new=mock_fetch):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v2/market/skills/ai_engineer?limit=20")

    assert r.status_code == 200
    skills = r.json()["skills"]
    assert skills, "skills list should not be empty"
    assert skills[0]["slug"] == "python"
    assert skills[0]["frequency_pct"] == 100.0


@pytest.mark.asyncio
async def test_skills_radar_deduplicates_urls():
    """Jobs with the same URL should only be counted once."""
    shared_url = "https://jobs.test/shared"
    jobs = [
        JobRaw(
            external_id=f"id{i}", title="Dev", company=f"Co{i}",
            location="Remote", remote_type="remote", url=shared_url,
            tech_tags=["python"], description="", salary_range=None, published_at=None,
        )
        for i in range(3)
    ]

    async def mock_fetch(*args, **kwargs):
        return jobs

    with patch("app.api.routes.market._fetch_safe", new=mock_fetch):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v2/market/skills/ai_engineer")

    assert r.status_code == 200
    assert r.json()["total_jobs_analyzed"] == 1


@pytest.mark.asyncio
async def test_trends_endpoint():
    # Unique titles → unique URLs after _make_job URL generation
    fake_jobs = [
        _make_job(title="Python AI Engineer", company="Anthropic", tech_tags=["python", "langchain"]),
        _make_job(title="Python Backend Dev", company="OpenAI", tech_tags=["python", "fastapi"]),
        _make_job(title="ML Engineer Python", company="Anthropic", tech_tags=["python", "pytorch"]),
    ]

    async def mock_fetch(*args, **kwargs):
        return fake_jobs

    with patch("app.api.routes.market._fetch_safe", new=mock_fetch):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v2/market/trends?role=ai_engineer&limit=10")

    assert r.status_code == 200
    data = r.json()
    assert "top_skills" in data
    assert "top_companies" in data
    assert "total_jobs_analyzed" in data
    # Anthropic appears in 2 of 3 jobs → should be rank 1 company
    companies = {c["name"]: c["job_count"] for c in data["top_companies"]}
    assert companies.get("Anthropic", 0) == 2


@pytest.mark.asyncio
async def test_cache_serves_second_request_without_fetch():
    """Second identical request should be served from cache (fetch not called again)."""
    fake_jobs = [_make_job(company="CacheCo", tech_tags=["python"])]
    fetch_call_count = 0

    async def counting_fetch(*args, **kwargs):
        nonlocal fetch_call_count
        fetch_call_count += 1
        return fake_jobs

    with patch("app.api.routes.market._fetch_safe", new=counting_fetch):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/api/v2/market/skills/ai_engineer")
            await client.get("/api/v2/market/skills/ai_engineer")

    # _fetch_safe called 3× on first request (one per source), 0× on second
    assert fetch_call_count == 3


@pytest.mark.asyncio
async def test_skills_radar_unknown_role_still_works():
    """An unrecognised role slug should fall back to a derived query and return 200."""
    async def mock_fetch(*args, **kwargs):
        return []

    with patch("app.api.routes.market._fetch_safe", new=mock_fetch):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v2/market/skills/ruby_developer")

    assert r.status_code == 200
    assert r.json()["role"] == "ruby_developer"
    assert r.json()["skills"] == []
