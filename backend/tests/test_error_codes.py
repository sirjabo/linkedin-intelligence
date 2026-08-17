"""Tests for ErrorCode taxonomy (app/core/errors.py)."""
import pytest
from app.core.errors import ErrorCode


def test_error_codes_are_strings():
    for code in ErrorCode:
        assert isinstance(code.value, str)
        assert "." in code.value  # namespaced: "domain.code"


def test_critical_codes_present():
    required = [
        "APPLICATION_ALREADY_SUBMITTED",
        "AGENT_DUPLICATE_SUBMIT",
        "AGENT_BROWSER_ERROR",
        "LLM_PROMPT_INJECTION",
        "BUDGET_EXCEEDED",
    ]
    names = {code.name for code in ErrorCode}
    for name in required:
        assert name in names, f"ErrorCode.{name} is missing"


def test_error_code_string_comparison():
    assert ErrorCode.AGENT_CRASH == "agent.crash"
    assert ErrorCode.LLM_PROMPT_INJECTION == "llm.prompt_injection_blocked"


def test_error_codes_unique():
    values = [code.value for code in ErrorCode]
    assert len(values) == len(set(values)), "Duplicate ErrorCode values found"


def test_error_codes_namespaced():
    """All codes must follow the domain.name pattern."""
    for code in ErrorCode:
        parts = code.value.split(".")
        assert len(parts) == 2, f"{code.name} = '{code.value}' is not namespaced (expected 'domain.code')"
        domain, name = parts
        assert domain and name, f"{code.name} has empty domain or name"
