"""Unit tests for ATS Engine — Sprint B-006."""

from __future__ import annotations

import pytest

from app.engine.ats import (
    ATSEngine,
    ATSMatcher,
    RecommendationEngine,
    WeightedKeyword,
    calculate_ats_score,
    frequency_to_weight,
)
from app.engine.cv_parser import CVParser, ParsedCV


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
    def test_perfect_match(self) -> None:
        kws = [
            WeightedKeyword(name="Python", weight=1.0),
            WeightedKeyword(name="SQL", weight=0.8),
        ]
        from app.engine.ats import MatchResult

        result = MatchResult(matched=kws, missing=[])
        assert calculate_ats_score(result) == 100

    def test_no_keywords(self) -> None:
        from app.engine.ats import MatchResult

        result = MatchResult(matched=[], missing=[])
        assert calculate_ats_score(result) == 0

    def test_critical_penalty(self) -> None:
        from app.engine.ats import MatchResult

        matched = [WeightedKeyword(name="Python", weight=1.0)]
        missing = [WeightedKeyword(name="SQL", weight=0.95)]
        result = MatchResult(matched=matched, missing=missing)
        # raw = 1.0/1.95*100 ≈ 51, penalty 10 → ~41
        score = calculate_ats_score(result)
        assert 30 <= score <= 50
        assert score < int((1.0 / 1.95) * 100)


class TestATSMatcher:
    def setup_method(self) -> None:
        self.matcher = ATSMatcher()
        self.keywords = [
            WeightedKeyword(name="Python", weight=1.0, aliases=["python3"]),
            WeightedKeyword(name="LangChain", weight=0.85, aliases=["lang-chain"]),
            WeightedKeyword(name="RAG", weight=0.8, aliases=["retrieval augmented"]),
            WeightedKeyword(name="Fortran", weight=0.3, aliases=[]),
        ]

    def test_exact_match(self) -> None:
        result = self.matcher.match(["Python", "SQL"], self.keywords, cv_text="Python developer")
        names = [k.name for k in result.matched]
        assert "Python" in names

    def test_alias_match(self) -> None:
        result = self.matcher.match([], self.keywords, cv_text="Experience with lang-chain frameworks")
        names = [k.name for k in result.matched]
        assert "LangChain" in names
        assert result.match_types.get("LangChain") == "alias"

    def test_semantic_match_for_high_weight(self) -> None:
        result = self.matcher.match(
            ["embeddings"],
            [WeightedKeyword(name="Vector DB", weight=0.75, aliases=[])],
            cv_text="Built semantic search with embeddings and pinecone",
        )
        assert any(k.name == "Vector DB" for k in result.matched)

    def test_missing_low_weight_no_semantic(self) -> None:
        result = self.matcher.match(["Java"], self.keywords, cv_text="Java developer")
        assert any(k.name == "Fortran" for k in result.missing)


class TestCVParser:
    def test_extracts_skills(self) -> None:
        parser = CVParser()
        parsed = parser.parse(SAMPLE_CV)
        assert "Python" in parsed.skills
        assert "SQL" in parsed.skills
        assert parsed.contact

    def test_extracts_experience_bullets(self) -> None:
        parser = CVParser()
        parsed = parser.parse(SAMPLE_CV)
        assert len(parsed.experience_bullets) >= 1


class TestRecommendationEngine:
    def test_generates_add_keyword_for_critical_missing(self) -> None:
        engine = RecommendationEngine()
        parsed = ParsedCV(skills=["Python"], experience="did stuff", projects="")
        missing = [
            WeightedKeyword(name="LangChain", weight=0.9),
            WeightedKeyword(name="ObscureLib", weight=0.2),
        ]
        from app.schemas.analyze import SectionScores

        recs = engine.generate(
            parsed,
            missing,
            SectionScores(
                contact=80, summary=50, experience=50, skills=40, education=70, projects=20
            ),
        )
        assert any(r.type == "add_keyword" and "LangChain" in r.message for r in recs)
        assert any(r.type == "add_section" and r.section == "projects" for r in recs)
        assert len(recs) <= 5


@pytest.mark.asyncio
class TestATSEngineIntegration:
    async def test_analyze_returns_valid_score(self) -> None:
        engine = ATSEngine(db=None)
        result = await engine.analyze(SAMPLE_CV, "ai_engineer")
        assert 0 <= result.ats_score <= 100
        assert result.keyword_analysis.found or result.keyword_analysis.missing
        assert result.section_scores.skills >= 0
        assert len(result.recommendations) <= 5
        assert result.summary

    async def test_joaco_cv_finds_python_sql(self) -> None:
        engine = ATSEngine(db=None)
        result = await engine.analyze(SAMPLE_CV, "ai_engineer")
        found_names = {k.keyword for k in result.keyword_analysis.found}
        assert "Python" in found_names
        assert "SQL" in found_names
        # Should be missing some AI-specific keywords not present in the CV
        missing_names = {k.keyword for k in result.keyword_analysis.missing}
        assert "LangGraph" in missing_names or "RAG" in missing_names or "FastAPI" in missing_names
