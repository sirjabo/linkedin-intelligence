"""Unit tests for ATS Engine — tasks/cursor-sprint-001.md requirements."""

from __future__ import annotations

import pytest

from app.engine.ats import (
    ATSEngine,
    ATSMatcher,
    MatchResult,
    RecommendationEngine,
    WeightedKeyword,
    calculate_ats_score,
    frequency_to_weight,
    role_keywords_to_weighted,
)
from app.engine.cv_parser import CVParser, ParsedCV
from app.schemas.analyze import SectionScores

SAMPLE_CV = """
Joaquín Pérez
joaco@example.com | +54 11 5555-1234 | linkedin.com/in/joaco

Summary
Analytics Engineer with 5 years of experience in Python, SQL and pandas.
Interested in transitioning to AI Engineer roles with LangChain and RAG.

Experience
Analytics Engineer — BBVA
- Desarrollé scripts de automatización en Python
- Built ETL pipelines with SQL and Airflow reducing reporting time by 40%
- Created dashboards in Power BI for marketing analytics

Skills
Python, SQL, pandas, n8n, Power BI, Git, Docker

Education
Licenciatura en Sistemas — UBA

Projects
"""


class TestFrequencyToWeight:
    def test_high_frequency(self) -> None:
        assert frequency_to_weight(0.9) == 1.0

    def test_mid_high(self) -> None:
        assert frequency_to_weight(0.6) == 0.7

    def test_mid(self) -> None:
        assert frequency_to_weight(0.4) == 0.5

    def test_low(self) -> None:
        assert frequency_to_weight(0.1) == 0.3


class TestCalculateAtsScore:
    def test_score_zero_when_no_keywords(self) -> None:
        result = MatchResult(matched=[], missing=[])
        assert calculate_ats_score(result) == 0

    def test_score_100_when_all_match(self) -> None:
        kws = [
            WeightedKeyword(name="Python", weight=1.0),
            WeightedKeyword(name="SQL", weight=0.8),
        ]
        result = MatchResult(matched=kws, missing=[])
        assert calculate_ats_score(result) == 100

    def test_critical_penalty_reduces_score(self) -> None:
        matched = [WeightedKeyword(name="Python", weight=1.0)]
        missing = [WeightedKeyword(name="SQL", weight=0.95)]
        result = MatchResult(matched=matched, missing=missing)
        raw = int((1.0 / 1.95) * 100)
        score = calculate_ats_score(result)
        assert score == max(0, raw - 10)
        assert score < raw


class TestATSMatcher:
    def setup_method(self) -> None:
        self.matcher = ATSMatcher()

    def test_alias_matching_langchain(self) -> None:
        keywords = [
            WeightedKeyword(
                name="LangChain",
                weight=0.9,
                aliases=["langchain", "lang-chain"],
            )
        ]
        result = self.matcher.match(
            [], keywords, cv_text="Experience with langchain frameworks"
        )
        assert any(k.name == "LangChain" for k in result.matched)
        assert result.match_types.get("LangChain") in {"exact", "alias"}

    def test_exact_match_python(self) -> None:
        keywords = [WeightedKeyword(name="Python", weight=1.0, aliases=["python"])]
        result = self.matcher.match(["Python"], keywords, cv_text="")
        assert any(k.name == "Python" for k in result.matched)


class TestRecommendationEngine:
    def test_recommendations_ordered_by_priority(self) -> None:
        engine = RecommendationEngine()
        parsed = ParsedCV(skills=["Python"], experience="did stuff", projects="")
        missing = [
            WeightedKeyword(name="LangChain", weight=0.9),
            WeightedKeyword(name="ObscureLib", weight=0.2),
        ]
        recs = engine.generate(
            parsed,
            missing,
            SectionScores(
                contact=80,
                summary=50,
                experience=50,
                skills=40,
                education=70,
                projects=20,
            ),
        )
        assert len(recs) <= 5
        priorities = [r.priority for r in recs]
        assert priorities == sorted(priorities)
        assert any(r.type == "add_keyword" and "LangChain" in r.message for r in recs)


class TestCVParser:
    def test_extracts_skills(self) -> None:
        parser = CVParser()
        parsed = parser.parse(SAMPLE_CV)
        assert "Python" in parsed.skills
        assert "SQL" in parsed.skills
        assert parsed.contact


@pytest.mark.asyncio
class TestATSEngineIntegration:
    async def test_analyze_returns_valid_score(self) -> None:
        engine = ATSEngine(db=None)
        result = await engine.analyze(SAMPLE_CV, "ai_engineer")
        assert 0 <= result.ats_score <= 100
        assert result.keyword_analysis.found or result.keyword_analysis.missing
        assert len(result.recommendations) <= 5

    async def test_joaco_cv_finds_python_sql(self) -> None:
        engine = ATSEngine(db=None)
        result = await engine.analyze(SAMPLE_CV, "ai_engineer")
        found_names = {k.keyword for k in result.keyword_analysis.found}
        assert "Python" in found_names
        assert "SQL" in found_names
        missing_names = {k.keyword for k in result.keyword_analysis.missing}
        assert "LangGraph" in missing_names or "FastAPI" in missing_names

    async def test_role_keywords_loaded(self) -> None:
        kws = role_keywords_to_weighted("ai_engineer")
        names = {k.name for k in kws}
        assert "Python" in names
        assert "LangChain" in names
        assert any(k.weight == 0.90 for k in kws if k.name == "LangChain")
