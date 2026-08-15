"""Lever ATS adapter.

URL pattern: jobs.lever.co/[company]/[uuid]
Lever job pages embed the application form in an iframe or behind an /apply sub-URL.
"""
import re
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


class LeverAdapter:
    ats_name = "lever"
    url_patterns = [
        re.compile(r"jobs\.lever\.co", re.I),
        re.compile(r"lever\.co/.*apply", re.I),
    ]

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        """Navigate to the /apply page if not already there, or enter the iframe."""
        current_url = await browser.get_current_url() or ""

        # If we're on a listing page (not yet on /apply), navigate there
        if "/apply" not in current_url:
            apply_url = current_url.rstrip("/") + "/apply"
            try:
                await browser.open_url(apply_url)
            except Exception:
                pass  # If /apply doesn't exist, stay on current page

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

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None  # use generic detector
