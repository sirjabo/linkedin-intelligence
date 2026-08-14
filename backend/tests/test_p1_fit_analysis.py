"""Tests for P1 Phase 5: Fit Analysis + Decision + Outcome endpoints.

Verifies:
  - GET /applications/{id}/fit-analysis returns structured match breakdown
  - GET /applications/{id}/decision returns APPLY/BLOCKED/STRETCH etc.
  - POST /applications/{id}/outcome records outcome on MatchAnalysis
  - 404 when no match analysis exists
  - 400 on invalid outcome value
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.user import User
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.match import MatchAnalysis
from app.db.models.application import Application
from app.main import app
from app.db.session import get_db
from app.api.deps import get_current_user


# ── In-memory SQLite DB ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def engine():
    e = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await e.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def user_and_candidate(db_session):
    user = User(id=uuid.uuid4(), email="test@example.com",
                hashed_password="x", is_active=True)
    candidate = Candidate(
        id=uuid.uuid4(), user_id=user.id,
        name="Jane Doe", email="jane@example.com", location="Buenos Aires",
    )
    db_session.add(user)
    db_session.add(candidate)
    await db_session.commit()
    return user, candidate


@pytest_asyncio.fixture
async def job(db_session, user_and_candidate):
    _, candidate = user_and_candidate
    j = Job(
        id=uuid.uuid4(), candidate_id=candidate.id,
        title="Senior Data Engineer", company="BigCo",
        tech_stack=["Python", "Spark"], seniority="senior",
        raw_jd="Looking for a senior data engineer.",
        status="analyzed",
    )
    db_session.add(j)
    await db_session.commit()
    return j


@pytest_asyncio.fixture
async def application(db_session, user_and_candidate, job):
    _, candidate = user_and_candidate
    app_obj = Application(
        id=uuid.uuid4(), candidate_id=candidate.id,
        job_id=job.id, status="draft",
    )
    db_session.add(app_obj)
    await db_session.commit()
    return app_obj


@pytest_asyncio.fixture
async def match(db_session, user_and_candidate, job):
    _, candidate = user_and_candidate
    m = MatchAnalysis(
        id=uuid.uuid4(), candidate_id=candidate.id, job_id=job.id,
        overall_score=0.82, deterministic_score=0.78, llm_score=0.88,
        match_tier="strong",
        skill_overlap_score=0.90, experience_score=0.85,
        location_score=0.75, education_score=1.0,
        matched_skills=["Python", "Spark"],
        missing_skills=["Kafka"],
        llm_reasoning="Good Python/Spark match; Kafka is a gap.",
        llm_strengths=["Python", "Spark"],
        llm_gaps=["Kafka"],
        career_fit_score=0.90,
        application_decision="APPLY_WITH_CUSTOMIZATION",
        hard_blockers=[],
    )
    db_session.add(m)
    await db_session.commit()
    return m


@pytest_asyncio.fixture
async def authed_client(db_session, user_and_candidate):
    """AsyncClient with DB and auth overrides applied."""
    user, _ = user_and_candidate

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Tests — fit-analysis ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fit_analysis_returns_breakdown(authed_client, application, match):
    """GET /applications/{id}/fit-analysis returns score breakdown from MatchAnalysis."""
    resp = await authed_client.get(f"/api/v2/applications/{application.id}/fit-analysis")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["job_fit_score"] == pytest.approx(0.82, abs=0.01)
    assert data["match_tier"] == "strong"
    assert "Python" in data["matched_skills"]
    assert "Kafka" in data["missing_skills"]
    assert data["career_fit_score"] == pytest.approx(0.90, abs=0.01)
    assert data["skill_overlap_score"] == pytest.approx(0.90, abs=0.01)


@pytest.mark.asyncio
async def test_fit_analysis_404_when_no_match(authed_client, application):
    """GET /applications/{id}/fit-analysis returns 404 when no match exists."""
    resp = await authed_client.get(f"/api/v2/applications/{application.id}/fit-analysis")
    assert resp.status_code == 404


# ── Tests — decision ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_decision_returns_recommendation(authed_client, application, match):
    """GET /applications/{id}/decision returns application decision."""
    resp = await authed_client.get(f"/api/v2/applications/{application.id}/decision")
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "APPLY_WITH_CUSTOMIZATION"
    assert isinstance(data["blockers"], list)
    assert data["overall_approach"] is None  # no strategy set


@pytest.mark.asyncio
async def test_decision_includes_strategy_approach(
    authed_client, application, match, db_session
):
    """Decision endpoint includes overall_approach from application.strategy."""
    application.strategy = {"overall_approach": "Lead with Spark pipeline experience"}
    await db_session.commit()

    resp = await authed_client.get(f"/api/v2/applications/{application.id}/decision")
    assert resp.status_code == 200
    assert "Spark pipeline" in resp.json()["overall_approach"]


# ── Tests — outcome ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_outcome_success(authed_client, application, match, db_session):
    """POST /applications/{id}/outcome records outcome on MatchAnalysis."""
    resp = await authed_client.post(
        f"/api/v2/applications/{application.id}/outcome",
        json={"outcome": "got_interview"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "got_interview"
    assert data["match_tier"] == "strong"

    # Verify persisted in DB
    await db_session.refresh(match)
    assert match.outcome == "got_interview"


@pytest.mark.asyncio
async def test_record_outcome_invalid_value(authed_client, application, match):
    """POST /applications/{id}/outcome rejects unknown outcome values."""
    resp = await authed_client.post(
        f"/api/v2/applications/{application.id}/outcome",
        json={"outcome": "hacked"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_record_outcome_404_no_match(authed_client, application):
    """POST /applications/{id}/outcome returns 404 when no match exists."""
    resp = await authed_client.post(
        f"/api/v2/applications/{application.id}/outcome",
        json={"outcome": "rejected"},
    )
    assert resp.status_code == 404
