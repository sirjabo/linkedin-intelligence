"""Tests for P2 Phase 10: Form Intelligence LLM fallback.

Verifies:
  - classify_field() returns "unknown" for truly unrecognized labels
  - classify_field_llm() returns a valid SemanticType when LLM responds correctly
  - classify_field_llm() falls back to "unknown" on LLM error
  - classify_field_llm() falls back to "unknown" if LLM returns garbage
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.form_intelligence import (
    _ALL_SEMANTIC_TYPES,
    classify_field,
    classify_field_llm,
)

# ── classify_field deterministic tests ───────────────────────────────────────

def test_classify_field_known_labels():
    assert classify_field("Full Name") == "full_name"
    assert classify_field("Email Address") == "email"
    assert classify_field("Resume") == "cv_file"
    assert classify_field("Cover Letter") == "cover_letter"
    assert classify_field("LinkedIn Profile") == "linkedin_url"


def test_classify_field_returns_unknown_for_unrecognized():
    assert classify_field("Hobbies and Interests") == "unknown"
    assert classify_field("Referral Code") == "unknown"
    # "How did you hear about us" is now classified as reference_contact (Sprint F)
    assert classify_field("How did you hear about us") == "reference_contact"


# ── classify_field_llm tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_classify_field_llm_returns_valid_type():
    """LLM returns a valid semantic type — should be accepted."""
    mock_content = MagicMock()
    mock_content.text = "work_authorization"

    mock_resp = MagicMock()
    mock_resp.content = [mock_content]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "test-key"
            result = await classify_field_llm("Are you authorized to work in the US?")

    assert result == "work_authorization"


@pytest.mark.asyncio
async def test_classify_field_llm_falls_back_on_garbage_response():
    """LLM returns nonsense — should fall back to 'unknown'."""
    mock_content = MagicMock()
    mock_content.text = "definitely_not_a_type_xyz"

    mock_resp = MagicMock()
    mock_resp.content = [mock_content]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "test-key"
            result = await classify_field_llm("Some mystery field")

    assert result == "unknown"


@pytest.mark.asyncio
async def test_classify_field_llm_falls_back_on_exception():
    """LLM raises an exception — should fall back to 'unknown'."""
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("API error")):
        result = await classify_field_llm("Anything")
    assert result == "unknown"


@pytest.mark.asyncio
async def test_classify_field_llm_accepts_hyphenated_response():
    """LLM returns 'full-name' (hyphenated) — normalisation should accept it."""
    mock_content = MagicMock()
    mock_content.text = "full-name"

    mock_resp = MagicMock()
    mock_resp.content = [mock_content]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "test-key"
            result = await classify_field_llm("Your full name")

    assert result == "full_name"


def test_all_semantic_types_non_empty():
    """_ALL_SEMANTIC_TYPES is populated and contains expected values."""
    assert "unknown" in _ALL_SEMANTIC_TYPES
    assert "email" in _ALL_SEMANTIC_TYPES
    assert "full_name" in _ALL_SEMANTIC_TYPES
    assert len(_ALL_SEMANTIC_TYPES) >= 10
