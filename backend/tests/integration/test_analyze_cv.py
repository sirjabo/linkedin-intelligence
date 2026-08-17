"""Integration tests for POST /analyze/cv — JSON body per brief."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

SAMPLE_CV = (
    "Soy Analytics Engineer con 5 años de experiencia en Python, SQL, pandas, "
    "n8n y Power BI. Trabajé en BBVA desarrollando pipelines de datos y "
    "automatizaciones. Tengo experiencia con PostgreSQL, Git y APIs REST."
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_analyze_cv_json_returns_score(client: AsyncClient) -> None:
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def override_get_db():
        yield mock_db

    from app.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db
    app.state.limiter.enabled = False

    response = await client.post(
        "/api/v1/analyze/cv",
        json={"cv_text": SAMPLE_CV, "target_role": "ai_engineer"},
    )

    app.dependency_overrides.clear()
    app.state.limiter.enabled = True

    assert response.status_code == 200, response.text
    body = response.json()
    assert 0 <= body["ats_score"] <= 100
    assert body["target_role"] == "ai_engineer"
    found = {k["keyword"] for k in body["keyword_analysis"]["found"]}
    assert "Python" in found
    assert "SQL" in found
    assert "analysis_id" in body
    assert "recommendations" in body


@pytest.mark.asyncio
async def test_analyze_cv_invalid_role(client: AsyncClient) -> None:
    app.state.limiter.enabled = False
    response = await client.post(
        "/api/v1/analyze/cv",
        json={"cv_text": SAMPLE_CV, "target_role": "frontend_dev"},
    )
    app.state.limiter.enabled = True
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_ROLE"


@pytest.mark.asyncio
async def test_analyze_cv_too_short(client: AsyncClient) -> None:
    app.state.limiter.enabled = False
    response = await client.post(
        "/api/v1/analyze/cv",
        json={"cv_text": "too short", "target_role": "ai_engineer"},
    )
    app.state.limiter.enabled = True
    assert response.status_code == 422
