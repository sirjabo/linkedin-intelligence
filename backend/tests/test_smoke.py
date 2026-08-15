"""Real smoke tests: validate LLM agent output quality with actual API calls.

These tests are SKIPPED unless ANTHROPIC_API_KEY is set and non-empty.
Run manually to verify agent quality after prompt or model changes:

    ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_smoke.py -v -s

Criteria-based evaluation via app.services.ai_evaluation — no ground-truth
labels required. Agents are judged on structural validity, not exact content.
"""
import pytest

from app.core.config import settings
from app.services.ai_evaluation import (
    evaluate,
    field_not_empty,
    field_in_range,
    field_contains_keyword,
    field_one_of,
    list_items_have_field,
)

# Skip all tests in this module if no real API key is configured
pytestmark = pytest.mark.skipif(
    not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "",
    reason="ANTHROPIC_API_KEY not set — skipping real LLM smoke tests",
)

SAMPLE_JD = """\
Senior Data Engineer — TechCorp
We are looking for a Senior Data Engineer with 5+ years of experience building
large-scale data pipelines. Must-have: Python, SQL, Apache Spark, dbt.
Nice-to-have: Kafka, Airflow. Location: Buenos Aires (hybrid). Full-time.
Salary: $120k-$150k. We do NOT offer visa sponsorship.
"""

CANDIDATE_SUMMARY = (
    "Experienced Senior Data Engineer with 7 years building Python data pipelines, "
    "dbt transformations, and Kafka streaming systems. Strong SQL skills."
)
CANDIDATE_SKILLS = ["Python", "SQL", "dbt", "Kafka", "Airflow", "PostgreSQL"]


# ── JobAgent smoke test ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_agent_smoke():
    from app.services.agents.job_agent import parse_job_description

    result = await parse_job_description(SAMPLE_JD)

    report = evaluate(result, [
        field_not_empty("title", min_length=3),
        field_not_empty("company", min_length=2),
        field_not_empty("requirements", min_length=1),
        field_not_empty("tech_stack", min_length=1),
        field_contains_keyword("tech_stack", "python"),
        field_one_of("seniority", {"senior", "staff", "lead", "principal"}),
        field_in_range("parsing_confidence", 0.5, 1.0),
    ])

    print("\n" + report.summary())
    assert report.passed, f"JobAgent failed evaluation:\n{report.summary()}"
    # Visa sponsorship should be False (explicitly not offered in JD)
    assert result.visa_sponsorship is False, "visa_sponsorship should be False (explicitly stated)"


@pytest.mark.asyncio
async def test_job_agent_requirement_classification():
    from app.services.agents.job_agent import parse_job_description

    result = await parse_job_description(SAMPLE_JD)
    must_have = [r for r in result.requirements if r.requirement_type == "must_have"]
    nice_to_have = [r for r in result.requirements if r.requirement_type == "nice_to_have"]

    # Should identify at least 2 must-have and 1 nice-to-have
    assert len(must_have) >= 2, f"Expected >=2 must_have, got {len(must_have)}"
    assert len(nice_to_have) >= 1, f"Expected >=1 nice_to_have, got {len(nice_to_have)}"

    # At least some requirements should have a classification
    with_classification = [r for r in result.requirements if r.classification]
    assert len(with_classification) >= 1, "At least one requirement should have a classification"


# ── MatchAgent smoke test ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_match_agent_smoke():
    from app.services.agents.match_agent import reason_about_match

    result = await reason_about_match(
        candidate_summary=CANDIDATE_SUMMARY,
        candidate_skills=CANDIDATE_SKILLS,
        candidate_career_level="senior",
        candidate_location="Buenos Aires, Argentina",
        job_title="Senior Data Engineer",
        job_company="TechCorp",
        job_seniority="senior",
        job_tech_stack=["Python", "Spark", "dbt", "Kafka"],
        requirements_must_have=["Python", "SQL", "Apache Spark", "dbt"],
        requirements_nice_to_have=["Kafka", "Airflow"],
        deterministic_score=0.78,
    )

    report = evaluate(result, [
        field_in_range("score", 0.0, 1.0),
        field_not_empty("reasoning", min_length=50),
        field_not_empty("strengths", min_length=1),
        field_not_empty("gaps", min_length=0),
        field_one_of("recommendation", {"apply", "apply_with_tailoring", "stretch", "do_not_apply"}),
    ])

    print("\n" + report.summary())
    assert report.passed, f"MatchAgent failed evaluation:\n{report.summary()}"
    # Score should be reasonable for a strong match
    assert result.score >= 0.5, f"Expected score >= 0.5 for strong candidate, got {result.score}"


# ── CVAgent smoke test ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cv_agent_smoke():
    from app.services.agents.cv_agent import personalize_cv

    result = await personalize_cv(
        candidate_summary=CANDIDATE_SUMMARY,
        candidate_headline="Senior Data Engineer | Python | dbt",
        candidate_skills=CANDIDATE_SKILLS,
        candidate_career_level="senior",
        candidate_experience=[
            {
                "title": "Senior Data Engineer",
                "company": "DataCo",
                "duration": "3 years",
                "description": "Built Python ETL pipelines and dbt models",
            }
        ],
        candidate_projects=None,
        job_title="Senior Data Engineer",
        job_company="TechCorp",
        job_seniority="senior",
        job_tech_stack=["Python", "Spark", "dbt", "Kafka"],
        requirements_must_have=["Python", "SQL", "Apache Spark", "dbt"],
        strategy_guidance=["Emphasize dbt experience", "Highlight Python pipeline work"],
    )

    report = evaluate(result, [
        field_not_empty("summary_adapted", min_length=80),
        field_not_empty("changes", min_length=1),
        field_not_empty("skills_ordered", min_length=3),
        list_items_have_field("changes", "adapted", min_non_empty=1),
    ])

    print("\n" + report.summary())
    assert report.passed, f"CVAgent failed evaluation:\n{report.summary()}"
    # Summary should mention the job company or key tech
    summary_lower = (result.summary_adapted or "").lower()
    has_relevant_content = any(kw in summary_lower for kw in ["python", "data", "pipeline", "engineer"])
    assert has_relevant_content, f"CV summary doesn't mention relevant tech: {result.summary_adapted}"


# ── CommunicationAgent smoke test ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_communication_agent_cover_letter_smoke():
    from app.services.agents.communication_agent import generate_cover_letter

    result = await generate_cover_letter(
        candidate_summary=CANDIDATE_SUMMARY,
        candidate_skills=CANDIDATE_SKILLS,
        candidate_career_level="senior",
        candidate_location="Buenos Aires, Argentina",
        job_title="Senior Data Engineer",
        job_company="TechCorp",
        job_seniority="senior",
        strengths_to_emphasize=["Python expertise", "dbt experience"],
        cover_letter_key_points=["5+ years pipeline experience", "dbt transformations"],
        match_tier="strong",
    )

    report = evaluate(result, [
        field_not_empty("content", min_length=200),
        field_not_empty("key_points_addressed", min_length=1),
    ])

    print("\n" + report.summary())
    assert report.passed, f"CommunicationAgent cover letter failed:\n{report.summary()}"
    # Content should mention TechCorp
    assert "techcorp" in result.content.lower(), "Cover letter should mention the company name"
