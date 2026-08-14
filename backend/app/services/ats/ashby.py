"""Ashby ATS adapter.

URL pattern: jobs.ashbyhq.com/[company]/[uuid]
"""
import re
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


class AshbyAdapter:
    ats_name = "ashby"
    url_patterns = [
        re.compile(r"jobs\.ashbyhq\.com", re.I),
        re.compile(r"ashbyhq\.com", re.I),
    ]

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        pass

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None
