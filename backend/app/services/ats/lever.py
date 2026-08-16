"""Lever ATS adapter.

URL pattern: jobs.lever.co/[company]/[uuid]
Lever job pages embed the application form in an iframe or behind an /apply sub-URL.
"""
import contextlib
import re

from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField

# Lever inline validation error selectors
_VALIDATION_ERROR_SELECTORS = [
    ".application-field .error",
    ".field-error",
    "[class*='error-message']",
    "[class*='validation-error']",
    ".error:not([aria-hidden='true'])",
]

# Custom question section markers in Lever forms
_CUSTOM_QUESTION_SELECTORS = [
    "[data-qa='additional-information']",
    ".custom-question",
    "[class*='custom-question']",
    "fieldset.lever-question",
]


class LeverAdapter:
    ats_name = "lever"
    url_patterns = [
        re.compile(r"jobs\.lever\.co", re.IGNORECASE),
        re.compile(r"lever\.co/.*apply", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        self.custom_question_labels: list[str] = []
        self.validation_errors: list[str] = []

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

        # Extract custom question labels for the orchestrator
        await self._extract_custom_questions(browser)

    async def _extract_custom_questions(self, browser: BrowserAutomationAdapter) -> None:
        """Collect labels of custom question fields so they can be surfaced to the user."""
        try:
            page_text = await browser.get_page_text()
            # Lever custom questions often start with a number or are in a "Additional information"
            # section; collect lines that look like questions
            for line in page_text.splitlines():
                line = line.strip()
                if line and line.endswith("?") and len(line) > 10 and line not in self.custom_question_labels:
                    self.custom_question_labels.append(line)
        except Exception:
            pass

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field  # Lever labels are already clean

    async def collect_validation_errors(self, browser: BrowserAutomationAdapter) -> list[str]:
        """After a failed submit, scrape inline validation error messages."""
        self.validation_errors = []
        try:
            page_text = await browser.get_page_text()
            # Look for error lines in page text — simple heuristic
            for line in page_text.splitlines():
                stripped = line.strip()
                if stripped and any(
                    kw in stripped.lower()
                    for kw in ("required", "invalid", "must be", "cannot be", "error")
                ) and len(stripped) < 200:
                    self.validation_errors.append(stripped)
        except Exception:
            pass
        return self.validation_errors

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        success = await browser.is_confirmation_page()
        if not success:
            await self.collect_validation_errors(browser)
        return success

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None  # use generic detector
