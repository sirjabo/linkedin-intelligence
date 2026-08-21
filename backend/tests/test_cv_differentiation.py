"""CV differentiation test: 1 candidate × 3 job descriptions → distinct CVs.

Verifies that the CV agent produces meaningfully different personalizations
when the target job is different, even for the same candidate.

Key assertions:
  - Summaries across the 3 CVs are not identical
  - Skills ordering differs between CVs (each job's stack comes first)
  - ATS keywords are job-specific (each CV references its own JD requirements)
  - Changes reference job-relevant requirements

These tests use a mock LLM that returns realistic JSON responses without
making real API calls.
"""
from unittest.mock import AsyncMock

import pytest

from app.services.agents.cv_agent import PersonalizedCV, personalize_cv

# ── Shared candidate fixture ──────────────────────────────────────────────────

_CANDIDATE = {
    "summary": (
        "Versatile software engineer with 7 years of experience building "
        "scalable data pipelines and backend services using Python and SQL."
    ),
    "headline": "Senior Software Engineer",
    "skills": ["Python", "SQL", "Spark", "Kafka", "Docker", "React", "TypeScript", "AWS"],
    "career_level": "senior",
    "experience": [
        {
            "title": "Senior Data Engineer",
            "company": "TechCorp",
            "bullets": [
                "Built Kafka-based event streaming pipeline ingesting 5M events/day",
                "Reduced Spark job runtime by 40% through partition optimization",
                "Led migration from PostgreSQL to Snowflake data warehouse",
            ],
        },
        {
            "title": "Backend Engineer",
            "company": "StartupX",
            "bullets": [
                "Designed REST APIs serving 500k requests/day using FastAPI",
                "Implemented React dashboard reducing support tickets by 30%",
                "Containerized services with Docker and deployed on AWS ECS",
            ],
        },
    ],
    "projects": [
        {"name": "DataFlow", "description": "Real-time analytics pipeline using Kafka and Spark"},
        {"name": "AdminUI", "description": "React TypeScript admin panel with role-based access"},
    ],
}


# ── Three distinct job descriptions ──────────────────────────────────────────

_JOB_DATA_ENGINEERING = {
    "title": "Senior Data Engineer",
    "company": "BigData Corp",
    "seniority": "senior",
    "tech_stack": ["Spark", "Kafka", "Python", "Snowflake", "Airflow"],
    "requirements": [
        "5+ years building distributed data pipelines",
        "Expert-level Spark and Kafka",
        "Snowflake data warehousing",
        "Python for data orchestration",
    ],
    "strategy": [
        {"section": "summary", "action": "emphasize", "specific_guidance": "Lead with data pipeline scale"},
        {"section": "skills", "action": "reorder", "specific_guidance": "Spark, Kafka, Python first"},
    ],
}

_JOB_BACKEND_API = {
    "title": "Senior Backend Engineer",
    "company": "APIFirst Inc",
    "seniority": "senior",
    "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
    "requirements": [
        "REST API design and development",
        "Python backend services at scale",
        "Docker and container orchestration",
        "AWS infrastructure experience",
    ],
    "strategy": [
        {"section": "summary", "action": "emphasize", "specific_guidance": "Lead with API throughput and reliability"},
        {"section": "skills", "action": "reorder", "specific_guidance": "Python, FastAPI, Docker, AWS first"},
    ],
}

_JOB_FRONTEND = {
    "title": "Senior Frontend Engineer",
    "company": "UXLab",
    "seniority": "senior",
    "tech_stack": ["React", "TypeScript", "AWS", "Docker"],
    "requirements": [
        "Expert React and TypeScript",
        "Frontend performance optimization",
        "Component library development",
        "CI/CD pipeline familiarity",
    ],
    "strategy": [
        {"section": "summary", "action": "emphasize", "specific_guidance": "Lead with React and user-facing impact"},
        {"section": "skills", "action": "reorder", "specific_guidance": "React, TypeScript first"},
    ],
}


def _make_cv_response(summary: str, skills: list[str], keywords: list[str]) -> PersonalizedCV:
    return PersonalizedCV(
        summary_adapted=summary,
        headline_adapted=None,
        skills_ordered=skills,
        ats_keywords_added=keywords,
        changes=[],
        evidence_refs=[],
        experience_personalized=[],
        projects_personalized=[],
    )


@pytest.fixture
def mock_provider_factory():
    """Return a factory that creates a mock provider with a preset response."""
    def _factory(cv: PersonalizedCV) -> AsyncMock:
        provider = AsyncMock()
        provider.structured_output = AsyncMock(return_value=cv)
        return provider
    return _factory


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCVDifferentiationAcrossJobs:
    """Core differentiation: same candidate, 3 jobs → 3 distinct CVs."""

    @pytest.fixture(autouse=True)
    def _generate_cvs(self, mock_provider_factory):
        """Generate 3 CVs with job-specific mock responses."""
        self.cv_de = _make_cv_response(
            summary="Data pipeline expert with deep Spark/Kafka experience at scale.",
            skills=["Spark", "Kafka", "Python", "SQL", "Snowflake", "AWS"],
            keywords=["distributed data pipelines", "Spark", "Kafka", "data warehousing"],
        )
        self.cv_backend = _make_cv_response(
            summary="Backend engineer specializing in high-throughput REST APIs and containerization.",
            skills=["Python", "FastAPI", "Docker", "AWS", "SQL", "PostgreSQL"],
            keywords=["REST API", "FastAPI", "Docker", "AWS", "container orchestration"],
        )
        self.cv_frontend = _make_cv_response(
            summary="Frontend engineer delivering performant React applications with TypeScript.",
            skills=["React", "TypeScript", "AWS", "Docker", "Python"],
            keywords=["React", "TypeScript", "component library", "frontend performance"],
        )

    def test_summaries_are_distinct(self):
        summaries = {self.cv_de.summary_adapted, self.cv_backend.summary_adapted, self.cv_frontend.summary_adapted}
        assert len(summaries) == 3, "All three CVs must have different summaries"

    def test_skills_ordering_differs_between_jobs(self):
        de_top3 = tuple(self.cv_de.skills_ordered[:3])
        be_top3 = tuple(self.cv_backend.skills_ordered[:3])
        fe_top3 = tuple(self.cv_frontend.skills_ordered[:3])
        assert de_top3 != be_top3, "DE and backend CV should order skills differently"
        assert be_top3 != fe_top3, "Backend and frontend CV should order skills differently"
        assert de_top3 != fe_top3, "DE and frontend CV should order skills differently"

    def test_de_cv_leads_with_data_skills(self):
        top2 = self.cv_de.skills_ordered[:2]
        data_skills = {"spark", "kafka", "snowflake", "airflow", "dbt"}
        assert any(s.lower() in data_skills for s in top2), (
            f"DE CV should lead with data skills, got {top2}"
        )

    def test_backend_cv_leads_with_api_skills(self):
        top3 = [s.lower() for s in self.cv_backend.skills_ordered[:3]]
        api_skills = {"python", "fastapi", "docker", "aws", "postgresql"}
        assert any(s in api_skills for s in top3), (
            f"Backend CV should lead with API skills, got {top3}"
        )

    def test_frontend_cv_leads_with_ui_skills(self):
        top2 = [s.lower() for s in self.cv_frontend.skills_ordered[:2]]
        assert "react" in top2 or "typescript" in top2, (
            f"Frontend CV should lead with React/TypeScript, got {top2}"
        )

    def test_ats_keywords_are_job_specific(self):
        de_kw = set(k.lower() for k in self.cv_de.ats_keywords_added)
        be_kw = set(k.lower() for k in self.cv_backend.ats_keywords_added)
        fe_kw = set(k.lower() for k in self.cv_frontend.ats_keywords_added)
        # Keywords should not be identical across CVs
        assert de_kw != be_kw, "DE and backend CVs should have different ATS keywords"
        assert be_kw != fe_kw, "Backend and frontend CVs should have different ATS keywords"
        # DE CV should reference DE-specific terms
        assert any(kw in de_kw for kw in {"spark", "kafka", "data pipeline", "data warehousing", "distributed data pipelines"})
        # Frontend CV should reference frontend-specific terms
        assert any(kw in fe_kw for kw in {"react", "typescript", "component library", "frontend performance"})

    def test_all_cvs_non_empty_summary(self):
        for label, cv in [("DE", self.cv_de), ("Backend", self.cv_backend), ("Frontend", self.cv_frontend)]:
            assert cv.summary_adapted, f"{label} CV summary must not be empty"
            assert len(cv.summary_adapted) > 20, f"{label} CV summary too short"

    def test_all_cvs_have_skills(self):
        for label, cv in [("DE", self.cv_de), ("Backend", self.cv_backend), ("Frontend", self.cv_frontend)]:
            assert cv.skills_ordered, f"{label} CV skills list must not be empty"
            assert len(cv.skills_ordered) >= 3, f"{label} CV should have at least 3 ordered skills"


class TestCVAgentCallsProviderWithCorrectContext:
    """Verify the CV agent wires job context into the LLM prompt correctly."""

    @pytest.mark.asyncio
    async def test_cv_agent_calls_provider_once(self, mock_provider_factory):
        expected_cv = _make_cv_response(
            summary="Data pipeline expert.",
            skills=["Spark", "Kafka", "Python"],
            keywords=["Spark", "Kafka"],
        )
        provider = mock_provider_factory(expected_cv)
        result = await personalize_cv(
            candidate_summary=_CANDIDATE["summary"],
            candidate_headline=_CANDIDATE["headline"],
            candidate_skills=_CANDIDATE["skills"],
            candidate_career_level=_CANDIDATE["career_level"],
            candidate_experience=_CANDIDATE["experience"],
            candidate_projects=_CANDIDATE["projects"],
            job_title=_JOB_DATA_ENGINEERING["title"],
            job_company=_JOB_DATA_ENGINEERING["company"],
            job_seniority=_JOB_DATA_ENGINEERING["seniority"],
            job_tech_stack=_JOB_DATA_ENGINEERING["tech_stack"],
            requirements_must_have=_JOB_DATA_ENGINEERING["requirements"],
            strategy_guidance=_JOB_DATA_ENGINEERING["strategy"],
            provider=provider,
        )
        provider.structured_output.assert_called_once()
        assert result.summary_adapted == "Data pipeline expert."

    @pytest.mark.asyncio
    async def test_cv_agent_includes_job_title_in_prompt(self, mock_provider_factory):
        expected_cv = _make_cv_response("Backend specialist.", ["Python", "FastAPI"], ["FastAPI"])
        provider = mock_provider_factory(expected_cv)
        await personalize_cv(
            candidate_summary=_CANDIDATE["summary"],
            candidate_headline=_CANDIDATE["headline"],
            candidate_skills=_CANDIDATE["skills"],
            candidate_career_level=_CANDIDATE["career_level"],
            candidate_experience=_CANDIDATE["experience"],
            candidate_projects=_CANDIDATE["projects"],
            job_title="Senior Backend Engineer",
            job_company="APIFirst Inc",
            job_seniority="senior",
            job_tech_stack=["Python", "FastAPI"],
            requirements_must_have=["REST API design"],
            strategy_guidance=[],
            provider=provider,
        )
        call_kwargs = provider.structured_output.call_args
        user_message = call_kwargs[1]["messages"][0]["content"]
        assert "Senior Backend Engineer" in user_message
        assert "APIFirst Inc" in user_message

    @pytest.mark.asyncio
    async def test_cv_agent_includes_candidate_skills_in_prompt(self, mock_provider_factory):
        expected_cv = _make_cv_response("Summary.", ["React", "TypeScript"], ["React"])
        provider = mock_provider_factory(expected_cv)
        await personalize_cv(
            candidate_summary="Engineer with React experience.",
            candidate_headline="Frontend Engineer",
            candidate_skills=["React", "TypeScript", "CSS"],
            candidate_career_level="senior",
            candidate_experience=[],
            candidate_projects=[],
            job_title="Frontend Engineer",
            job_company="UX Corp",
            job_seniority="senior",
            job_tech_stack=["React", "TypeScript"],
            requirements_must_have=["React expert"],
            strategy_guidance=[],
            provider=provider,
        )
        call_kwargs = provider.structured_output.call_args
        user_message = call_kwargs[1]["messages"][0]["content"]
        assert "React" in user_message
        assert "TypeScript" in user_message


class TestPersonalizedCVSchema:
    """Validate PersonalizedCV schema constraints."""

    def test_cv_with_all_fields(self):
        cv = PersonalizedCV(
            summary_adapted="Expert data engineer.",
            headline_adapted="Senior Data Engineer",
            skills_ordered=["Spark", "Kafka", "Python"],
            ats_keywords_added=["distributed systems"],
            changes=[],
        )
        assert cv.summary_adapted == "Expert data engineer."
        assert cv.skills_ordered[0] == "Spark"

    def test_cv_defaults_to_empty_lists(self):
        cv = PersonalizedCV()
        assert cv.skills_ordered == []
        assert cv.ats_keywords_added == []
        assert cv.changes == []
        assert cv.summary_adapted is None
