"""Tests for P3 Phases 15-16: Workday and SmartRecruiters adapters.

Verifies:
  - WorkdayAdapter.url_patterns matches Workday URLs
  - WorkdayAdapter.before_discover() clicks Apply button when found
  - WorkdayAdapter.normalize_field() prefers aria_label over label
  - SmartRecruitersAdapter.url_patterns matches SmartRecruiters URLs
  - SmartRecruitersAdapter.before_discover() tries cookie banner + apply
  - AshbyAdapter.before_discover() navigates to /application URL
"""
import pytest
from unittest.mock import AsyncMock

from app.services.ats.workday import WorkdayAdapter
from app.services.ats.smart_recruiters import SmartRecruitersAdapter
from app.services.ats.ashby import AshbyAdapter
from app.services.browser.adapter import RawFormField


# ── WorkdayAdapter ────────────────────────────────────────────────────────────

def test_workday_url_patterns():
    adapter = WorkdayAdapter()
    assert any(p.search("https://acme.wd1.myworkdayjobs.com/en-US/acme/job/123") for p in adapter.url_patterns)
    assert any(p.search("https://wd3.myworkdayjobs.com/BigCorp/job/123") for p in adapter.url_patterns)


def test_workday_url_does_not_match_greenhouse():
    adapter = WorkdayAdapter()
    assert not any(p.search("https://boards.greenhouse.io/company") for p in adapter.url_patterns)


@pytest.mark.asyncio
async def test_workday_before_discover_clicks_apply():
    adapter = WorkdayAdapter()
    browser = AsyncMock()

    async def _has(selector: str) -> bool:
        return "applyButton" in selector or "Apply Now" in selector

    browser.has_element.side_effect = _has
    browser.click.return_value = True

    await adapter.before_discover(browser)
    browser.click.assert_called_once()
    browser.click_next.assert_not_called()


@pytest.mark.asyncio
async def test_workday_before_discover_no_apply_button():
    """If no Apply button found, before_discover should not raise."""
    adapter = WorkdayAdapter()
    browser = AsyncMock()
    browser.has_element.return_value = False

    await adapter.before_discover(browser)
    browser.click_next.assert_not_called()


def test_workday_normalize_field_prefers_aria_label():
    adapter = WorkdayAdapter()
    field = RawFormField(
        field_id="f1", name="fname", label="First Name",
        field_type="text", is_required=True,
        aria_label="Legal First Name",
    )
    result = adapter.normalize_field(field)
    assert result.label == "Legal First Name"


def test_workday_normalize_field_falls_back_to_label():
    adapter = WorkdayAdapter()
    field = RawFormField(
        field_id="f2", name="lname", label="Last Name",
        field_type="text", is_required=True, aria_label=None,
    )
    result = adapter.normalize_field(field)
    assert result.label == "Last Name"


# ── SmartRecruitersAdapter ───────────────────────────────────────────────────

def test_smartrecruiters_url_patterns():
    adapter = SmartRecruitersAdapter()
    assert any(p.search("https://careers.smartrecruiters.com/Acme/job123") for p in adapter.url_patterns)
    assert any(p.search("https://smartrecruiters.com/jobs/123") for p in adapter.url_patterns)


def test_smartrecruiters_url_does_not_match_lever():
    adapter = SmartRecruitersAdapter()
    assert not any(p.search("https://jobs.lever.co/company/123") for p in adapter.url_patterns)


@pytest.mark.asyncio
async def test_smartrecruiters_before_discover_no_error():
    """before_discover should not raise even if no banners or apply buttons found."""
    adapter = SmartRecruitersAdapter()
    browser = AsyncMock()
    browser.has_element.return_value = False

    await adapter.before_discover(browser)


# ── AshbyAdapter ──────────────────────────────────────────────────────────────

def test_ashby_url_patterns():
    adapter = AshbyAdapter()
    assert any(p.search("https://jobs.ashbyhq.com/acme/abc-123") for p in adapter.url_patterns)


@pytest.mark.asyncio
async def test_ashby_before_discover_skips_when_already_on_application():
    adapter = AshbyAdapter()
    browser = AsyncMock()
    browser.get_current_url.return_value = "https://jobs.ashbyhq.com/acme/abc-123/application"

    await adapter.before_discover(browser)
    browser.click_next.assert_not_called()
    browser.has_element.assert_not_called()


@pytest.mark.asyncio
async def test_ashby_before_discover_clicks_apply():
    adapter = AshbyAdapter()
    browser = AsyncMock()
    browser.get_current_url.return_value = "https://jobs.ashbyhq.com/acme/abc-123"

    async def _has(selector: str) -> bool:
        return "Apply" in selector

    browser.has_element.side_effect = _has
    browser.click.return_value = True

    await adapter.before_discover(browser)
    browser.click.assert_called_once()
    browser.click_next.assert_not_called()
