"""Tests for POST /api/v2/analyze/linkedin."""
import pytest
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app
from app.services.linkedin_analyzer import (
    _compute_overall,
    _parse_llm_json,
    analyze_linkedin_profile,
)

_TEST_USER = {"email": "linkedin_test@example.com", "password": "TestPass123!"}


async def _get_token(client: AsyncClient) -> str:
    r = await client.post("/api/v2/auth/register", json=_TEST_USER)
    if r.status_code == 400:
        r = await client.post("/api/v2/auth/login", json=_TEST_USER)
    return r.json()["access_token"]


# ── Helper fixtures ────────────────────────────────────────────────────────────

FAKE_LLM_RESPONSE = {
    "current_title": "Analista de Datos SSR en BBVA",
    "section_scores": {
        "title": 30,
        "about": 60,
        "experience": 70,
        "skills": 55,
        "projects": 40,
        "education": 80,
    },
    "title_issues": [
        "No menciona el rol objetivo (AI Engineer)",
        "No incluye tecnologías clave",
    ],
    "title_variants": [
        "AI Engineer | Python · LangChain · SQL · GenAI",
        "Analytics → AI Engineer | LLMs · RAG · Python · FastAPI",
        "Data & AI Engineer | LangChain · Python · SQL · Cloud",
    ],
    "keyword_gaps": ["LangChain", "RAG", "FastAPI", "LangGraph", "MLflow"],
    "recommendations": [
        {"priority": 1, "section": "title", "message": "Reemplazá el título", "impact": "very_high"},
        {"priority": 2, "section": "about", "message": "Agregá un resumen con keywords", "impact": "high"},
        {"priority": 3, "section": "skills", "message": "Listá LangChain y RAG", "impact": "high"},
        {"priority": 4, "section": "experience", "message": "Cuantificá logros", "impact": "medium"},
        {"priority": 5, "section": "projects", "message": "Agregá un proyecto de IA", "impact": "medium"},
    ],
}

FAKE_PROFILE_TEXT = """
Juan Pérez
Analista de Datos SSR en BBVA
Buenos Aires, Argentina

Acerca de:
Trabajo con datos en el sector financiero. Python y SQL.

Experiencia:
BBVA — Analista de Datos (2022 - presente)
- Análisis de datos con Python y SQL
- Reportes en Power BI

Educación:
Universidad de Buenos Aires — Lic. en Sistemas (2022)

Skills: Python, SQL, Power BI, Excel
"""


def _make_anthropic_response(content: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=content)]
    return msg


# ── Unit tests: helpers ────────────────────────────────────────────────────────

class TestHelpers:
    def test_compute_overall_weighted(self):
        scores = {"title": 100, "about": 100, "experience": 100, "skills": 100, "projects": 100, "education": 100}
        assert _compute_overall(scores) == 100

    def test_compute_overall_zero(self):
        scores = {"title": 0, "about": 0, "experience": 0, "skills": 0, "projects": 0, "education": 0}
        assert _compute_overall(scores) == 0

    def test_compute_overall_partial(self):
        # title (25%) = 80 → 20, about (20%) = 0, experience (25%) = 0,
        # skills (15%) = 0, projects (10%) = 0, education (5%) = 0 → 20
        scores = {"title": 80, "about": 0, "experience": 0, "skills": 0, "projects": 0, "education": 0}
        assert _compute_overall(scores) == 20

    def test_parse_llm_json_plain(self):
        raw = json.dumps({"key": "value"})
        assert _parse_llm_json(raw) == {"key": "value"}

    def test_parse_llm_json_strips_fences(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        assert _parse_llm_json(raw) == {"key": "value"}

    def test_parse_llm_json_invalid_raises(self):
        with pytest.raises(Exception):
            _parse_llm_json("not json at all")


# ── Unit tests: service ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_profile_returns_structure():
    mock_response = _make_anthropic_response(json.dumps(FAKE_LLM_RESPONSE))

    with patch("app.services.linkedin_analyzer._client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        result = await analyze_linkedin_profile(FAKE_PROFILE_TEXT, "ai_engineer")

    assert "analysis_id" in result
    assert result["target_role"] == "ai_engineer"
    assert isinstance(result["overall_score"], int)
    assert 0 <= result["overall_score"] <= 100
    assert "section_scores" in result
    assert "title_analysis" in result
    assert len(result["title_analysis"]["suggested_variants"]) == 3
    assert "keyword_gaps" in result
    assert "recommendations" in result


@pytest.mark.asyncio
async def test_analyze_profile_overall_reflects_section_scores():
    mock_response = _make_anthropic_response(json.dumps(FAKE_LLM_RESPONSE))

    with patch("app.services.linkedin_analyzer._client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        result = await analyze_linkedin_profile(FAKE_PROFILE_TEXT, "ai_engineer")

    # Manually compute expected: 30*.25 + 60*.20 + 70*.25 + 55*.15 + 40*.10 + 80*.05
    expected = round(30 * 0.25 + 60 * 0.20 + 70 * 0.25 + 55 * 0.15 + 40 * 0.10 + 80 * 0.05)
    assert result["overall_score"] == expected


@pytest.mark.asyncio
async def test_analyze_profile_invalid_json_raises():
    mock_response = _make_anthropic_response("this is not json")

    with patch("app.services.linkedin_analyzer._client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        with pytest.raises(ValueError, match="invalid JSON"):
            await analyze_linkedin_profile(FAKE_PROFILE_TEXT, "ai_engineer")


# ── Integration tests: endpoint ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_linkedin_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v2/analyze/linkedin",
            json={"profile_text": FAKE_PROFILE_TEXT, "target_role": "ai_engineer"},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_analyze_linkedin_endpoint_success(client: AsyncClient):
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    mock_response = _make_anthropic_response(json.dumps(FAKE_LLM_RESPONSE))

    with patch("app.services.linkedin_analyzer._client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        r = await client.post(
            "/api/v2/analyze/linkedin",
            json={"profile_text": FAKE_PROFILE_TEXT, "target_role": "ai_engineer"},
            headers=headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["target_role"] == "ai_engineer"
    assert 0 <= data["overall_score"] <= 100
    assert len(data["title_analysis"]["suggested_variants"]) == 3
    assert len(data["recommendations"]) == 5


@pytest.mark.asyncio
async def test_analyze_linkedin_endpoint_empty_text(client: AsyncClient):
    token = await _get_token(client)
    r = await client.post(
        "/api/v2/analyze/linkedin",
        json={"profile_text": "   ", "target_role": "ai_engineer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_analyze_linkedin_endpoint_invalid_role(client: AsyncClient):
    token = await _get_token(client)
    r = await client.post(
        "/api/v2/analyze/linkedin",
        json={"profile_text": FAKE_PROFILE_TEXT, "target_role": "wizard_developer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_analyze_roles():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v2/analyze/linkedin/roles")
    assert r.status_code == 200
    data = r.json()
    assert "roles" in data
    assert "ai_engineer" in data["roles"]
