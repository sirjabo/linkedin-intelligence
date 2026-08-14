"""Workday ATS adapter.

URL pattern: [company].wd1.myworkdayjobs.com/...
"""
import re
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


class WorkdayAdapter:
    ats_name = "workday"
    url_patterns = [
        re.compile(r"myworkdayjobs\.com", re.I),
        re.compile(r"workday\.com", re.I),
    ]

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        # Workday often requires clicking "Apply" first — handled by orchestrator
        pass

    def normalize_field(self, field: RawFormField) -> RawFormField:
        # Workday uses aria-labels heavily — already captured by extractor
        return field

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return re.compile(r"WD[-]?(\d{7,})", re.I)
