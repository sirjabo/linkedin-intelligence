"""Workday ATS adapter.

URL pattern: [company].wd1.myworkdayjobs.com/...
Workday renders job pages that require clicking "Apply Now" to open the wizard.
The application wizard is a multi-step flow with page-level navigation.
"""
import re

from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField

_APPLY_SELECTORS = [
    "[data-automation-id='applyButton']",
    "[data-automation-id='applyNowButton']",
    "button:has-text('Apply Now')",
    "button:has-text('Apply')",
    "a:has-text('Apply Now')",
    "a:has-text('Apply')",
]

_NEXT_SELECTORS = [
    "button:has-text('Next')",
    "button:has-text('Continue')",
    "[data-automation-id='nextButton']",
]


class WorkdayAdapter:
    ats_name = "workday"
    url_patterns = [
        re.compile(r"myworkdayjobs\.com", re.IGNORECASE),
        re.compile(r"workday\.com", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        self.current_section: str | None = None
        self.section_history: list[str] = []

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        """Click the 'Apply Now' button if the page is a job description, not yet a form."""
        for selector in _APPLY_SELECTORS:
            if await browser.has_element(selector):
                try:
                    # The click will navigate to the wizard — click_next handles navigation
                    await browser.click_next()
                    await self._track_section(browser)
                    return
                except Exception:
                    continue

    async def _track_section(self, browser: BrowserAutomationAdapter) -> None:
        """Track which wizard section is currently shown."""
        try:
            page_text = await browser.get_page_text()
            # Workday section headers are typically short lines (< 60 chars) early in the page
            for line in page_text.splitlines()[:30]:
                line = line.strip()
                if 5 < len(line) < 60 and not line.endswith("."):
                    if line != self.current_section:
                        self.current_section = line
                        if line not in self.section_history:
                            self.section_history.append(line)
                    break
        except Exception:
            pass

    def normalize_field(self, field: RawFormField) -> RawFormField:
        # Workday uses aria-labels as the primary source; prefer aria_label over label
        label = field.aria_label or field.label or field.name
        return RawFormField(
            field_id=field.field_id,
            name=field.name,
            label=label,
            field_type=field.field_type,
            is_required=field.is_required,
            options=field.options,
            placeholder=field.placeholder,
            css_selector=field.css_selector,
            section_title=field.section_title,
            aria_label=field.aria_label,
        )

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        # Workday wizard: click Next until Submit is the only action
        max_steps = 15
        for _ in range(max_steps):
            has_submit = await browser.has_element("button[type='submit'], [data-automation-id='submitButton']")
            has_next = await browser.has_element(
                ", ".join(_NEXT_SELECTORS)
            )
            if has_submit and not has_next:
                break
            if has_next:
                await browser.click_next()
                await self._track_section(browser)
            else:
                break
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return re.compile(r"WD[-]?(\d{7,})", re.IGNORECASE)
