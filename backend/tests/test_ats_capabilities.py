"""Tests for the ATS capability matrix and adapter fixes.

All tests are pure unit tests — no browser, no server, no DB.
Covers:
  - ATSCapabilities declarations for every adapter
  - Fresh-instance isolation (registry no longer returns singletons)
  - browser.click() is declared on the protocol
  - Greenhouse no longer uses fill_text for cookie banners
  - Workday / Ashby no longer use click_next for Apply button
  - SmartRecruiters URL patterns include jobs.smartrecruiters.com
  - Lever validation errors are stored and logged after failed submit
  - GenericFormAgent CONFIDENCE_PENALTY matches capabilities.confidence_penalty
"""

import pytest

from app.services.ats.adapter import ATSAdapter, ATSCapabilities
from app.services.ats.ashby import AshbyAdapter
from app.services.ats.generic import GenericFormAgent
from app.services.ats.greenhouse import GreenhouseAdapter
from app.services.ats.lever import LeverAdapter
from app.services.ats.registry import ATSRegistry, detect_ats
from app.services.ats.smart_recruiters import SmartRecruitersAdapter
from app.services.ats.workday import WorkdayAdapter
from app.services.browser.adapter import BrowserAutomationAdapter

# ── Helpers ───────────────────────────────────────────────────────────────────

class _FakeBrowser:
    """Minimal browser stub that records method calls."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._url = "https://jobs.lever.co/acme/uuid-123"
        self._has: dict[str, bool] = {}
        self._page_text = ""

    async def open_url(self, url: str):
        self.calls.append(("open_url", url))
        self._url = url
        from app.services.browser.adapter import PageState
        return PageState(url=url, title="Page")

    async def get_current_url(self) -> str | None:
        return self._url

    async def get_page_text(self) -> str:
        return self._page_text

    async def has_element(self, selector: str) -> bool:
        return self._has.get(selector, False)

    async def click(self, selector: str) -> bool:
        self.calls.append(("click", selector))
        return True

    async def fill_text(self, selector: str, value: str) -> bool:
        self.calls.append(("fill_text", selector, value))
        return True

    async def click_next(self):
        self.calls.append(("click_next",))
        from app.services.browser.adapter import PageState
        return PageState(url=self._url, title="Page")

    async def click_submit(self):
        self.calls.append(("click_submit",))
        from app.services.browser.adapter import PageState
        return PageState(url=self._url, title="Done")

    async def is_confirmation_page(self) -> bool:
        return True

    async def switch_to_frame(self, selector: str) -> bool:
        self.calls.append(("switch_to_frame", selector))
        return False

    async def switch_to_main_frame(self) -> None:
        pass

    async def discover_form(self):
        from app.services.browser.adapter import RawForm
        return RawForm()

    async def capture_screenshot(self) -> bytes:
        return b""

    async def extract_confirmation_id(self) -> str | None:
        return None

    async def check_checkbox(self, selector: str, checked: bool) -> bool:
        return True

    async def select_option(self, selector: str, value: str) -> bool:
        return True

    async def upload_file(self, selector: str, file_path: str) -> bool:
        return True

    async def close(self) -> None:
        pass

    async def detect_page_blocker(self):
        return None

    async def wait_for_spa_ready(self, wait_ms: int = 10_000) -> bool:
        return True

    async def discover_form_in_iframes(self):
        return None

    async def handle_custom_select(self, container_selector: str, value: str) -> bool:
        return True

    async def fill_location_autocomplete(self, selector: str, value: str) -> bool:
        return True

    async def upload_file_hidden(self, label_selector: str, file_path: str) -> bool:
        return True


# ── ATSCapabilities dataclass ─────────────────────────────────────────────────

def test_capabilities_is_frozen():
    caps = ATSCapabilities()
    with pytest.raises((AttributeError, TypeError)):
        caps.eeo_detection = True  # type: ignore[misc]


def test_capabilities_defaults():
    caps = ATSCapabilities()
    assert caps.eeo_detection is False
    assert caps.multi_page is False
    assert caps.max_form_pages == 1
    assert caps.iframe_support is False
    assert caps.custom_questions is False
    assert caps.requires_apply_click is False
    assert caps.has_confirmation_id is False
    assert caps.confidence_penalty == 0.0
    assert caps.known_url_patterns == []


# ── Per-adapter capability declarations ───────────────────────────────────────

def test_greenhouse_capabilities():
    caps = GreenhouseAdapter().capabilities
    assert caps.eeo_detection is True
    assert caps.multi_page is True
    assert caps.max_form_pages >= 5
    assert caps.has_confirmation_id is True


def test_lever_capabilities():
    caps = LeverAdapter().capabilities
    assert caps.iframe_support is True
    assert caps.custom_questions is True


def test_workday_capabilities():
    caps = WorkdayAdapter().capabilities
    assert caps.multi_page is True
    assert caps.max_form_pages >= 10
    assert caps.requires_apply_click is True
    assert caps.has_confirmation_id is True


def test_ashby_capabilities():
    caps = AshbyAdapter().capabilities
    assert caps.requires_apply_click is True


def test_smartrecruiters_capabilities():
    caps = SmartRecruitersAdapter().capabilities
    assert caps.multi_page is True
    assert caps.has_confirmation_id is True


def test_generic_capabilities():
    caps = GenericFormAgent().capabilities
    assert caps.confidence_penalty > 0.0


def test_all_adapters_have_capabilities_property():
    for klass in [GreenhouseAdapter, LeverAdapter, AshbyAdapter, WorkdayAdapter,
                  SmartRecruitersAdapter, GenericFormAgent]:
        adapter = klass()
        assert isinstance(adapter.capabilities, ATSCapabilities), (
            f"{klass.__name__} missing capabilities property"
        )


# ── Registry fresh-instance isolation ─────────────────────────────────────────

def test_detect_ats_returns_fresh_instance_each_call():
    url = "https://boards.greenhouse.io/acme/jobs/1"
    a1 = detect_ats(url)
    a2 = detect_ats(url)
    assert a1 is not a2


def test_detect_ats_fresh_generic_instances():
    url = "https://unknown.example.com/apply"
    g1 = detect_ats(url)
    g2 = detect_ats(url)
    assert g1 is not g2


def test_registry_capabilities_for_known_ats():
    registry = ATSRegistry()
    caps = registry.capabilities_for("https://boards.greenhouse.io/acme/jobs/1")
    assert caps.eeo_detection is True


def test_registry_capabilities_for_unknown_url():
    registry = ATSRegistry()
    caps = registry.capabilities_for("https://jobs.example.com/apply")
    assert caps.confidence_penalty > 0.0


# ── SmartRecruiters URL pattern fix ───────────────────────────────────────────

def test_smartrecruiters_matches_jobs_subdomain():
    adapter = detect_ats("https://jobs.smartrecruiters.com/Acme/job-123")
    assert isinstance(adapter, SmartRecruitersAdapter)


def test_smartrecruiters_matches_careers_subdomain():
    adapter = detect_ats("https://careers.smartrecruiters.com/Acme/job-123")
    assert isinstance(adapter, SmartRecruitersAdapter)


def test_smartrecruiters_matches_www():
    adapter = detect_ats("https://www.smartrecruiters.com/Acme/apply")
    assert isinstance(adapter, SmartRecruitersAdapter)


# ── Greenhouse cookie banner uses click() not fill_text() ─────────────────────

async def test_greenhouse_cookie_banner_uses_click():
    adapter = GreenhouseAdapter()
    browser = _FakeBrowser()
    browser._page_text = "Please accept our cookie policy"
    await adapter.before_discover(browser)
    call_names = [c[0] for c in browser.calls]
    assert "fill_text" not in call_names, "Greenhouse should not use fill_text for cookie banner"


async def test_greenhouse_no_banner_no_click():
    adapter = GreenhouseAdapter()
    browser = _FakeBrowser()
    browser._page_text = "Apply for Backend Engineer at Acme"
    await adapter.before_discover(browser)
    # no banner — no interaction expected
    assert browser.calls == []


# ── Workday Apply button uses click() not click_next() ───────────────────────

async def test_workday_apply_uses_click_not_click_next():
    adapter = WorkdayAdapter()
    browser = _FakeBrowser()
    apply_selector = "[data-automation-id='applyButton']"
    browser._has = {apply_selector: True}
    browser._url = "https://acme.myworkdayjobs.com/careers/job/123"
    await adapter.before_discover(browser)
    call_names = [c[0] for c in browser.calls]
    assert "click_next" not in call_names, "Workday should not use click_next for Apply button"
    assert "click" in call_names


async def test_workday_no_apply_button_no_action():
    adapter = WorkdayAdapter()
    browser = _FakeBrowser()
    browser._has = {}
    await adapter.before_discover(browser)
    assert browser.calls == []


# ── Ashby Apply button uses click() not click_next() ─────────────────────────

async def test_ashby_apply_uses_click_not_click_next():
    adapter = AshbyAdapter()
    browser = _FakeBrowser()
    browser._url = "https://jobs.ashbyhq.com/acme/position"
    apply_selector = "a:has-text('Apply for this job')"
    browser._has = {apply_selector: True}
    await adapter.before_discover(browser)
    call_names = [c[0] for c in browser.calls]
    assert "click_next" not in call_names, "Ashby should not use click_next for Apply button"
    assert "click" in call_names


async def test_ashby_already_on_application_page_no_click():
    adapter = AshbyAdapter()
    browser = _FakeBrowser()
    browser._url = "https://jobs.ashbyhq.com/acme/position/application"
    await adapter.before_discover(browser)
    assert browser.calls == []


# ── SmartRecruiters cookie dismissal uses click() ────────────────────────────

async def test_smartrecruiters_cookie_uses_click_not_fill_text():
    adapter = SmartRecruitersAdapter()
    browser = _FakeBrowser()
    cookie_selector = "button:has-text('Accept')"
    browser._has = {cookie_selector: True}
    await adapter.before_discover(browser)
    call_names = [c[0] for c in browser.calls]
    assert "fill_text" not in call_names, "SmartRecruiters should not use fill_text for cookie banner"
    assert "click" in call_names


# ── Lever validation errors surface after failed submit ───────────────────────

async def test_lever_stores_validation_errors_on_failure():
    adapter = LeverAdapter()
    browser = _FakeBrowser()

    # Override is_confirmation_page to simulate failure
    async def fail_confirm():
        return False
    browser.is_confirmation_page = fail_confirm  # type: ignore[method-assign]

    # Provide page text with validation error content
    browser._page_text = "This field is required\nPlease enter a valid email"

    result = await adapter.submit(browser)
    assert result is False
    assert hasattr(adapter, "last_validation_errors")
    assert len(adapter.last_validation_errors) > 0


async def test_lever_no_validation_errors_on_success():
    adapter = LeverAdapter()
    browser = _FakeBrowser()
    # Default is_confirmation_page returns True
    result = await adapter.submit(browser)
    assert result is True
    assert hasattr(adapter, "last_validation_errors")
    assert adapter.last_validation_errors == []


# ── GenericFormAgent CONFIDENCE_PENALTY consistency ───────────────────────────

def test_generic_confidence_penalty_matches_capabilities():
    agent = GenericFormAgent()
    assert agent.capabilities.confidence_penalty == agent.CONFIDENCE_PENALTY


def test_generic_confidence_penalty_is_nonzero():
    assert GenericFormAgent.CONFIDENCE_PENALTY > 0.0


# ── BrowserAutomationAdapter protocol has click() ────────────────────────────

def test_browser_protocol_has_click():
    assert hasattr(BrowserAutomationAdapter, "click")


def test_fake_browser_satisfies_protocol():
    browser = _FakeBrowser()
    assert isinstance(browser, BrowserAutomationAdapter)


# ── Protocol conformance for all adapters ─────────────────────────────────────

def test_all_adapters_satisfy_ats_protocol():
    for klass in [GreenhouseAdapter, LeverAdapter, AshbyAdapter, WorkdayAdapter,
                  SmartRecruitersAdapter, GenericFormAgent]:
        adapter = klass()
        assert isinstance(adapter, ATSAdapter), (
            f"{klass.__name__} does not satisfy ATSAdapter protocol"
        )
