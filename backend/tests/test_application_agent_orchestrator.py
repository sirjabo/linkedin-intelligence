"""Integration tests for ApplicationAgentOrchestrator with Mock ATS.

AC-02 / AC-07 / AC-10 / AC-12: orchestrator.start() → resume() → submit()
Uses real SQLite in-memory DB + real Playwright + mock ATS server.
"""
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.base import Base
from app.db.models import (
    User, Candidate, CandidateProfile, Application,
    ApplicationForm, ApplicationFormField,
)
from app.db.models.agent_session import ApplicationAgentSession
from app.db.models.job import Job
from app.services.application_agent_orchestrator import ApplicationAgentOrchestrator, AgentError

from tests.mock_ats.conftest_ats import mock_ats_url  # noqa: F401

# ── Skip if no Chromium ───────────────────────────────────────────────────────
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
async def test_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"agent_test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def candidate_with_profile(db, test_user):
    candidate = Candidate(
        id=uuid.uuid4(),
        user_id=test_user.id,
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
        experience=[
            {"company": "BigCo", "role": "Senior Data Engineer", "start_date": "01/2021", "end_date": "Present", "duration_years": 3, "bullets": ["Led Spark pipeline redesign"]},
            {"company": "MidCo", "role": "Data Engineer", "start_date": "06/2018", "end_date": "12/2020", "duration_years": 2.5, "bullets": []},
            {"company": "StartupX", "role": "Junior DE", "start_date": "01/2017", "end_date": "05/2018", "duration_years": 1.5, "bullets": []},
        ],
        education=[
            {"degree": "Bachelor", "field": "Computer Science", "institution": "UBA", "year": "2016", "gpa": None},
        ],
        skills=["Python", "Spark", "Airflow", "PostgreSQL", "dbt", "AWS"],
    )
    db.add(profile)
    await db.commit()
    return candidate, profile


@pytest.fixture
async def application(db, candidate_with_profile):
    candidate, _ = candidate_with_profile

    job = Job(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        title="Senior Data Engineer",
        company="Mock Company",
        raw_jd="Build data pipelines",
        location="Buenos Aires (Hybrid)",
        job_url="http://localhost/job/1",
        status="analyzed",
    )
    db.add(job)
    await db.flush()

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

class TestOrchestratorStart:
    @pytest.mark.asyncio
    async def test_start_creates_session(self, mock_ats_url, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        session = await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )

        assert session.id is not None
        assert session.application_id == application.id
        assert session.status in ("awaiting_human", "ready_to_fill")
        assert session.ats_name == "generic"
        assert session.fields_total >= 12

    @pytest.mark.asyncio
    async def test_start_creates_form_fields(self, mock_ats_url, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )

        form_result = await db.execute(
            select(ApplicationForm)
            .options(selectinload(ApplicationForm.fields))
            .where(ApplicationForm.application_id == application.id)
        )
        form = form_result.scalar_one_or_none()
        assert form is not None
        assert len(form.fields) >= 12

    @pytest.mark.asyncio
    async def test_start_auto_fills_known_fields(self, mock_ats_url, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        session = await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )

        assert session.fields_auto_filled > 0, "Should auto-fill at least some fields"
        assert session.fields_auto_filled >= 4, "Should auto-fill name, email, location, salary at minimum"

    @pytest.mark.asyncio
    async def test_start_marks_phone_human_required(self, mock_ats_url, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )

        form_result = await db.execute(
            select(ApplicationForm).where(ApplicationForm.application_id == application.id)
        )
        form = form_result.scalar_one()
        await db.refresh(form)

        # Need to load fields separately since the form was already retrieved
        fields_result = await db.execute(
            select(ApplicationFormField).where(ApplicationFormField.form_id == form.id)
        )
        fields = fields_result.scalars().all()

        phone_fields = [f for f in fields if "phone" in f.label.lower()]
        assert phone_fields, "Phone field should exist"
        assert phone_fields[0].human_required is True, "Phone should be human_required"

    @pytest.mark.asyncio
    async def test_start_session_status_awaiting_human_when_unanswered(self, mock_ats_url, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        session = await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )
        # Mock ATS has phone (always human) + why_company (custom_essay) + resume (file)
        # So status should be awaiting_human
        assert session.status == "awaiting_human"
        assert session.fields_human_pending >= 1


class TestOrchestratorResume:
    @pytest.mark.asyncio
    async def test_resume_stays_awaiting_if_fields_unanswered(self, mock_ats_url, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        session = await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )
        assert session.status == "awaiting_human"

        resumed = await orchestrator.resume(session_id=session.id, db=db)
        assert resumed.status == "awaiting_human"
        assert resumed.fields_human_pending >= 1

    @pytest.mark.asyncio
    async def test_resume_advances_when_all_answered(self, mock_ats_url, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        session = await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )

        # Fill in all human-required fields
        form_result = await db.execute(
            select(ApplicationForm).where(ApplicationForm.application_id == application.id)
        )
        form = form_result.scalar_one()
        fields_result = await db.execute(
            select(ApplicationFormField).where(
                ApplicationFormField.form_id == form.id,
                ApplicationFormField.human_required.is_(True),
            )
        )
        human_fields = fields_result.scalars().all()

        for field in human_fields:
            if field.semantic_type == "phone":
                field.human_answer = "+1-555-123-4567"
            elif field.semantic_type == "cv_file":
                field.human_answer = "/tmp/test_cv.txt"
            else:
                field.human_answer = "I am passionate about data engineering and your company's mission."
        await db.commit()

        resumed = await orchestrator.resume(session_id=session.id, db=db)
        assert resumed.status == "ready_to_fill"


class TestOrchestratorSubmit:
    @pytest.mark.asyncio
    async def test_submit_requires_human_confirmed(self, application, db):
        orchestrator = ApplicationAgentOrchestrator()
        fake_session_id = uuid.uuid4()

        with pytest.raises(AgentError, match="human_confirmed"):
            await orchestrator.submit(
                session_id=fake_session_id,
                human_confirmed=False,
                db=db,
            )

    @pytest.mark.asyncio
    async def test_full_e2e_with_mock_ats(self, mock_ats_url, application, db):
        """AC-10 golden E2E: start → answer human fields → submit → APP- reference."""
        orchestrator = ApplicationAgentOrchestrator()

        # Start
        session = await orchestrator.start(
            application_id=application.id,
            form_url=f"{mock_ats_url}/apply",
            db=db,
        )
        assert session.status == "awaiting_human"

        # Answer all human-required fields
        form_result = await db.execute(
            select(ApplicationForm).where(ApplicationForm.application_id == application.id)
        )
        form = form_result.scalar_one()
        fields_result = await db.execute(
            select(ApplicationFormField).where(
                ApplicationFormField.form_id == form.id,
                ApplicationFormField.human_required.is_(True),
            )
        )
        human_fields = fields_result.scalars().all()

        # Create a real temp CV file
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w")
        tmp.write("Jane Doe\nSenior Data Engineer\n")
        tmp.close()
        cv_path = tmp.name

        for field in human_fields:
            if field.semantic_type == "phone":
                field.human_answer = "+1-555-000-9999"
            elif field.semantic_type == "cv_file":
                field.human_answer = cv_path
            else:
                field.human_answer = "I love data engineering and building reliable pipelines."
        await db.commit()

        # Resume → ready_to_fill
        session = await orchestrator.resume(session_id=session.id, db=db)
        assert session.status == "ready_to_fill"

        # Submit
        session = await orchestrator.submit(
            session_id=session.id,
            human_confirmed=True,
            db=db,
        )

        os.unlink(cv_path)

        assert session.status == "submitted"
        assert session.confirmation_id is not None
        assert "APP" in session.confirmation_id.upper()

        # Application status updated
        await db.refresh(application)
        assert application.status == "applied"
        assert application.applied_at is not None
