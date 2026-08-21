"""Tests for P2 Phase 12: Agent answer list + update endpoints.

Verifies:
  - GET /applications/{id}/agent/answers returns all ApplicationAnswer rows
  - PATCH /applications/{id}/agent/answers/{answer_id} updates the answer text
  - 404 when answer not found
  - 404 when application not found
"""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.models.application import Application, ApplicationAnswer
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.user import User
from app.db.session import get_db
from app.main import app

# ── In-memory DB ──────────────────────────────────────────────────────────────

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
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def user_and_candidate(db_session):
    user = User(id=uuid.uuid4(), email="test@example.com", hashed_password="x", is_active=True)
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
        title="Data Engineer", company="Acme",
        tech_stack=["Python"], seniority="senior",
        raw_jd="...", status="analyzed",
    )
    db_session.add(j)
    await db_session.commit()
    return j


@pytest_asyncio.fixture
async def application(db_session, user_and_candidate, job):
    _, candidate = user_and_candidate
    a = Application(
        id=uuid.uuid4(), candidate_id=candidate.id,
        job_id=job.id, status="draft",
    )
    db_session.add(a)
    await db_session.commit()
    return a


@pytest_asyncio.fixture
async def answers(db_session, application):
    a1 = ApplicationAnswer(
        id=uuid.uuid4(), application_id=application.id,
        question="Why do you want this role?",
        answer="Because I love data engineering.",
    )
    a2 = ApplicationAnswer(
        id=uuid.uuid4(), application_id=application.id,
        question="What is your biggest strength?",
        answer="Problem-solving.",
    )
    db_session.add(a1)
    db_session.add(a2)
    await db_session.commit()
    return [a1, a2]


@pytest_asyncio.fixture
async def authed_client(db_session, user_and_candidate):
    user, _ = user_and_candidate

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Tests — GET /answers ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_answers_returns_all(authed_client, application, answers):
    resp = await authed_client.get(f"/api/v2/applications/{application.id}/agent/answers")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 2
    questions = {item["question"] for item in data}
    assert "Why do you want this role?" in questions
    assert "What is your biggest strength?" in questions


@pytest.mark.asyncio
async def test_list_answers_empty_when_none(authed_client, application):
    resp = await authed_client.get(f"/api/v2/applications/{application.id}/agent/answers")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_answers_404_unknown_application(authed_client):
    resp = await authed_client.get(f"/api/v2/applications/{uuid.uuid4()}/agent/answers")
    assert resp.status_code == 404


# ── Tests — PATCH /answers/{answer_id} ───────────────────────────────────────

@pytest.mark.asyncio
async def test_update_answer_success(authed_client, application, answers, db_session):
    target = answers[0]
    resp = await authed_client.patch(
        f"/api/v2/applications/{application.id}/agent/answers/{target.id}",
        json={"answer": "I love Python and distributed systems."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["answer"] == "I love Python and distributed systems."
    assert data["question"] == target.question

    # Verify persisted
    await db_session.refresh(target)
    assert target.answer == "I love Python and distributed systems."


@pytest.mark.asyncio
async def test_update_answer_404_wrong_id(authed_client, application):
    resp = await authed_client.patch(
        f"/api/v2/applications/{application.id}/agent/answers/{uuid.uuid4()}",
        json={"answer": "new answer"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_answer_404_wrong_application(authed_client, answers):
    target = answers[0]
    resp = await authed_client.patch(
        f"/api/v2/applications/{uuid.uuid4()}/agent/answers/{target.id}",
        json={"answer": "new answer"},
    )
    assert resp.status_code == 404
