"""Tests for job endpoints — including user isolation and analysis."""
import pytest
from httpx import AsyncClient

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


async def _register_and_login(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v2/auth/register", json={"email": email, "password": "secure1234"})
    assert reg.status_code == 201
    return reg.json()["access_token"]


@pytest.mark.asyncio
async def test_analyze_jd_success(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "jtest1@example.com")
    resp = await client.post(
        "/api/v2/jobs/analyze",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": SAMPLE_JD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Senior Data Engineer"
    assert data["company"] == "TechCorp"
    assert data["seniority"] == "senior"
    assert data["remote_type"] == "hybrid"
    assert len(data["requirements"]) == 2
    assert data["parsing_confidence"] == 0.9
    assert "Python" in data["tech_stack"]


@pytest.mark.asyncio
async def test_analyze_overrides_title_company(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "jtest2@example.com")
    resp = await client.post(
        "/api/v2/jobs/analyze",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": SAMPLE_JD, "title": "Custom Title", "company": "My Company"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Custom Title"
    assert data["company"] == "My Company"


@pytest.mark.asyncio
async def test_analyze_jd_too_short(client: AsyncClient):
    token = await _register_and_login(client, "jtest3@example.com")
    resp = await client.post(
        "/api/v2/jobs/analyze",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": "too short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_analyze_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v2/jobs/analyze", json={"raw_jd": SAMPLE_JD})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient):
    token = await _register_and_login(client, "jtest4@example.com")
    resp = await client.get("/api/v2/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_job(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "jtest5@example.com")
    resp = await client.post(
        "/api/v2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": SAMPLE_JD},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Senior Data Engineer"
    assert data["company"] == "TechCorp"
    assert data["status"] == "analyzed"
    assert len(data["requirements"]) == 2
    assert "id" in data
    assert data["requirements"][0]["requirement_type"] == "must_have"
    assert data["requirements"][0]["seniority_signal"] == "5+ years"


@pytest.mark.asyncio
async def test_create_job_with_url_and_overrides(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "jtest6@example.com")
    resp = await client.post(
        "/api/v2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "raw_jd": SAMPLE_JD,
            "title": "Data Engineer II",
            "company": "ACME Corp",
            "job_url": "https://example.com/jobs/123",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Data Engineer II"
    assert data["company"] == "ACME Corp"
    assert data["job_url"] == "https://example.com/jobs/123"


@pytest.mark.asyncio
async def test_list_jobs_after_create(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "jtest7@example.com")
    await client.post(
        "/api/v2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": SAMPLE_JD},
    )
    resp = await client.get("/api/v2/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Data Engineer"
    assert len(jobs[0]["requirements"]) == 2


@pytest.mark.asyncio
async def test_get_job_by_id(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "jtest8@example.com")
    create_resp = await client.post(
        "/api/v2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": SAMPLE_JD, "job_url": "https://example.com/jobs/456"},
    )
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job_id
    assert data["job_url"] == "https://example.com/jobs/456"
    assert len(data["requirements"]) == 2
    assert data["tech_stack"] == ["Python", "Spark", "dbt", "Kafka"]


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient):
    token = await _register_and_login(client, "jtest9@example.com")
    resp = await client.get(
        "/api/v2/jobs/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_job_user_isolation(client: AsyncClient, mock_job_agent):
    """User B must not be able to read User A's jobs."""
    token_a = await _register_and_login(client, "jtest_a@example.com")
    token_b = await _register_and_login(client, "jtest_b@example.com")

    # User A saves a job
    create_resp = await client.post(
        "/api/v2/jobs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"raw_jd": SAMPLE_JD},
    )
    job_id = create_resp.json()["id"]

    # User B tries to fetch it by ID — should 404
    resp = await client.get(f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404

    # User B's list is empty
    list_resp = await client.get("/api/v2/jobs", headers={"Authorization": f"Bearer {token_b}"})
    assert list_resp.status_code == 200
    assert list_resp.json() == []
