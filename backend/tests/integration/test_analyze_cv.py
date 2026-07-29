"""Integration tests for POST /analyze/cv."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


SAMPLE_CV = (
    "Joaquín Pérez\n"
    "joaco@example.com | linkedin.com/in/joaco\n\n"
    "Summary\n"
    "Analytics Engineer with Python, SQL, pandas and n8n. Building AI skills with LangChain interest.\n\n"
    "Experience\n"
    "Analytics Engineer — BBVA\n"
    "- Desarrollé pipelines de datos en Python y SQL reduciendo el tiempo de reporting en 40%\n"
    "- Automatización con n8n y Power BI\n\n"
    "Skills\n"
    "Python, SQL, pandas, n8n, Power BI, Git, Docker, FastAPI\n\n"
    "Education\n"
    "Licenciatura en Sistemas\n"
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_analyze_cv_returns_score(client: AsyncClient) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_db

    from app.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db
    app.state.limiter.enabled = False

    response = await client.post(
        "/api/v1/analyze/cv",
        data={"cv_text": SAMPLE_CV, "target_role": "ai_engineer"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert 0 <= body["ats_score"] <= 100
    assert body["target_role"] == "ai_engineer"
    assert "keyword_analysis" in body
    assert "found" in body["keyword_analysis"]
    assert "recommendations" in body
    assert "analysis_id" in body


@pytest.mark.asyncio
async def test_analyze_cv_invalid_role(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analyze/cv",
        data={"cv_text": SAMPLE_CV, "target_role": "frontend_dev"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_ROLE"


@pytest.mark.asyncio
async def test_analyze_cv_too_short(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analyze/cv",
        data={"cv_text": "too short", "target_role": "ai_engineer"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_cv_missing_input(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analyze/cv",
        data={"target_role": "ai_engineer"},
    )
    assert response.status_code == 400
