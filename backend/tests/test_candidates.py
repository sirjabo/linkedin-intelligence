"""Tests for candidate endpoints — including user isolation."""
import pytest
from httpx import AsyncClient

from app.services.agents.profile_agent import extract_from_source


async def _register_and_login(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v2/auth/register", json={"email": email, "password": "Secure1234"})
    assert reg.status_code == 201
    return reg.json()["access_token"]


@pytest.mark.asyncio
async def test_get_candidate_after_register(client: AsyncClient):
    token = await _register_and_login(client, "alice2@example.com")
    resp = await client.get("/api/v2/candidates/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["name"] is None  # auto-created, no name yet


@pytest.mark.asyncio
async def test_update_candidate(client: AsyncClient):
    token = await _register_and_login(client, "bob2@example.com")
    resp = await client.put(
        "/api/v2/candidates/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Bob Smith", "location": "Buenos Aires", "target_roles": ["Analytics Engineer"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Bob Smith"
    assert data["target_roles"] == ["Analytics Engineer"]


@pytest.mark.asyncio
async def test_user_isolation(client: AsyncClient):
    """User A should not be able to update User B's profile."""
    token_a = await _register_and_login(client, "user_a@example.com")
    token_b = await _register_and_login(client, "user_b@example.com")

    # Update user A's profile
    await client.put(
        "/api/v2/candidates/me",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "User A"},
    )

    # User B reads their own profile — should see None, not "User A"
    resp = await client.get("/api/v2/candidates/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert resp.json()["name"] is None


@pytest.mark.asyncio
async def test_list_sources_empty(client: AsyncClient):
    token = await _register_and_login(client, "carol2@example.com")
    resp = await client.get("/api/v2/candidates/me/sources", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_ingest_text_source(client: AsyncClient, mock_profile_agent):
    token = await _register_and_login(client, "dave2@example.com")
    resp = await client.post(
        "/api/v2/candidates/me/sources/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_type": "linkedin", "raw_text": "Senior Data Engineer with 5 years experience..."},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_type"] == "linkedin"
    assert data["extracted_content"] is not None


@pytest.mark.asyncio
async def test_ingest_invalid_source_type(client: AsyncClient):
    token = await _register_and_login(client, "eve2@example.com")
    resp = await client.post(
        "/api/v2/candidates/me/sources/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_type": "twitter", "raw_text": "Some text"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rebuild_profile_no_sources(client: AsyncClient):
    token = await _register_and_login(client, "frank2@example.com")
    resp = await client.post(
        "/api/v2/candidates/me/profile/rebuild",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rebuild_profile_with_source(client: AsyncClient, mock_profile_agent):
    token = await _register_and_login(client, "grace@example.com")
    # Ingest a source
    await client.post(
        "/api/v2/candidates/me/sources/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_type": "cv", "raw_text": "Experienced engineer..."},
    )
    # Rebuild profile
    resp = await client.post(
        "/api/v2/candidates/me/profile/rebuild",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_get_profile_before_rebuild(client: AsyncClient):
    token = await _register_and_login(client, "henry@example.com")
    resp = await client.get("/api/v2/candidates/me/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_candidate_kb_fields(client: AsyncClient):
    """Knowledge Base 2.0: work_authorization, salary, availability, languages."""
    token = await _register_and_login(client, "kb_user@example.com")
    resp = await client.put(
        "/api/v2/candidates/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "work_authorization": "citizen",
            "availability": "immediate",
            "career_goals": "Become a Staff Engineer in AI infrastructure",
            "salary_min_usd": 120_000,
            "languages": [{"language": "English", "level": "native"}, {"language": "Spanish", "level": "fluent"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["work_authorization"] == "citizen"
    assert data["availability"] == "immediate"
    assert data["salary_min_usd"] == 120_000
    assert len(data["languages"]) == 2
    assert data["career_goals"] == "Become a Staff Engineer in AI infrastructure"


@pytest.mark.asyncio
async def test_extract_from_source_falls_back_without_llm_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.agents.profile_agent.settings.ANTHROPIC_API_KEY", "")
    monkeypatch.setattr("app.services.agents.profile_agent.settings.OPENROUTER_API_KEY", "")

    result = await extract_from_source(
        "Lucia Test\nBuenos Aires, Argentina\nBackend engineer with 5 years of experience in Python, FastAPI, PostgreSQL, Docker and AWS.",
        source_type="cv",
    )

    assert result.location == "Buenos Aires, Argentina"
    assert result.career_level == "mid"
    assert {skill.canonical_name for skill in result.skills} >= {"Python", "FastAPI", "PostgreSQL", "Docker", "AWS"}
    assert result.extraction_confidence == 0.35


@pytest.mark.asyncio
async def test_extract_from_source_falls_back_when_provider_errors(monkeypatch: pytest.MonkeyPatch):
    class BrokenProvider:
        async def structured_output(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    monkeypatch.setattr("app.services.agents.profile_agent.settings.ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("app.services.agents.profile_agent.settings.OPENROUTER_API_KEY", "")

    result = await extract_from_source(
        "Senior backend engineer based in Remote LATAM with Python and Redis experience.",
        source_type="linkedin",
        provider=BrokenProvider(),
    )

    assert result.career_level == "senior"
    assert result.location is not None
    assert any(skill.canonical_name == "Redis" for skill in result.skills)
