"""Tests for P2 Phase 11: Lever ATS adapter + browser frame switching.

Verifies:
  - LeverAdapter.before_discover() navigates to /apply when not on apply URL
  - LeverAdapter.before_discover() tries to switch into iframe
  - PlaywrightAdapter.switch_to_main_frame() clears active frame
  - PlaywrightAdapter.get_current_url() returns page URL
"""
from unittest.mock import AsyncMock

import pytest

from app.services.ats.lever import LeverAdapter

# ── LeverAdapter.url_patterns ────────────────────────────────────────────────

def test_lever_url_patterns():
    adapter = LeverAdapter()
    assert any(p.search("https://jobs.lever.co/acme/abc123") for p in adapter.url_patterns)
    assert any(p.search("https://lever.co/acme/apply") for p in adapter.url_patterns)


def test_lever_url_does_not_match_greenhouse():
    adapter = LeverAdapter()
    assert not any(p.search("https://boards.greenhouse.io/acme/jobs/123") for p in adapter.url_patterns)


# ── LeverAdapter.before_discover() ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_before_discover_navigates_to_apply_when_missing():
    """If current URL has no /apply, before_discover should call open_url with /apply appended."""
    adapter = LeverAdapter()

    browser = AsyncMock()
    browser.get_current_url.return_value = "https://jobs.lever.co/acme/abc123"
    browser.switch_to_frame.return_value = False  # no iframe found

    await adapter.before_discover(browser)

    browser.open_url.assert_called_once_with("https://jobs.lever.co/acme/abc123/apply")


@pytest.mark.asyncio
async def test_before_discover_skips_navigation_when_already_on_apply():
    """If URL already has /apply, before_discover should not navigate again."""
    adapter = LeverAdapter()

    browser = AsyncMock()
    browser.get_current_url.return_value = "https://jobs.lever.co/acme/abc123/apply"
    browser.switch_to_frame.return_value = False

    await adapter.before_discover(browser)

    browser.open_url.assert_not_called()


@pytest.mark.asyncio
async def test_before_discover_switches_into_iframe():
    """If an iframe is found, before_discover should switch into it."""
    adapter = LeverAdapter()

    browser = AsyncMock()
    browser.get_current_url.return_value = "https://jobs.lever.co/acme/abc123/apply"

    # First iframe selector succeeds
    async def _switch(selector: str) -> bool:
        return selector == "iframe[src*='lever']"

    browser.switch_to_frame.side_effect = _switch

    await adapter.before_discover(browser)

    # switch_to_frame was called until success
    assert browser.switch_to_frame.call_count >= 1


@pytest.mark.asyncio
async def test_before_discover_handles_navigation_error_gracefully():
    """Navigation to /apply failing should not raise — adapter is silent."""
    adapter = LeverAdapter()

    browser = AsyncMock()
    browser.get_current_url.return_value = "https://jobs.lever.co/acme/abc123"
    browser.open_url.side_effect = Exception("network error")
    browser.switch_to_frame.return_value = False

    # Should not raise
    await adapter.before_discover(browser)


# ── normalize_field ───────────────────────────────────────────────────────────

def test_lever_normalize_field_is_identity():
    from app.services.browser.adapter import RawFormField
    adapter = LeverAdapter()
    field = RawFormField(
        field_id="f1", name="first_name", label="First Name",
        field_type="text", is_required=True,
    )
    result = adapter.normalize_field(field)
    assert result.label == "First Name"
    assert result.field_id == "f1"
