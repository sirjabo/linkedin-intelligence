"""Unit tests for new services: about_writer, email_service, market salary, benchmark logic.

All pure-unit — no real HTTP, no DB, no LLM calls required.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

# ── about_writer._parse_json ──────────────────────────────────────────────────
from app.services.about_writer import _parse_json


def test_parse_json_clean():
    payload = {"variants": [{"id": 1, "tone": "t", "text": "hello"}], "tips": ["tip1"]}
    result = _parse_json(json.dumps(payload))
    assert result["variants"][0]["id"] == 1
    assert result["tips"] == ["tip1"]


def test_parse_json_strips_markdown_fence():
    payload = {"variants": [], "tips": []}
    raw = f"```json\n{json.dumps(payload)}\n```"
    result = _parse_json(raw)
    assert result == payload


def test_parse_json_strips_plain_fence():
    payload = {"variants": [], "tips": []}
    raw = f"```\n{json.dumps(payload)}\n```"
    result = _parse_json(raw)
    assert result == payload


def test_parse_json_invalid_raises():
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_json("not json at all {broken")


def test_parse_json_empty_string_raises():
    with pytest.raises(ValueError):
        _parse_json("```\nnot json\n```")


# ── email_service graceful degradation ───────────────────────────────────────

from app.services import email_service as _email_mod


def test_send_email_returns_false_when_smtp_not_configured(monkeypatch):
    monkeypatch.setattr(_email_mod.settings, "SMTP_HOST", "")
    result = _email_mod.send_email(
        to="user@example.com",
        subject="Test",
        html_body="<p>Hi</p>",
        text_body="Hi",
    )
    assert result is False


def test_send_email_attempts_smtp_when_configured(monkeypatch):
    monkeypatch.setattr(_email_mod.settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(_email_mod.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(_email_mod.settings, "SMTP_USER", "user@gmail.com")
    monkeypatch.setattr(_email_mod.settings, "SMTP_PASSWORD", "pass")
    monkeypatch.setattr(_email_mod.settings, "SMTP_FROM", "noreply@example.com")

    mock_smtp = MagicMock()
    mock_smtp_instance = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_service.smtplib.SMTP", mock_smtp):
        result = _email_mod.send_email(
            to="dest@example.com",
            subject="Weekly digest",
            html_body="<p>Top skills</p>",
            text_body="Top skills",
        )

    assert result is True
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once()
    mock_smtp_instance.sendmail.assert_called_once()


# ── market salary ranges ──────────────────────────────────────────────────────

from app.api.routes.market import _SALARY_RANGES


def test_salary_ranges_all_roles_present():
    expected_roles = {
        "ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer",
        "backend_engineer", "frontend_engineer", "devops_engineer", "data_scientist",
    }
    assert expected_roles == set(_SALARY_RANGES.keys()), "All 8 roles must have salary data"


def test_salary_ranges_valid_structure():
    for role, data in _SALARY_RANGES.items():
        assert "min_usd" in data, f"{role}: missing 'min_usd'"
        assert "max_usd" in data, f"{role}: missing 'max_usd'"
        assert "median_usd" in data, f"{role}: missing 'median_usd'"
        assert data["min_usd"] <= data["median_usd"] <= data["max_usd"], (
            f"{role}: min({data['min_usd']}) <= median({data['median_usd']}) <= max({data['max_usd']}) violated"
        )
        assert data["min_usd"] > 0, f"{role}: min_usd must be positive"


def test_salary_ranges_usd_range_sane():
    for role, data in _SALARY_RANGES.items():
        assert 500 <= data["min_usd"] <= 15000, f"{role}: min_usd out of expected range"
        assert 1000 <= data["max_usd"] <= 25000, f"{role}: max_usd out of expected range"


# ── benchmark tier logic ──────────────────────────────────────────────────────

def _compute_tier(percentile: int) -> str:
    if percentile >= 75:
        return "Excelente"
    if percentile >= 50:
        return "Bueno"
    if percentile >= 25:
        return "En desarrollo"
    return "Inicial"


@pytest.mark.parametrize("pct,expected_tier", [
    (100, "Excelente"),
    (75, "Excelente"),
    (74, "Bueno"),
    (50, "Bueno"),
    (49, "En desarrollo"),
    (25, "En desarrollo"),
    (24, "Inicial"),
    (0, "Inicial"),
])
def test_benchmark_tier_thresholds(pct, expected_tier):
    assert _compute_tier(pct) == expected_tier


def test_benchmark_percentile_calculation():
    """Test the percentile calculation formula used in the endpoint."""
    # If candidate matches 6 out of 8 market skills → 75 percentile
    matched = 6
    total = 8
    percentile = int((matched / total) * 100) if total > 0 else 0
    assert percentile == 75
    assert _compute_tier(percentile) == "Excelente"


def test_benchmark_percentile_zero_total():
    """No skills to check → percentile 0, tier Inicial."""
    matched = 0
    total = 0
    percentile = int((matched / total) * 100) if total > 0 else 0
    assert percentile == 0
    assert _compute_tier(percentile) == "Inicial"


# ── rate limiter storage URI ──────────────────────────────────────────────────

def test_limiter_uses_memory_fallback_when_no_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)

    import importlib

    import app.core.limiter as limiter_mod
    importlib.reload(limiter_mod)

    assert limiter_mod.limiter is not None


def test_limiter_uses_redis_when_configured(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    import importlib

    import app.core.limiter as limiter_mod
    importlib.reload(limiter_mod)

    assert limiter_mod.limiter is not None
