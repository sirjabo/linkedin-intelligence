"""Lever ATS adapter.

URL pattern: jobs.lever.co/[company]/[uuid]
Lever job pages embed the application form in an iframe or behind an /apply sub-URL.
"""
import contextlib
import re

from app.core.logging import get_logger
from app.services.ats.adapter import ATSCapabilities
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField

_log = get_logger(__name__)

_CAPABILITIES = ATSCapabilities(
    iframe_support=True,
    custom_questions=True,
    known_url_patterns=["jobs.lever.co/company/uuid", "lever.co/company/apply"],
)


class LeverAdapter:
    ats_name = "lever"
    url_patterns = [
        re.compile(r"jobs\.lever\.co", re.IGNORECASE),
        re.compile(r"lever\.co/.*apply", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        self.custom_question_labels: list[str] = []
        self.validation_errors: list[str] = []
        self.last_validation_errors: list[str] = []

    @property
    def capabilities(self) -> ATSCapabilities:
        return _CAPABILITIES

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        """Navigate to the /apply page if not already there, or enter the iframe."""
        current_url = await browser.get_current_url() or ""

        # If we're on a listing page (not yet on /apply), navigate there
        if "/apply" not in current_url:
            apply_url = current_url.rstrip("/") + "/apply"
            with contextlib.suppress(Exception):
                await browser.open_url(apply_url)

        # Lever sometimes renders the form inside an <iframe> — switch into it
        for selector in [
            "iframe[src*='lever']",
            "iframe[src*='apply']",
            "iframe.application-form",
            "iframe",
        ]:
            switched = await browser.switch_to_frame(selector)
            if switched:
                break

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field  # Lever labels are already clean

    async def collect_validation_errors(self, browser: BrowserAutomationAdapter) -> list[str]:
        """After a failed submit, scrape inline validation error messages."""
        errors: list[str] = []
        try:
            page_text = await browser.get_page_text()
            for line in page_text.splitlines():
                stripped = line.strip()
                if stripped and any(
                    kw in stripped.lower()
                    for kw in ("required", "invalid", "must be", "cannot be", "error")
                ) and len(stripped) < 200:
                    errors.append(stripped)
        except Exception:
            pass
        if errors:
            _log.warning("lever.validation_errors", count=len(errors), errors=errors[:5])
        return errors

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        success = await browser.is_confirmation_page()
        if not success:
            self.last_validation_errors = await self.collect_validation_errors(browser)
        else:
            self.last_validation_errors = []
        return success

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None  # use generic detector
