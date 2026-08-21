"""Integration tests for salary, benchmark, and about-writer endpoints.

Uses in-memory SQLite (via conftest) — no real DB, no real HTTP, no real LLM.
"""
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.market import SkillSnapshot


async def _register_and_login(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v2/auth/register", json={"email": email, "password": "Secure1234"})
    assert reg.status_code == 201
    return reg.json()["access_token"]


# ── Market salary ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_salary_known_role(client: AsyncClient):
    resp = await client.get("/api/v2/market/salary/ai_engineer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "ai_engineer"
    assert data["available"] is True
    assert data["min_usd"] > 0
    assert data["max_usd"] >= data["median_usd"] >= data["min_usd"]


@pytest.mark.asyncio
async def test_salary_unknown_role_returns_unavailable(client: AsyncClient):
    resp = await client.get("/api/v2/market/salary/nonexistent_role")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert "nonexistent_role" in data["message"]


@pytest.mark.asyncio
async def test_salary_list_all_roles(client: AsyncClient):
    resp = await client.get("/api/v2/market/salary")
    assert resp.status_code == 200
    data = resp.json()
    assert "roles" in data
    assert len(data["roles"]) == 8
    for role_data in data["roles"].values():
        assert "min_usd" in role_data
        assert "max_usd" in role_data
        assert "median_usd" in role_data


# ── Benchmark ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_benchmark_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v2/candidates/me/benchmark?role=ai_engineer")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_benchmark_invalid_role(client: AsyncClient):
    token = await _register_and_login(client, "bench_bad@example.com")
    resp = await client.get(
        "/api/v2/candidates/me/benchmark?role=invalid_role",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_benchmark_no_skills_returns_inicial(client: AsyncClient, db_session: AsyncSession):
    """Candidate with no skills and snapshot data → 0 matches → Inicial tier."""
    token = await _register_and_login(client, "bench_zero@example.com")

    today = date.today()
    for slug, name, freq in [
        ("python", "Python", 85.0),
        ("docker", "Docker", 60.0),
        ("pytorch", "PyTorch", 50.0),
    ]:
        db_session.add(SkillSnapshot(
            id=uuid.uuid4(),
            role="ai_engineer",
            skill_slug=slug,
            skill_name=name,
            category="other",
            frequency_pct=freq,
            job_count=int(freq * 2),
            snapshot_date=today,
        ))
    await db_session.commit()

    resp = await client.get(
        "/api/v2/candidates/me/benchmark?role=ai_engineer",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "ai_engineer"
    assert data["matched_count"] == 0
    assert data["total_checked"] == 3
    assert data["percentile"] == 0
    assert data["tier"] == "Inicial"
    assert data["profile_has_skills"] is False


@pytest.mark.asyncio
async def test_benchmark_uses_snapshot_data(client: AsyncClient, db_session: AsyncSession):
    """Reads from SkillSnapshot instead of calling live API."""
    token = await _register_and_login(client, "bench_snap@example.com")

    # Seed 5 market skills
    today = date.today()
    seeds = [
        ("python", "Python", 85.0),
        ("docker", "Docker", 60.0),
        ("pytorch", "PyTorch", 50.0),
        ("langchain", "LangChain", 45.0),
        ("aws", "AWS", 40.0),
    ]
    for slug, name, freq in seeds:
        db_session.add(SkillSnapshot(
            id=uuid.uuid4(),
            role="data_engineer",
            skill_slug=slug,
            skill_name=name,
            category="other",
            frequency_pct=freq,
            job_count=int(freq * 2),
            snapshot_date=today,
        ))
    await db_session.commit()

    resp = await client.get(
        "/api/v2/candidates/me/benchmark?role=data_engineer",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checked"] == 5
    assert "matched_skills" in data
    assert "missing_skills" in data
    assert len(data["matched_skills"]) + len(data["missing_skills"]) == 5
    assert "percentile" in data
    assert "tier" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_benchmark_fallback_when_no_snapshot(client: AsyncClient):
    """Falls back to _aggregate_skills when DB has no snapshot for the role."""
    token = await _register_and_login(client, "bench_fallback@example.com")

    from collections import Counter

    from app.services.job_sources.base import JobRaw

    fake_jobs = [JobRaw(
        external_id="1",
        title="ML Engineer",
        company="Co",
        location="Remote",
        remote_type="remote",
        url="https://example.com/1",
        description="python pytorch",
        tech_tags=["python", "pytorch"],
        salary_range=None,
        published_at="2026-08-01",
    )]
    fake_counter: Counter = Counter({"python": 1, "pytorch": 1})

    with patch(
        "app.api.routes.market._aggregate_skills",
        new_callable=AsyncMock,
    ) as mock_agg:
        mock_agg.return_value = (fake_jobs, fake_counter)
        resp = await client.get(
            "/api/v2/candidates/me/benchmark?role=ml_engineer",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checked"] == 2
    mock_agg.assert_called_once()


# ── About-writer ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_about_writer_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v2/analyze/about-writer",
        json={"target_role": "ai_engineer", "profile_summary": "Senior AI Engineer with 5 years experience."},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_about_writer_invalid_role(client: AsyncClient):
    token = await _register_and_login(client, "about_bad@example.com")
    resp = await client.post(
        "/api/v2/analyze/about-writer",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_role": "invalid_role", "profile_summary": "Some text that is long enough for testing purposes."},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_about_writer_summary_too_short(client: AsyncClient):
    token = await _register_and_login(client, "about_short@example.com")
    resp = await client.post(
        "/api/v2/analyze/about-writer",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_role": "ai_engineer", "profile_summary": "Too short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_about_writer_success(client: AsyncClient):
    token = await _register_and_login(client, "about_ok@example.com")

    mock_result = {
        "writer_id": str(uuid.uuid4()),
        "target_role": "ai_engineer",
        "variants": [
            {"id": 1, "tone": "técnico y directo", "text": "Soy un AI Engineer con 5 años..."},
            {"id": 2, "tone": "narrativo y humano", "text": "Mi camino en la inteligencia artificial..."},
            {"id": 3, "tone": "orientado a resultados", "text": "Con 5 años de experiencia construyendo..."},
        ],
        "tips": ["Agregar métricas concretas", "Incluir logros cuantificables"],
    }

    with patch("app.api.routes.analyze.write_about_section", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = mock_result
        resp = await client.post(
            "/api/v2/analyze/about-writer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "target_role": "ai_engineer",
                "profile_summary": "Senior AI Engineer with 5 years building LLM-based products at scale.",
                "key_skills": ["python", "langchain", "aws"],
                "achievements": ["Reduced latency by 40%", "Led team of 5 engineers"],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["variants"]) == 3
    assert "tips" in data
    assert data["target_role"] == "ai_engineer"
    assert "writer_id" in data
    mock_write.assert_called_once()


@pytest.mark.asyncio
async def test_about_writer_llm_error_returns_502(client: AsyncClient):
    token = await _register_and_login(client, "about_err@example.com")

    with patch("app.api.routes.analyze.write_about_section", new_callable=AsyncMock) as mock_write:
        mock_write.side_effect = ValueError("About writer returned invalid JSON")
        resp = await client.post(
            "/api/v2/analyze/about-writer",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "target_role": "ai_engineer",
                "profile_summary": "Senior AI Engineer with 5 years building LLM-based products at scale.",
            },
        )

    assert resp.status_code == 502
