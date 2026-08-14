"""Playwright implementation of BrowserAutomationAdapter.

Uses the pre-installed Chromium at PLAYWRIGHT_BROWSERS_PATH.
Never import this directly in domain logic — depend on the BrowserAutomationAdapter Protocol.
"""
import os
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Frame

from app.services.browser.adapter import (
    BrowserAutomationAdapter,
    RawForm, RawFormField, RawFormSection,
    PageState, SubmissionResult,
)
from app.services.browser.form_extractor import (
    FORM_EXTRACTOR_JS, CONFIRMATION_DETECTOR_JS,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_CHROMIUM_PATH = os.environ.get(
    "PLAYWRIGHT_CHROMIUM_EXECUTABLE",
    "/opt/pw-browsers/chromium/chrome",
)

# Fallback paths (different Playwright versions use different subpaths)
_CHROMIUM_CANDIDATES = [
    "/opt/pw-browsers/chromium/chrome",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
]


def _find_chromium() -> str:
    """Return the first valid Chromium executable path."""
    # env override wins
    env = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if env and os.path.isfile(env):
        return env
    for candidate in _CHROMIUM_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return _CHROMIUM_PATH  # let Playwright resolve it


class PlaywrightAdapter:
    """Concrete browser automation backed by Playwright + pre-installed Chromium."""

    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self._headless = headless
        self._slow_mo = slow_mo
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._active_frame: Frame | None = None  # set when inside an iframe

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def __aenter__(self) -> "PlaywrightAdapter":
        self._playwright = await async_playwright().start()
        chromium_path = _find_chromium()
        logger.info("browser_launch", chromium=chromium_path)
        self._browser = await self._playwright.chromium.launch(
            executable_path=chromium_path,
            headless=self._headless,
            slow_mo=self._slow_mo,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def close(self) -> None:
        if self._page:
            await self._page.close()
            self._page = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    # ── Navigation ────────────────────────────────────────────────────────────

    async def open_url(self, url: str) -> PageState:
        assert self._page, "call __aenter__ first"
        response = await self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        title = await self._page.title()
        logger.info("browser_navigate", url=url, status=response.status if response else None)
        return PageState(url=self._page.url, title=title)

    # ── Form discovery ────────────────────────────────────────────────────────

    async def discover_form(self) -> RawForm:
        assert self._page, "call __aenter__ first"
        target = self._active_frame or self._page
        result = await target.evaluate(FORM_EXTRACTOR_JS)
        raw_fields = result.get("fields", [])

        fields: list[RawFormField] = []
        for f in raw_fields:
            fields.append(RawFormField(
                field_id=f.get("field_id", ""),
                name=f.get("name", ""),
                label=f.get("label", ""),
                field_type=f.get("field_type", "text"),
                is_required=bool(f.get("is_required", False)),
                options=f.get("options"),
                placeholder=f.get("placeholder"),
                css_selector=f.get("css_selector", ""),
                section_title=f.get("section_title"),
                aria_label=f.get("aria_label"),
            ))

        # Group by section_title
        section_map: dict[str | None, list[RawFormField]] = {}
        for field in fields:
            key = field.section_title
            section_map.setdefault(key, []).append(field)

        sections = [
            RawFormSection(title=title, fields=section_fields)
            for title, section_fields in section_map.items()
        ]

        logger.info("form_discovered", fields=len(fields), sections=len(sections))
        return RawForm(
            sections=sections,
            fields=fields,
            page_title=result.get("page_title"),
            submit_button_selector=result.get("submit_button_selector"),
            form_action=result.get("form_action"),
        )

    # ── Field interaction ──────────────────────────────────────────────────────

    async def fill_text(self, css_selector: str, value: str) -> bool:
        assert self._page
        try:
            target = self._active_frame or self._page
            await target.locator(css_selector).first.fill(value, timeout=5_000)
            return True
        except Exception as exc:
            logger.warning("fill_text_failed", selector=css_selector, error=str(exc))
            return False

    async def select_option(self, css_selector: str, value: str) -> bool:
        assert self._page
        try:
            target = self._active_frame or self._page
            locator = target.locator(css_selector).first
            try:
                await locator.select_option(value=value, timeout=5_000)
            except Exception:
                await locator.select_option(label=value, timeout=5_000)
            return True
        except Exception as exc:
            logger.warning("select_option_failed", selector=css_selector, value=value, error=str(exc))
            return False

    async def check_checkbox(self, css_selector: str, checked: bool) -> bool:
        assert self._page
        try:
            target = self._active_frame or self._page
            locator = target.locator(css_selector).first
            if checked:
                await locator.check(timeout=5_000)
            else:
                await locator.uncheck(timeout=5_000)
            return True
        except Exception as exc:
            logger.warning("check_checkbox_failed", selector=css_selector, error=str(exc))
            return False

    async def upload_file(self, css_selector: str, file_path: str) -> bool:
        assert self._page
        try:
            target = self._active_frame or self._page
            await target.locator(css_selector).first.set_input_files(file_path, timeout=10_000)
            return True
        except Exception as exc:
            logger.warning("upload_file_failed", selector=css_selector, path=file_path, error=str(exc))
            return False

    # ── Navigation actions ────────────────────────────────────────────────────

    async def click_submit(self) -> PageState:
        assert self._page
        submit_url = self._page.url
        try:
            async with self._page.expect_navigation(wait_until="domcontentloaded", timeout=15_000):
                await self._page.locator("button[type='submit'], input[type='submit']").first.click(timeout=10_000)
        except Exception:
            # Navigation may have already completed or the server returned in-place
            await self._page.wait_for_load_state("domcontentloaded", timeout=15_000)
        title = await self._page.title()
        return PageState(url=self._page.url, title=title)

    async def click_next(self) -> PageState:
        assert self._page
        async with self._page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
            # Common "Next" button patterns
            for selector in ["button:has-text('Next')", "button:has-text('Continue')", "[type='submit']"]:
                try:
                    await self._page.locator(selector).first.click(timeout=5_000)
                    break
                except Exception:
                    continue
        title = await self._page.title()
        return PageState(url=self._page.url, title=title)

    # ── Page inspection ────────────────────────────────────────────────────────

    async def capture_screenshot(self) -> bytes:
        assert self._page
        return await self._page.screenshot(full_page=True)

    async def get_page_text(self) -> str:
        assert self._page
        return await self._page.inner_text("body")

    async def is_confirmation_page(self) -> bool:
        result = await self._page.evaluate(CONFIRMATION_DETECTOR_JS)
        return bool(result.get("is_confirmation", False))

    async def extract_confirmation_id(self) -> str | None:
        result = await self._page.evaluate(CONFIRMATION_DETECTOR_JS)
        return result.get("confirmation_id")

    async def has_element(self, selector: str) -> bool:
        assert self._page
        try:
            target = self._active_frame or self._page
            count = await target.locator(selector).count()
            return count > 0
        except Exception:
            return False

    async def switch_to_frame(self, frame_selector: str) -> bool:
        """Switch context into an iframe matched by CSS selector. Returns True on success."""
        assert self._page
        try:
            element = await self._page.query_selector(frame_selector)
            if not element:
                return False
            frame = await element.content_frame()
            if not frame:
                return False
            self._active_frame = frame
            logger.info("switched_to_frame", selector=frame_selector)
            return True
        except Exception as exc:
            logger.warning("switch_to_frame_failed", selector=frame_selector, error=str(exc))
            return False

    async def switch_to_main_frame(self) -> None:
        """Return context to the main page (exit iframe)."""
        self._active_frame = None

    async def get_current_url(self) -> str | None:
        if self._page:
            return self._page.url
        return None
