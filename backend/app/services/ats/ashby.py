"""Ashby ATS adapter.

URL pattern: jobs.ashbyhq.com/[company]/[uuid]
Ashby embeds the application form directly on the job page.
Some jobs redirect to a separate /application page with a full form.
"""
import re

from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField

_APPLY_SELECTORS = [
    "a:has-text('Apply for this job')",
    "button:has-text('Apply')",
    "[data-testid='apply-button']",
    "a[href*='/application']",
]


class AshbyAdapter:
    ats_name = "ashby"
    url_patterns = [
        re.compile(r"jobs\.ashbyhq\.com", re.IGNORECASE),
        re.compile(r"ashbyhq\.com", re.IGNORECASE),
    ]

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        """Navigate to the application form if not already there."""
        current_url = await browser.get_current_url() or ""

        # Already on the application page
        if "/application" in current_url:
            return

        # Try clicking the apply button to get to the form
        for selector in _APPLY_SELECTORS:
            if await browser.has_element(selector):
                try:
                    await browser.click_next()
                    return
                except Exception:
                    continue

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field  # Ashby labels are clean and consistent

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None  # Ashby shows confirmation by page content
