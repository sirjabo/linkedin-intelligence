"""Tests for Phase 6 — Interview Prep."""
import pytest
from httpx import AsyncClient

SAMPLE_JD = """\
Senior Data Engineer — TechCorp

Requirements:
- Strong Python and SQL skills
- Experience with Apache Spark, dbt, and Kafka
"""


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


async def _create_application(client: AsyncClient, token: str, job_id: str) -> dict:
    resp = await client.post(
        "/api/v2/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job_id},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_interview_prep_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v2/applications/00000000-0000-0000-0000-000000000000/interview-prep")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_interview_prep_not_found(client: AsyncClient):
    token = await _register_and_login(client, "iv1@example.com")
    resp = await client.post(
        "/api/v2/applications/00000000-0000-0000-0000-000000000000/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_interview_prep_success(
    client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents, mock_interview_agent
):
    token = await _register_and_login(client, "iv2@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["application_id"] == app_id
    assert isinstance(data["technical_questions"], list)
    assert len(data["technical_questions"]) == 5
    assert isinstance(data["behavioral_questions"], list)
    assert len(data["behavioral_questions"]) == 5
    assert isinstance(data["star_stories"], list)
    assert len(data["star_stories"]) == 3
    assert isinstance(data["questions_to_ask"], list)
    assert len(data["questions_to_ask"]) == 5
    assert isinstance(data["company_research"], dict)
    assert mock_interview_agent.called


@pytest.mark.asyncio
async def test_generate_interview_prep_response_shape(
    client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents, mock_interview_agent
):
    token = await _register_and_login(client, "iv3@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()

    # Check technical question shape
    tq = data["technical_questions"][0]
    assert "question" in tq
    assert "rationale" in tq

    # Check behavioral question shape
    bq = data["behavioral_questions"][0]
    assert "question" in bq
    assert "competency" in bq

    # Check STAR story shape
    star = data["star_stories"][0]
    assert "competency" in star
    assert "situation" in star
    assert "task" in star
    assert "action" in star
    assert "result" in star

    # Check company research
    cr = data["company_research"]
    assert "culture" in cr
    assert "mission" in cr
    assert "values" in cr


@pytest.mark.asyncio
async def test_get_interview_prep_not_generated(
    client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents
):
    token = await _register_and_login(client, "iv4@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    resp = await client.get(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_interview_prep_after_generate(
    client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents, mock_interview_agent
):
    token = await _register_and_login(client, "iv5@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    await client.post(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["application_id"] == app_id
    assert len(data["technical_questions"]) == 5


@pytest.mark.asyncio
async def test_generate_interview_prep_updates_existing(
    client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents, mock_interview_agent
):
    """Calling generate twice should upsert, not create duplicates."""
    token = await _register_and_login(client, "iv6@example.com")
    job_id = await _create_job(client, token)
    app_data = await _create_application(client, token, job_id)
    app_id = app_data["id"]

    r1 = await client.post(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )
    r2 = await client.post(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    # Same id means it was updated, not duplicated
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_interview_prep_user_isolation(
    client: AsyncClient, mock_job_agent, mock_match_agent, mock_application_agents, mock_interview_agent
):
    token_a = await _register_and_login(client, "iva@example.com")
    token_b = await _register_and_login(client, "ivb@example.com")

    job_id = await _create_job(client, token_a)
    app_data = await _create_application(client, token_a, job_id)
    app_id = app_data["id"]

    resp = await client.post(
        f"/api/v2/applications/{app_id}/interview-prep",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
