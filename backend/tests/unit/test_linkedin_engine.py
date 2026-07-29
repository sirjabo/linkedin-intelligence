"""Unit tests for the LinkedIn Profile Engine — Sprint 002."""

from __future__ import annotations

from app.engine.linkedin import (
    SECTION_WEIGHTS,
    AboutScorer,
    ProfileParser,
    ProfileScorer,
    TitleScorer,
)

SAMPLE_PROFILE = """
AI Engineer | Python · LangChain · RAG · FastAPI · SQL

About
Building production RAG systems with LangChain and FastAPI.
I reduced retrieval latency by 40% across 3 LLM pipelines in the last 2 years.
Open to AI Engineer roles — let's connect.

Experience
AI Engineer at Acme (2022 - Present)
Built RAG pipelines with Python, LangChain, and PostgreSQL

Projects
RAG Chatbot — Python, LangChain, OpenAI

Skills
Python · LangChain · FastAPI · SQL · Docker · AWS

Education
BSc Computer Science — University (2018)
"""


class TestProfileParser:
    def test_extracts_title_with_role(self) -> None:
        parsed = ProfileParser().parse(SAMPLE_PROFILE)
        assert "AI Engineer" in parsed.title
        assert "LangChain" in parsed.title

    def test_extracts_about(self) -> None:
        parsed = ProfileParser().parse(SAMPLE_PROFILE)
        assert "RAG" in parsed.about
        assert "40%" in parsed.about

    def test_extracts_skills(self) -> None:
        parsed = ProfileParser().parse(SAMPLE_PROFILE)
        assert any("Python" in s for s in parsed.skills)
        assert any("LangChain" in s for s in parsed.skills)


class TestTitleScorer:
    def test_weak_title_scores_low(self) -> None:
        result = TitleScorer().score("Analista SSR en BBVA", "ai_engineer")
        assert result.score < 20
        assert result.checks["role_mentioned"] is False

    def test_strong_title_scores_high(self) -> None:
        result = TitleScorer().score(
            "AI Engineer | Python · LangChain · SQL",
            "ai_engineer",
        )
        assert result.score > 70
        assert result.checks["role_mentioned"] is True
        assert result.checks["role_first"] is True


class TestAboutScorer:
    def test_empty_about_scores_zero(self) -> None:
        result = AboutScorer().score("", "ai_engineer")
        assert result.score == 0

    def test_detects_cta(self) -> None:
        body = (
            "AI Engineer building LLM apps with Python and LangChain. "
            "Shipped 3 RAG products that cut support tickets by 40%. "
            + ("stack keywords python langchain fastapi sql docker. " * 8)
        )
        about = body + "Open to AI Engineer opportunities in fintech."
        result = AboutScorer().score(about, "ai_engineer")
        assert result.checks["has_cta"] is True


class TestProfileScorer:
    def test_overall_score_weighted(self) -> None:
        parsed = ProfileParser().parse(SAMPLE_PROFILE)
        result = ProfileScorer().score(parsed, "ai_engineer")
        expected = (
            result.section_scores.title * SECTION_WEIGHTS["title"]
            + result.section_scores.about * SECTION_WEIGHTS["about"]
            + result.section_scores.skills * SECTION_WEIGHTS["skills"]
            + result.section_scores.experience * SECTION_WEIGHTS["experience"]
            + result.section_scores.projects * SECTION_WEIGHTS["projects"]
            + result.section_scores.education * SECTION_WEIGHTS["education"]
        )
        assert abs(result.overall_score - round(expected, 1)) < 0.01
        assert 0 <= result.overall_score <= 100

    def test_section_weights_sum_to_one(self) -> None:
        assert abs(sum(SECTION_WEIGHTS.values()) - 1.0) < 1e-9

    def test_first_recommendation_is_weakest_weighted_section(self) -> None:
        parsed = ProfileParser().parse(
            "Analista SSR en BBVA\n\n"
            "About\nAnalista de datos con experiencia.\n\n"
            "Skills\nExcel · Power BI"
        )
        result = ProfileScorer().score(parsed, "ai_engineer")
        assert result.recommendations
        weighted = {
            "title": result.section_scores.title * SECTION_WEIGHTS["title"],
            "about": result.section_scores.about * SECTION_WEIGHTS["about"],
            "skills": result.section_scores.skills * SECTION_WEIGHTS["skills"],
            "experience": result.section_scores.experience * SECTION_WEIGHTS["experience"],
            "projects": result.section_scores.projects * SECTION_WEIGHTS["projects"],
            "education": result.section_scores.education * SECTION_WEIGHTS["education"],
        }
        weakest = min(weighted.items(), key=lambda item: item[1])[0]
        assert result.recommendations[0].section == weakest
