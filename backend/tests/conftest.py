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
def mock_match_agent():
    """Mock the match agent LLM call; deterministic engine still runs for real."""
    from app.services.agents.match_agent import LLMMatchResult
    sample = LLMMatchResult(
        score=0.80,
        reasoning="Strong Python and data engineering background aligns well with requirements.",
        strengths=["Python expertise", "Data pipeline experience"],
        gaps=["No explicit Spark experience listed"],
        recommendation="apply_with_tailoring",
    )
    with patch("app.api.routes.match.reason_about_match", new_callable=AsyncMock) as mock:
        mock.return_value = sample
        yield mock


@pytest.fixture
def mock_application_agents():
    """Mock all three application generation agents (strategy, CV, communication)."""
    from app.services.agents.application_agent import ApplicationStrategy, CVChangeGuidance
    from app.services.agents.cv_agent import PersonalizedCV, CVChange
    from app.services.agents.communication_agent import CoverLetterResult, AnswerResult

    strategy = ApplicationStrategy(
        overall_approach="Position as a strong Python data engineer with pipeline experience.",
        cv_changes=[
            CVChangeGuidance(
                section="summary",
                action="rewrite",
                rationale="Emphasize data pipeline experience",
                specific_guidance="Lead with pipeline expertise and Python skills",
            )
        ],
        cover_letter_key_points=["Python expertise", "Data pipeline experience"],
        strengths_to_emphasize=["Python", "SQL", "data pipelines"],
        risks_to_address=["Limited Spark experience"],
        recommendation="apply_with_tailoring",
    )

    cv_result = PersonalizedCV(
        summary_adapted="Experienced Senior Data Engineer with 5+ years building Python data pipelines.",
        headline_adapted="Senior Data Engineer | Python | dbt | Kafka",
        skills_ordered=["Python", "SQL", "dbt", "Kafka"],
        ats_keywords_added=["data pipeline", "data infrastructure"],
        changes=[
            CVChange(
                section="summary",
                original="Experienced data professional",
                adapted="Experienced Senior Data Engineer with 5+ years building Python data pipelines.",
                rationale="Aligns with JD seniority and Python requirements",
                evidence_ref="5+ years Python experience",
            )
        ],
        evidence_refs=["Python experience", "SQL experience"],
    )

    cover_letter = CoverLetterResult(
        content="Dear Hiring Manager,\n\nI am applying for the Senior Data Engineer role at TechCorp...",
        key_points_addressed=["Python expertise", "Data pipeline experience"],
        evidence_refs=["Python experience"],
    )

    answers = [
        AnswerResult(
            question="Why do you want to work at TechCorp?",
            answer="TechCorp's focus on large-scale data infrastructure aligns with my 5+ years building...",
            evidence_refs=["Data engineering experience"],
        )
    ]

    with patch("app.api.routes.applications.generate_strategy", new_callable=AsyncMock) as s_mock, \
         patch("app.api.routes.applications.personalize_cv", new_callable=AsyncMock) as cv_mock, \
         patch("app.api.routes.applications.generate_cover_letter", new_callable=AsyncMock) as cl_mock, \
         patch("app.api.routes.applications.generate_application_answers", new_callable=AsyncMock) as ans_mock:
        s_mock.return_value = strategy
        cv_mock.return_value = cv_result
        cl_mock.return_value = cover_letter
        ans_mock.return_value = answers
        yield {
            "strategy": s_mock,
            "cv": cv_mock,
            "cover_letter": cl_mock,
            "answers": ans_mock,
        }


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


@pytest.fixture
def mock_interview_agent():
    """Mock the interview prep agent."""
    from app.services.agents.interview_agent import (
        InterviewPrepResult, TechnicalQuestion, BehavioralQuestion, STARStory
    )
    result = InterviewPrepResult(
        technical_questions=[
            TechnicalQuestion(question="Explain your data pipeline architecture.", rationale="Core JD requirement"),
            TechnicalQuestion(question="How do you handle data quality in dbt?", rationale="dbt mentioned in JD"),
            TechnicalQuestion(question="Describe your Kafka experience.", rationale="Kafka required"),
            TechnicalQuestion(question="How do you optimize Spark jobs?", rationale="Spark required"),
            TechnicalQuestion(question="Explain SQL window functions.", rationale="SQL proficiency"),
        ],
        behavioral_questions=[
            BehavioralQuestion(question="Tell me about a time you led a data migration.", competency="leadership"),
            BehavioralQuestion(question="Describe a complex technical problem you solved.", competency="problem_solving"),
            BehavioralQuestion(question="How do you handle ambiguous requirements?", competency="adaptability"),
            BehavioralQuestion(question="Tell me about a failed project.", competency="resilience"),
            BehavioralQuestion(question="How do you collaborate with data scientists?", competency="collaboration"),
        ],
        star_stories=[
            STARStory(
                competency="technical_leadership",
                situation="Our team needed to migrate a 10TB data warehouse.",
                task="I was responsible for designing the migration strategy.",
                action="I designed a phased migration with zero downtime.",
                result="Successfully migrated with 99.9% data integrity.",
            ),
            STARStory(
                competency="problem_solving",
                situation="Pipeline failures were causing data quality issues.",
                task="Diagnose and fix the root cause.",
                action="Implemented comprehensive monitoring and alerting.",
                result="Reduced pipeline failures by 85%.",
            ),
            STARStory(
                competency="collaboration",
                situation="Cross-team project with conflicting priorities.",
                task="Align stakeholders on a shared approach.",
                action="Facilitated workshops and created shared documentation.",
                result="Delivered project on time with all stakeholders satisfied.",
            ),
        ],
        questions_to_ask=[
            "What does the data team's typical sprint look like?",
            "What are the biggest data quality challenges you face?",
            "How do you measure success for this role?",
            "What is the team's approach to technical debt?",
            "What opportunities exist for growth?",
        ],
        company_research={
            "culture": "Data-driven, collaborative engineering culture.",
            "mission": "Empowering businesses through data insights.",
            "values": "Innovation, integrity, and continuous improvement.",
        },
    )
    with patch("app.api.routes.interview.generate_interview_prep", new_callable=AsyncMock) as mock:
        mock.return_value = result
        yield mock


REMOTIVE_SAMPLE = {
    "jobs": [
        {
            "id": 101,
            "title": "Senior Data Engineer",
            "company_name": "TechCorp",
            "candidate_required_location": "Worldwide",
            "job_type": "full_time",
            "url": "https://remotive.com/remote-jobs/data/101",
            "description": "Python SQL data pipelines dbt kafka spark",
            "tags": [{"name": "python"}, {"name": "sql"}, {"name": "dbt"}],
            "salary": "$120k-$150k",
            "publication_date": "2026-08-01",
        },
        {
            "id": 102,
            "title": "Frontend React Developer",
            "company_name": "WebCo",
            "candidate_required_location": "USA",
            "job_type": "full_time",
            "url": "https://remotive.com/remote-jobs/frontend/102",
            "description": "React TypeScript CSS",
            "tags": [{"name": "react"}, {"name": "typescript"}],
            "salary": None,
            "publication_date": "2026-08-02",
        },
    ]
}


@pytest.fixture
def mock_remotive():
    """Mock RemotiveSource.fetch to avoid real HTTP calls in tests."""
    from app.services.job_sources.base import JobRaw

    jobs = [
        JobRaw(
            external_id="101",
            title="Senior Data Engineer",
            company="TechCorp",
            location="Worldwide",
            remote_type="remote",
            url="https://remotive.com/remote-jobs/data/101",
            description="Python SQL data pipelines dbt kafka spark",
            tech_tags=["python", "sql", "dbt"],
            salary_range="$120k-$150k",
            published_at="2026-08-01",
        ),
        JobRaw(
            external_id="102",
            title="Frontend React Developer",
            company="WebCo",
            location="USA",
            remote_type="remote",
            url="https://remotive.com/remote-jobs/frontend/102",
            description="React TypeScript CSS",
            tech_tags=["react", "typescript"],
            salary_range=None,
            published_at="2026-08-02",
        ),
    ]
    with patch(
        "app.api.routes.recommendations.RemotiveSource.fetch",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = jobs
        yield mock
