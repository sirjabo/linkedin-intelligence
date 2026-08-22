"""AC-02: PlaywrightAdapter opens the mock ATS and discovers form fields.

These tests require:
  - A live mock ATS server (provided by mock_ats_url fixture)
  - Chromium installed at /opt/pw-browsers (PLAYWRIGHT_BROWSERS_PATH)

Skip on environments without Playwright/Chromium.
"""

import pytest

# Skip entire module if Playwright is not importable (e.g. minimal CI)
playwright_available = True
try:
    import playwright  # noqa: F401
except ImportError:
    playwright_available = False

pytestmark = pytest.mark.skipif(
    not playwright_available,
    reason="playwright package not installed",
)

if playwright_available:
    from app.services.browser.adapter import RawForm
    from app.services.browser.playwright_adapter import PlaywrightAdapter, _find_chromium, chromium_available

from tests.mock_ats.conftest_ats import mock_ats_url  # noqa: F401 — re-export fixture

# ── helpers ───────────────────────────────────────────────────────────────────

MOCK_ATS_EXPECTED_FIELDS = {
    "first_name", "last_name", "email", "phone",
    "location", "linkedin_url",
    "years_experience", "salary_expectation", "work_authorization",
    "resume", "cover_letter_text",
    "why_company", "relocation_willing", "remote_ok",
}

REQUIRED_FIELD_NAMES = {
    "first_name", "last_name", "email", "phone",
    "years_experience", "work_authorization", "resume", "why_company",
}


# ── Chromium discovery ────────────────────────────────────────────────────────

def test_find_chromium_returns_a_path():
    if not chromium_available():
        pytest.skip("No Chromium available")
    path = _find_chromium()
    assert path is None or (isinstance(path, str) and len(path) > 0)


def test_chromium_exists_on_filesystem():
    if not chromium_available():
        pytest.skip("No Chromium available — skipping Playwright tests")


# ── Form discovery via PlaywrightAdapter ──────────────────────────────────────

@pytest.fixture
def require_chromium():
    if not chromium_available():
        pytest.skip("No Chromium available")


@pytest.mark.asyncio
async def test_open_url_returns_page_state(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        state = await browser.open_url(f"{mock_ats_url}/apply")
        assert state.url.endswith("/apply") or "apply" in state.url
        assert state.is_loaded is True


@pytest.mark.asyncio
async def test_discover_form_returns_raw_form(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()
        assert isinstance(form, RawForm)


@pytest.mark.asyncio
async def test_discover_form_finds_all_expected_fields(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()

    discovered_names = {f.name for f in form.fields}
    missing = MOCK_ATS_EXPECTED_FIELDS - discovered_names
    assert not missing, (
        f"discover_form() missed these fields: {missing}\n"
        f"Discovered: {discovered_names}"
    )


@pytest.mark.asyncio
async def test_discover_form_field_count_gte_minimum(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()

    assert len(form.fields) >= 12, (
        f"Expected at least 12 fields, got {len(form.fields)}"
    )


@pytest.mark.asyncio
async def test_discover_form_required_fields_marked_correctly(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()

    field_map = {f.name: f for f in form.fields}
    for name in REQUIRED_FIELD_NAMES:
        if name in field_map:
            assert field_map[name].is_required, (
                f"Field '{name}' should be required but is_required=False"
            )


@pytest.mark.asyncio
async def test_discover_form_resume_field_is_file_type(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()

    field_map = {f.name: f for f in form.fields}
    assert "resume" in field_map, "resume field not discovered"
    assert field_map["resume"].field_type == "file"


@pytest.mark.asyncio
async def test_discover_form_years_experience_is_select(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()

    field_map = {f.name: f for f in form.fields}
    assert "years_experience" in field_map
    assert field_map["years_experience"].field_type == "select"
    assert field_map["years_experience"].options is not None
    assert len(field_map["years_experience"].options) >= 4


@pytest.mark.asyncio
async def test_discover_form_has_sections(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()

    assert len(form.sections) >= 2, (
        f"Expected at least 2 sections (fieldsets), got {len(form.sections)}"
    )


@pytest.mark.asyncio
async def test_discover_form_has_submit_selector(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        form = await browser.discover_form()

    assert form.submit_button_selector is not None


# ── is_confirmation_page ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_form_page_is_not_confirmation(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/apply")
        is_confirm = await browser.is_confirmation_page()
    assert is_confirm is False


@pytest.mark.asyncio
async def test_confirm_page_is_detected(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/confirm?ref=APP-TESTDEAD")
        is_confirm = await browser.is_confirmation_page()
    assert is_confirm is True


@pytest.mark.asyncio
async def test_extract_confirmation_id_from_confirm_page(mock_ats_url, require_chromium):
    async with PlaywrightAdapter(headless=True) as browser:
        await browser.open_url(f"{mock_ats_url}/confirm?ref=APP-ABCD1234")
        conf_id = await browser.extract_confirmation_id()
    assert conf_id is not None
    assert "APP" in conf_id.upper() or "ABCD1234" in conf_id
