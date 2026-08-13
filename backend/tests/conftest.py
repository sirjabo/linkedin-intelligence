"""Shared fixtures for pytest.

Key design principles:
- LLM calls are always mocked — no real API calls in tests.
- DB uses an in-memory SQLite via aiosqlite for fast, isolated tests.
- Each test gets a fresh DB schema.
"""
import asyncio
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.services.ai.provider import LLMProvider
from app.services.agents.profile_agent import ExtractedProfile

# In-memory SQLite for tests (no Postgres needed)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_profile_agent():
    """Mock the profile agent to return predictable data without LLM calls."""
    sample = ExtractedProfile(
        name="Test User",
        email="test@example.com",
        location="Buenos Aires, Argentina",
        summary="Experienced data professional",
        career_level="senior",
        skills=[],
        experience=[],
        education=[],
        extraction_confidence=0.9,
    )
    with patch("app.api.routes.candidates.extract_from_source", new_callable=AsyncMock) as mock:
        mock.return_value = sample
        with patch("app.api.routes.candidates.consolidate_profiles", new_callable=AsyncMock) as mock2:
            from app.services.agents.profile_agent import ConsolidatedProfile
            mock2.return_value = ConsolidatedProfile(
                summary="Experienced data professional",
                career_level="senior",
                professional_identity={"name": "Test User", "email": "test@example.com"},
            )
            yield mock


@pytest.fixture
def mock_job_agent():
    """Mock the job agent to return predictable data without LLM calls."""
    from app.services.agents.job_agent import ParsedJob, RequirementItem
    sample = ParsedJob(
        title="Senior Data Engineer",
        company="TechCorp",
        location="Buenos Aires, Argentina",
        remote_type="hybrid",
        seniority="senior",
        employment_type="full-time",
        tech_stack=["Python", "Spark", "dbt", "Kafka"],
        requirements=[
            RequirementItem(
                description="5+ years of data engineering experience",
                requirement_type="must_have",
                category="experience",
                is_required=True,
                seniority_signal="5+ years",
            ),
            RequirementItem(
                description="Strong Python and SQL skills",
                requirement_type="must_have",
                category="technical",
                is_required=True,
            ),
        ],
        key_responsibilities=["Design and build data pipelines", "Maintain data warehouse"],
        company_description="TechCorp is a leading data company",
        parsing_confidence=0.9,
    )
    with patch("app.api.routes.jobs.parse_job_description", new_callable=AsyncMock) as mock:
        mock.return_value = sample
        yield mock
