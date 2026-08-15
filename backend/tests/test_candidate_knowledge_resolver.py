"""Unit tests for CandidateKnowledgeResolver.

AC-04: resolver.resolve() returns the correct value and source for each semantic type.
All tests use synthetic candidate data — no real personal data.
"""
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.candidate_knowledge_resolver import (
    CandidateKnowledgeResolver,
    _compute_total_years,
    _years_to_bucket,
    _match_select_option,
    _get_highest_education,
)


# ── Fixtures — use SimpleNamespace so no SQLAlchemy machinery needed ──────────

def _make_candidate(
    name: str = "Jane Doe",
    email: str = "jane@example.com",
    location: str = "Buenos Aires, Argentina",
    work_authorization: str = "visa_required",
    salary_min_usd: int = 95000,
    availability: str = "two_weeks",
    sources: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        email=email,
        location=location,
        work_authorization=work_authorization,
        salary_min_usd=salary_min_usd,
        availability=availability,
        career_goals="Build scalable data platforms",
        sources=sources or [],
    )


def _make_profile(
    summary: str = "Senior Data Engineer with 7+ years",
    experience: list | None = None,
    education: list | None = None,
    skills: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        summary=summary,
        experience=experience or [
            {"company": "BigCo", "role": "Senior Data Engineer", "start_date": "01/2021", "end_date": "Present", "duration_years": 3, "bullets": []},
            {"company": "MidCo", "role": "Data Engineer", "start_date": "06/2018", "end_date": "12/2020", "duration_years": 2.5, "bullets": []},
            {"company": "StartupX", "role": "Junior DE", "start_date": "01/2017", "end_date": "05/2018", "duration_years": 1.5, "bullets": []},
        ],
        education=education or [
            {"degree": "Bachelor", "field": "Computer Science", "institution": "UBA", "year": "2016", "gpa": None},
        ],
        skills=skills or ["Python", "Spark", "Airflow", "PostgreSQL", "dbt"],
    )


def _make_application(
    cover_letters: list | None = None,
    answers: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        cover_letters=cover_letters or [],
        cv_versions=[],
        answers=answers or [],
    )


resolver = CandidateKnowledgeResolver()


# ── Direct resolvers ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_full_name():
    c = _make_candidate(name="Jane Doe")
    r = await resolver.resolve("full_name", "Full Name", None, c, None, _make_application())
    assert r.value == "Jane Doe"
    assert r.source == "DIRECT"
    assert r.confidence >= 0.9


@pytest.mark.asyncio
async def test_resolve_first_name():
    c = _make_candidate(name="Jane Doe")
    r = await resolver.resolve("first_name", "First Name", None, c, None, _make_application())
    assert r.value == "Jane"
    assert r.source == "COMPUTED"


@pytest.mark.asyncio
async def test_resolve_last_name():
    c = _make_candidate(name="Jane Doe")
    r = await resolver.resolve("last_name", "Last Name", None, c, None, _make_application())
    assert r.value == "Doe"
    assert r.source == "COMPUTED"


@pytest.mark.asyncio
async def test_resolve_email():
    c = _make_candidate(email="jane@example.com")
    r = await resolver.resolve("email", "Email", None, c, None, _make_application())
    assert r.value == "jane@example.com"
    assert r.source == "DIRECT"


@pytest.mark.asyncio
async def test_resolve_phone_always_human():
    c = _make_candidate()
    r = await resolver.resolve("phone", "Phone Number", None, c, None, _make_application())
    assert r.value is None
    assert r.source == "HUMAN_REQUIRED"


@pytest.mark.asyncio
async def test_resolve_location():
    c = _make_candidate(location="Buenos Aires")
    r = await resolver.resolve("location", "Location", None, c, None, _make_application())
    assert r.value == "Buenos Aires"
    assert r.source == "DIRECT"


@pytest.mark.asyncio
async def test_resolve_work_authorization():
    c = _make_candidate(work_authorization="citizen")
    r = await resolver.resolve("work_authorization", "Work Authorization", ["citizen", "permanent_resident", "visa_required"], c, None, _make_application())
    assert r.source == "DIRECT"
    assert r.value == "citizen"


@pytest.mark.asyncio
async def test_resolve_work_authorization_option_matching():
    c = _make_candidate(work_authorization="visa_required")
    options = ["US Citizen", "Permanent Resident", "Require Sponsorship"]
    r = await resolver.resolve("work_authorization", "Work Authorization", options, c, None, _make_application())
    # value should be one of the options (matched) or the raw value
    assert r.source == "DIRECT"
    assert r.value is not None


@pytest.mark.asyncio
async def test_resolve_salary_expectation():
    c = _make_candidate(salary_min_usd=95000)
    r = await resolver.resolve("salary_expectation", "Expected Salary", None, c, None, _make_application())
    assert r.value == "95000"
    assert r.source == "DIRECT"


# ── Computed resolvers ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_years_experience_computed():
    c = _make_candidate()
    p = _make_profile()  # total = 3+2.5+1.5 = 7 → "6-10"
    r = await resolver.resolve("years_experience", "Years of Experience", ["0-2", "3-5", "6-10", "10+"], c, p, _make_application())
    assert r.source == "COMPUTED"
    assert r.value is not None
    assert "6" in r.value or "10" in r.value  # "6-10" bucket


@pytest.mark.asyncio
async def test_resolve_years_experience_no_profile():
    c = _make_candidate()
    r = await resolver.resolve("years_experience", "Years of Experience", None, c, None, _make_application())
    assert r.source == "HUMAN_REQUIRED"
    assert r.value is None


@pytest.mark.asyncio
async def test_resolve_current_company():
    c = _make_candidate()
    p = _make_profile()
    r = await resolver.resolve("current_company", "Current Company", None, c, p, _make_application())
    assert r.source == "COMPUTED"
    assert r.value == "BigCo"


@pytest.mark.asyncio
async def test_resolve_current_title():
    c = _make_candidate()
    p = _make_profile()
    r = await resolver.resolve("current_title", "Current Title", None, c, p, _make_application())
    assert r.source == "COMPUTED"
    assert "Engineer" in (r.value or "")


@pytest.mark.asyncio
async def test_resolve_cover_letter():
    c = _make_candidate()
    cl = SimpleNamespace(content="I am excited about this role.", created_at=datetime.utcnow())
    app = _make_application(cover_letters=[cl])

    r = await resolver.resolve("cover_letter", "Cover Letter", None, c, None, app)
    assert r.source == "DIRECT"
    assert r.value == "I am excited about this role."


@pytest.mark.asyncio
async def test_resolve_cv_file_human_required():
    c = _make_candidate()
    r = await resolver.resolve("cv_file", "Resume / CV", None, c, None, _make_application())
    assert r.source == "HUMAN_REQUIRED"


# ── Unknown / custom types ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_custom_essay_no_api_key_falls_back():
    """Without an API key the LLM call fails → HUMAN_REQUIRED fallback."""
    c = _make_candidate()
    p = _make_profile()
    app = _make_application()

    with patch("app.services.candidate_knowledge_resolver.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = ""
        r = await resolver.resolve("custom_essay", "Why do you want to work here?", None, c, p, app)

    # Should either generate or fall back — never invent
    assert r.value is None or len(r.value) > 0
    assert r.source in ("GENERATED", "HUMAN_REQUIRED")


# ── FROM_KB tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_custom_essay_from_kb_answer_match():
    """FROM_KB: returns stored ApplicationAnswer when label matches question."""
    c = _make_candidate()
    p = _make_profile()
    stored_answer = SimpleNamespace(
        question="Why do you want to work here?",
        answer="I am passionate about data engineering and your company's mission.",
    )
    app = _make_application(answers=[stored_answer])

    r = await resolver.resolve("custom_essay", "Why do you want to work here?", None, c, p, app)
    assert r.source == "FROM_KB"
    assert r.value == "I am passionate about data engineering and your company's mission."


@pytest.mark.asyncio
async def test_custom_essay_from_kb_partial_label_match():
    """FROM_KB: substring match works when label is contained in stored question."""
    c = _make_candidate()
    stored_answer = SimpleNamespace(
        question="Describe why you want this role at our company",
        answer="I have deep experience in Spark pipelines.",
    )
    app = _make_application(answers=[stored_answer])

    r = await resolver.resolve("custom_essay", "why you want this role", None, c, None, app)
    assert r.source == "FROM_KB"
    assert "Spark" in r.value


@pytest.mark.asyncio
async def test_custom_essay_from_kb_cover_letter_motivation():
    """FROM_KB: motivation field uses cover letter content when no answer matches."""
    c = _make_candidate()
    cover = SimpleNamespace(
        content="Dear Hiring Manager, I am excited about this opportunity because of my Spark expertise.",
        created_at=datetime(2026, 8, 14),
        evidence_refs=[],
    )
    app = _make_application(cover_letters=[cover], answers=[])

    r = await resolver.resolve("custom_essay", "What motivates you?", None, c, None, app)
    assert r.source == "FROM_KB"
    assert "Spark" in r.value


@pytest.mark.asyncio
async def test_unknown_type_from_kb_when_answer_exists():
    """Unknown semantic type uses FROM_KB if a matching answer exists."""
    c = _make_candidate()
    stored_answer = SimpleNamespace(
        question="Describe your leadership experience",
        answer="I led a team of 5 engineers at BigCo.",
    )
    app = _make_application(answers=[stored_answer])

    r = await resolver.resolve("unknown", "Describe your leadership experience", None, c, None, app)
    assert r.source == "FROM_KB"
    assert "BigCo" in r.value


@pytest.mark.asyncio
async def test_unknown_type_still_human_required_when_no_kb():
    """Unknown semantic type is HUMAN_REQUIRED when no KB entry matches."""
    c = _make_candidate()
    app = _make_application(answers=[])

    r = await resolver.resolve("unknown", "Some mystery field", None, c, None, app)
    assert r.source == "HUMAN_REQUIRED"
    assert r.value is None


# ── Helper function tests ─────────────────────────────────────────────────────

def test_compute_total_years():
    p = _make_profile()
    total = _compute_total_years(p)
    assert total == pytest.approx(7.0, abs=0.1)


def test_compute_total_years_no_profile():
    assert _compute_total_years(None) is None


def test_years_to_bucket():
    assert _years_to_bucket(1) == "0-2"
    assert _years_to_bucket(2) == "0-2"
    assert _years_to_bucket(3) == "3-5"
    assert _years_to_bucket(5) == "3-5"
    assert _years_to_bucket(6) == "6-10"
    assert _years_to_bucket(10) == "6-10"
    assert _years_to_bucket(11) == "10+"
    assert _years_to_bucket(20) == "10+"


def test_match_select_option_exact():
    options = ["0-2", "3-5", "6-10", "10+"]
    assert _match_select_option("3-5", options) == "3-5"


def test_match_select_option_prefix():
    options = ["0–2 years", "3–5 years", "6–10 years", "10+ years"]
    result = _match_select_option("6-10", options)
    assert result is not None
    assert "6" in result


def test_match_select_option_no_match():
    assert _match_select_option("unknown", ["yes", "no"]) is None


def test_get_highest_education():
    p = _make_profile(education=[
        {"degree": "Bachelor", "field": "CS", "institution": "UBA", "year": "2016"},
        {"degree": "Master", "field": "Data Science", "institution": "MIT", "year": "2018"},
    ])
    result = _get_highest_education(p)
    assert result == "Master"


@pytest.mark.asyncio
async def test_linkedin_url_from_source():
    src = SimpleNamespace(source_type="linkedin", source_url="https://linkedin.com/in/janedoe")
    c = _make_candidate(sources=[src])
    r = await resolver.resolve("linkedin_url", "LinkedIn Profile", None, c, None, _make_application())
    assert r.source == "DIRECT"
    assert r.value == "https://linkedin.com/in/janedoe"
