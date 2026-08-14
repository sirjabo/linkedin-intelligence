"""SmartRecruiters ATS adapter.

URL pattern: careers.smartrecruiters.com/[company]
"""
import re
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


class SmartRecruitersAdapter:
    ats_name = "smartrecruiters"
    url_patterns = [
        re.compile(r"smartrecruiters\.com", re.I),
        re.compile(r"careers\.smartrecruiters", re.I),
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
