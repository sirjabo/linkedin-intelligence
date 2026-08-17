"""Integration tests for LinkedIn analyzer and market skills."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

SAMPLE_PROFILE = """
AI Engineer | Python · LangChain · RAG · FastAPI · SQL

About
Building production RAG systems with LangChain and FastAPI.
I reduced retrieval latency by 40% across 3 LLM pipelines in the last 2 years.
Open to AI Engineer roles — let's connect.

Experience
AI Engineer at Acme (2022 - Present)
Built RAG pipelines with Python, LangChain, and PostgreSQL

Projects
RAG Chatbot — Python, LangChain, OpenAI

Skills
Python · LangChain · FastAPI · SQL · Docker · AWS

Education
BSc Computer Science — University (2018)
"""


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_analyze_linkedin_returns_score(client: AsyncClient) -> None:
    app.state.limiter.enabled = False
    response = await client.post(
        "/api/v1/analyze/linkedin",
        json={"profile_text": SAMPLE_PROFILE, "target_role": "ai_engineer"},
    )
    app.state.limiter.enabled = True
    assert response.status_code == 200, response.text
    body = response.json()
    assert 0 <= body["overall_score"] <= 100
    assert body["section_scores"]["title"] > 50
    assert body["title_analysis"]["suggested_variants"]
    assert body["recommendations"]


@pytest.mark.asyncio
async def test_market_skills_ai_engineer(client: AsyncClient) -> None:
    app.state.limiter.enabled = False
    response = await client.get("/api/v1/market/skills/ai_engineer")
    app.state.limiter.enabled = True
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "ai_engineer"
    names = {s["name"] for s in body["skills"]}
    assert "Python" in names
    assert "LangChain" in names
    assert body["total_jobs_analyzed"] > 0


@pytest.mark.asyncio
async def test_market_trends_has_rising(client: AsyncClient) -> None:
    app.state.limiter.enabled = False
    response = await client.get("/api/v1/market/trends", params={"role": "ai_engineer"})
    app.state.limiter.enabled = True
    assert response.status_code == 200, response.text
    body = response.json()
    assert "rising" in body
    assert any(item["skill"] == "LangGraph" for item in body["rising"])
