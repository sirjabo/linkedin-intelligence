"""AC-08: ATSRegistry.detect() returns the correct adapter class for each URL.

Tests are pure unit tests — no browser, no server.
"""
import pytest

from app.services.ats.registry import ATSRegistry, detect_ats
from app.services.ats.greenhouse import GreenhouseAdapter
from app.services.ats.lever import LeverAdapter
from app.services.ats.ashby import AshbyAdapter
from app.services.ats.workday import WorkdayAdapter
from app.services.ats.smart_recruiters import SmartRecruitersAdapter
from app.services.ats.generic import GenericFormAgent


registry = ATSRegistry()


@pytest.mark.parametrize("url,expected_class", [
    # Greenhouse
    ("https://boards.greenhouse.io/acme/jobs/12345", GreenhouseAdapter),
    ("https://greenhouse.io/acme/jobs/apply", GreenhouseAdapter),
    # Lever
    ("https://jobs.lever.co/acme/abc-def/apply", LeverAdapter),
    ("https://lever.co/acme/apply", LeverAdapter),
    # Ashby
    ("https://jobs.ashbyhq.com/acme/position-123", AshbyAdapter),
    ("https://ashbyhq.com/acme/apply", AshbyAdapter),
    # Workday
    ("https://acme.myworkdayjobs.com/en-US/careers/job/12345", WorkdayAdapter),
    ("https://acme.workday.com/apply", WorkdayAdapter),
    # SmartRecruiters
    ("https://careers.smartrecruiters.com/Acme/apply", SmartRecruitersAdapter),
    ("https://www.smartrecruiters.com/Acme/application", SmartRecruitersAdapter),
    # Generic fallback
    ("https://jobs.example.com/apply/data-engineer", GenericFormAgent),
    ("https://careers.acme.io/position/42", GenericFormAgent),
    ("http://localhost:8888/apply", GenericFormAgent),
])
def test_detect_ats_returns_correct_adapter(url, expected_class):
    adapter = detect_ats(url)
    assert isinstance(adapter, expected_class), (
        f"Expected {expected_class.__name__} for URL {url!r}, "
        f"got {type(adapter).__name__}"
    )


def test_registry_detect_method_matches_detect_ats():
    url = "https://boards.greenhouse.io/acme/jobs/1"
    assert type(registry.detect(url)) == type(detect_ats(url))


def test_registry_supported_ats_lists_all_named_adapters():
    supported = registry.supported_ats
    assert "greenhouse" in supported
    assert "lever" in supported
    assert "ashby" in supported
    assert "workday" in supported
    assert "smartrecruiters" in supported
    # Generic is a fallback, not a named supported ATS
    assert "generic" not in supported


def test_generic_has_empty_url_patterns():
    agent = GenericFormAgent()
    assert agent.url_patterns == []


def test_generic_confidence_penalty_is_positive():
    agent = GenericFormAgent()
    assert agent.CONFIDENCE_PENALTY > 0


def test_adapters_have_required_attributes():
    for adapter in [
        GreenhouseAdapter(),
        LeverAdapter(),
        AshbyAdapter(),
        WorkdayAdapter(),
        SmartRecruitersAdapter(),
        GenericFormAgent(),
    ]:
        assert hasattr(adapter, "ats_name"), f"{type(adapter).__name__} missing ats_name"
        assert hasattr(adapter, "url_patterns"), f"{type(adapter).__name__} missing url_patterns"
        assert hasattr(adapter, "normalize_field"), f"{type(adapter).__name__} missing normalize_field"
        assert hasattr(adapter, "submit"), f"{type(adapter).__name__} missing submit"
