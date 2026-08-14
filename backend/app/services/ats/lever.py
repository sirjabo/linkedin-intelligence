"""Lever ATS adapter.

URL pattern: jobs.lever.co/[company]/[uuid]
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
        pass  # Lever forms are usually immediately accessible

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field  # Lever labels are already clean

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None  # use generic detector
