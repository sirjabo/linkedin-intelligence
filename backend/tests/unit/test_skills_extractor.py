"""Tests for heuristic skills extractor."""

from __future__ import annotations

import pytest

from app.etl.skills_extractor import SkillsExtractor


@pytest.mark.asyncio
async def test_heuristic_extracts_python_and_langchain() -> None:
    extractor = SkillsExtractor(use_llm=False)
    result = await extractor.extract(
        "Looking for an AI Engineer with Python, LangChain, RAG and FastAPI experience."
    )
    names = {s.name for s in result.skills}
    assert "Python" in names
    assert "LangChain" in names
    assert "RAG" in names
    assert "FastAPI" in names
    assert all(s.category for s in result.skills)
