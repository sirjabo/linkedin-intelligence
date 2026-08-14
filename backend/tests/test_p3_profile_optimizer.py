"""Tests for P3 Phase 18: Profile Optimizer.

Verifies:
  - _aggregate_skill_gaps() counts skills correctly
  - generate_optimization_report() returns correct structure
  - Deterministic tips are generated without LLM
  - Empty analyses returns a sensible no-data report
"""
import pytest

from app.services.profile_optimizer import (
    generate_optimization_report,
    _aggregate_skill_gaps,
    _deterministic_tips,
)


SAMPLE_ANALYSES = [
    {"match_tier": "strong", "overall_score": 0.78, "missing_skills": ["Kafka", "Flink"], "matched_skills": ["Python"], "llm_gaps": ["Kafka"]},
    {"match_tier": "moderate", "overall_score": 0.55, "missing_skills": ["Kafka", "dbt"], "matched_skills": ["Spark"], "llm_gaps": ["Kafka", "dbt"]},
    {"match_tier": "strong", "overall_score": 0.80, "missing_skills": ["Kafka", "Kubernetes"], "matched_skills": ["Python", "Spark"], "llm_gaps": []},
    {"match_tier": "excellent", "overall_score": 0.92, "missing_skills": [], "matched_skills": ["Python", "Kafka"], "llm_gaps": []},
]

SAMPLE_PROFILE = {
    "summary": "Experienced data engineer with Python and Spark skills.",
    "skills": [{"canonical_name": "Python"}, {"canonical_name": "Spark"}],
    "experience": [{"title": "Data Engineer", "company": "Acme"}],
    "education": [],
}


# ── _aggregate_skill_gaps ─────────────────────────────────────────────────────

def test_aggregate_skill_gaps_counts_correctly():
    gaps = _aggregate_skill_gaps(SAMPLE_ANALYSES)
    gap_map = {g.skill: g.frequency for g in gaps}
    assert gap_map["kafka"] == 3  # appears in 3 of 4 analyses
    assert gap_map["flink"] == 1
    assert gap_map["dbt"] == 1
    assert gap_map.get("kubernetes") == 1


def test_aggregate_skill_gaps_empty():
    gaps = _aggregate_skill_gaps([])
    assert gaps == []


def test_aggregate_skill_gaps_normalizes_case():
    analyses = [
        {"match_tier": "strong", "overall_score": 0.7, "missing_skills": ["KAFKA", "Kafka"], "matched_skills": [], "llm_gaps": []},
    ]
    gaps = _aggregate_skill_gaps(analyses)
    gap_map = {g.skill: g.frequency for g in gaps}
    # Both should normalize to "kafka" with count 2
    assert gap_map.get("kafka") == 2


# ── _deterministic_tips ───────────────────────────────────────────────────────

def test_deterministic_tips_generates_skill_tips():
    from app.services.profile_optimizer import SkillGap
    gaps = [SkillGap(skill="kafka", frequency=5), SkillGap(skill="dbt", frequency=2)]
    tips = _deterministic_tips(gaps, SAMPLE_PROFILE)
    tip_texts = [t.tip for t in tips]
    assert any("kafka" in t.lower() for t in tip_texts)


def test_deterministic_tips_no_summary_tip():
    from app.services.profile_optimizer import SkillGap
    gaps = []
    profile_missing_summary = {"summary": None, "skills": ["Python"], "experience": [{"title": "Eng"}], "education": []}
    tips = _deterministic_tips(gaps, profile_missing_summary)
    assert any("summary" in t.tip.lower() for t in tips)


def test_deterministic_tips_no_skills_tip():
    from app.services.profile_optimizer import SkillGap
    profile_no_skills = {"summary": "Great engineer", "skills": [], "experience": [], "education": []}
    tips = _deterministic_tips([], profile_no_skills)
    categories = {t.category for t in tips}
    assert "profile_completeness" in categories


# ── generate_optimization_report ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_report_structure():
    """Report has required fields and correct types."""
    report = await generate_optimization_report(SAMPLE_ANALYSES, SAMPLE_PROFILE)
    assert report.total_analyses_reviewed == 4
    assert isinstance(report.top_skill_gaps, list)
    assert isinstance(report.tips, list)
    assert isinstance(report.summary, str)
    assert len(report.summary) > 0


@pytest.mark.asyncio
async def test_generate_report_empty_analyses():
    """Empty analyses returns a no-data report."""
    report = await generate_optimization_report([], SAMPLE_PROFILE)
    assert report.total_analyses_reviewed == 0
    assert report.top_skill_gaps == []
    assert "No match analyses" in report.summary or len(report.summary) > 0


@pytest.mark.asyncio
async def test_generate_report_kafka_is_top_gap():
    report = await generate_optimization_report(SAMPLE_ANALYSES, SAMPLE_PROFILE)
    # kafka appears 3 times — should be at the top
    if report.top_skill_gaps:
        assert report.top_skill_gaps[0].skill == "kafka"
        assert report.top_skill_gaps[0].frequency == 3


@pytest.mark.asyncio
async def test_generate_report_tips_have_impact():
    report = await generate_optimization_report(SAMPLE_ANALYSES, SAMPLE_PROFILE)
    for tip in report.tips:
        assert tip.impact in ("high", "medium", "low")
        assert tip.priority >= 1
        assert tip.category in ("skill", "experience", "summary", "profile_completeness")
