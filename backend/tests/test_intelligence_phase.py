"""Integration tests for orchestrator intelligence phase (P0 Phase 1).

Verifies that orchestrator.start() with a mock LLMProvider populates:
- Application.strategy
- CVVersion row with adapted content
- CoverLetter row with generated content

Uses real SQLite in-memory DB + real Playwright + mock ATS server.
"""
import uuid
import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.base import Base
from app.db.models import (
    User, Candidate, CandidateProfile, Application,
)
from app.db.models.application import CVVersion, CoverLetter
from app.db.models.job import Job, JobRequirement
from app.services.application_agent_orchestrator import ApplicationAgentOrchestrator
from app.services.agents.match_agent import LLMMatchResult
from app.services.agents.application_agent import ApplicationStrategy, CVChangeGuidance
from app.services.agents.cv_agent import PersonalizedCV, CVChange
from app.services.agents.communication_agent import CoverLetterResult

from tests.mock_ats.conftest_ats import mock_ats_url  # noqa: F401

import os
_CHROMIUM_CANDIDATES = [
    "/opt/pw-browsers/chromium/chrome",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
]
pytestmark = pytest.mark.skipif(
    not any(os.path.isfile(p) for p in _CHROMIUM_CANDIDATES),
    reason="No pre-installed Chromium",
)


# ── MockLLMProvider ───────────────────────────────────────────────────────────

class MockLLMProvider:
    """Returns pre-built fixture instances keyed by schema class name."""

    _FIXTURES: dict[str, BaseModel] = {
        "LLMMatchResult": LLMMatchResult(
            score=0.80,
            reasoning="Strong Python and Spark background aligns well with data pipeline role.",
            strengths=["Python", "Spark", "7 years experience"],
            gaps=["Kafka not mentioned"],
            recommendation="apply_with_tailoring",
        ),
        "ApplicationStrategy": ApplicationStrategy(
            overall_approach=(
                "Emphasize proven Spark pipeline experience at BigCo and AWS fluency. "
                "Cover letter should address the Kafka gap proactively."
            ),
            cv_changes=[
                CVChangeGuidance(
                    section="summary",
                    action="rewrite",
                    rationale="Lead with data pipeline scale to match JD emphasis",
                    specific_guidance=(
                        "Rewrite to: '7-year Data Engineer specializing in PB-scale Spark pipelines.'"
                    ),
                ),
            ],
            cover_letter_key_points=["Spark pipeline redesign at BigCo", "AWS cost reduction"],
            strengths_to_emphasize=["Python", "Spark", "Airflow"],
            risks_to_address=["Kafka experience limited"],
            recommendation="apply_with_tailoring",
        ),
        "PersonalizedCV": PersonalizedCV(
            summary_adapted=(
                "Senior Data Engineer with 7 years building PB-scale Spark pipelines on AWS, "
                "specializing in Airflow orchestration and dbt transformations."
            ),
            headline_adapted="Senior Data Engineer | Spark · Airflow · AWS",
            skills_ordered=["Python", "Spark", "Airflow", "dbt", "AWS", "PostgreSQL"],
            ats_keywords_added=["Apache Spark", "data pipeline", "ETL"],
            changes=[
                CVChange(
                    section="summary",
                    original="Senior Data Engineer with 7 years of experience in Python and Spark.",
                    adapted=(
                        "Senior Data Engineer with 7 years building PB-scale Spark pipelines on AWS, "
                        "specializing in Airflow orchestration and dbt transformations."
                    ),
                    reason="Incorporates JD keywords and quantifies scale",
                    evidence_refs=["BigCo Spark pipeline redesign"],
                ),
            ],
            evidence_refs=["BigCo Spark pipeline redesign (2021-Present)"],
        ),
        "CoverLetterResult": CoverLetterResult(
            content=(
                "Dear Hiring Manager,\n\n"
                "I am writing to apply for the Senior Data Engineer role at Mock Company. "
                "Over the past 7 years I have built and maintained large-scale Spark pipelines "
                "that process terabytes of data daily, most recently at BigCo where I led the "
                "redesign of our core pipeline infrastructure.\n\n"
                "My proficiency in Python, Airflow, and dbt maps directly to the stack described "
                "in your job description. I am confident in delivering reliable, maintainable "
                "data systems at scale.\n\n"
                "Thank you for your consideration.\n\nJane Doe"
            ),
            key_points_addressed=["Spark pipeline redesign at BigCo", "AWS cost reduction"],
            evidence_refs=["BigCo Senior Data Engineer 2021-Present"],
        ),
    }

    async def generate(self, system: str, messages: list, model: str, max_tokens: int = 4096) -> str:
        return "Mock generate response"

    async def structured_output(
        self,
        system: str,
        messages: list,
        schema: type[BaseModel],
        model: str,
        max_tokens: int = 4096,
    ) -> BaseModel:
        fixture = self._FIXTURES.get(schema.__name__)
        if fixture is None:
            raise ValueError(f"MockLLMProvider has no fixture for schema {schema.__name__!r}")
        return fixture

    async def stream(self, system: str, messages: list, model: str, max_tokens: int = 4096):
        yield "Mock stream"


# ── DB fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest.fixture
async def candidate_with_profile(db):
    user = User(
        id=uuid.uuid4(),
        email=f"intel_test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    candidate = Candidate(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Jane Doe",
        email="jane@example.com",
        location="Buenos Aires, Argentina",
        work_authorization="visa_required",
        salary_min_usd=95000,
        availability="two_weeks",
        career_goals="Build scalable data pipelines",
    )
    db.add(candidate)
    await db.flush()

    profile = CandidateProfile(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        summary="Senior Data Engineer with 7 years of experience in Python and Spark.",
        career_level="senior",
        experience=[
            {
                "company": "BigCo",
                "role": "Senior Data Engineer",
                "start_date": "01/2021",
                "end_date": "Present",
                "duration_years": 3,
                "bullets": ["Led Spark pipeline redesign"],
            },
        ],
        education=[
            {"degree": "Bachelor", "field": "Computer Science", "institution": "UBA", "year": "2016"},
        ],
        skills=["Python", "Spark", "Airflow", "PostgreSQL", "dbt", "AWS"],
    )
    db.add(profile)
    await db.commit()
    return candidate, profile


@pytest.fixture
async def application_with_job(db, candidate_with_profile):
    candidate, _ = candidate_with_profile

    job = Job(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        title="Senior Data Engineer",
        company="Mock Company",
        raw_jd="Build and maintain large-scale data pipelines using Spark and Python.",
        location="Buenos Aires (Hybrid)",
        job_url="http://localhost/job/intel/1",
        status="analyzed",
        seniority="senior",
        tech_stack=["Python", "Spark", "Airflow", "Kafka", "AWS"],
    )
    db.add(job)
    await db.flush()

    req_must = JobRequirement(
        id=uuid.uuid4(),
        job_id=job.id,
        description="5+ years Python data engineering",
        requirement_type="must_have",
        category="experience",
    )
    req_nice = JobRequirement(
        id=uuid.uuid4(),
        job_id=job.id,
        description="Kafka experience",
        requirement_type="nice_to_have",
        category="technical",
    )
    db.add(req_must)
    db.add(req_nice)

    app = Application(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        job_id=job.id,
        status="draft",
    )
    db.add(app)
    await db.commit()
    return app


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestIntelligencePhase:
    @pytest.mark.asyncio
    async def test_start_populates_strategy_and_cv(
        self, mock_ats_url, application_with_job, db
    ):
        """Intelligence phase populates Application.strategy, CVVersion, and CoverLetter."""
        orchestrator = ApplicationAgentOrchestrator()
        session = await orchestrator.start(
            application_id=application_with_job.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
            intelligence_provider=MockLLMProvider(),
        )

        # Session should complete normally
        assert session.status in ("awaiting_human", "ready_to_fill")

        # Application.strategy should be populated
        await db.refresh(application_with_job)
        assert application_with_job.strategy is not None
        strategy = application_with_job.strategy
        assert "overall_approach" in strategy
        assert "cv_changes" in strategy
        assert "recommendation" in strategy

    @pytest.mark.asyncio
    async def test_start_creates_cv_version_row(
        self, mock_ats_url, application_with_job, db
    ):
        """CVVersion row is created with adapted content from cv_agent."""
        orchestrator = ApplicationAgentOrchestrator()
        await orchestrator.start(
            application_id=application_with_job.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
            intelligence_provider=MockLLMProvider(),
        )

        result = await db.execute(
            select(CVVersion).where(CVVersion.application_id == application_with_job.id)
        )
        cv_version = result.scalar_one_or_none()

        assert cv_version is not None
        assert cv_version.summary_adapted is not None
        assert "Spark" in cv_version.summary_adapted
        assert isinstance(cv_version.skills_ordered, list)
        assert "Python" in cv_version.skills_ordered
        assert isinstance(cv_version.changes, list)
        assert len(cv_version.changes) >= 1
        assert isinstance(cv_version.ats_keywords, list)

    @pytest.mark.asyncio
    async def test_start_creates_cover_letter_row(
        self, mock_ats_url, application_with_job, db
    ):
        """CoverLetter row is created with generated content from communication_agent."""
        orchestrator = ApplicationAgentOrchestrator()
        await orchestrator.start(
            application_id=application_with_job.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
            intelligence_provider=MockLLMProvider(),
        )

        result = await db.execute(
            select(CoverLetter).where(CoverLetter.application_id == application_with_job.id)
        )
        cover_letter = result.scalar_one_or_none()

        assert cover_letter is not None
        assert cover_letter.content is not None
        assert len(cover_letter.content) > 50
        assert isinstance(cover_letter.evidence_refs, list)

    @pytest.mark.asyncio
    async def test_intelligence_phase_graceful_on_no_job(
        self, mock_ats_url, db, candidate_with_profile
    ):
        """Orchestrator continues even when Job is missing (graceful degradation)."""
        candidate, _ = candidate_with_profile

        # Application with a non-existent job_id
        app = Application(
            id=uuid.uuid4(),
            candidate_id=candidate.id,
            job_id=uuid.uuid4(),  # doesn't exist in DB
            status="draft",
        )
        db.add(app)
        await db.commit()

        orchestrator = ApplicationAgentOrchestrator()
        # Should not raise — intelligence phase logs warning and returns
        session = await orchestrator.start(
            application_id=app.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
            intelligence_provider=MockLLMProvider(),
        )
        assert session.status in ("awaiting_human", "ready_to_fill")

        # No CVVersion or CoverLetter rows — gracefully skipped
        cv_result = await db.execute(
            select(CVVersion).where(CVVersion.application_id == app.id)
        )
        assert cv_result.scalar_one_or_none() is None
