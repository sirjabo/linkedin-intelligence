"""Workday ATS adapter.

URL pattern: [company].wd1.myworkdayjobs.com/...
Workday renders job pages that require clicking "Apply Now" to open the wizard.
The application wizard is a multi-step flow with page-level navigation.
"""
import re

from app.services.ats.adapter import ATSCapabilities
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

_CAPABILITIES = ATSCapabilities(
    multi_page=True,
    max_form_pages=15,
    requires_apply_click=True,
    has_confirmation_id=True,
    known_url_patterns=["company.myworkdayjobs.com/careers", "company.workday.com/apply"],
)


class WorkdayAdapter:
    ats_name = "workday"
    url_patterns = [
        re.compile(r"myworkdayjobs\.com", re.IGNORECASE),
        re.compile(r"workday\.com", re.IGNORECASE),
    ]

    @property
    def capabilities(self) -> ATSCapabilities:
        return _CAPABILITIES

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        """Click the 'Apply Now' button if the page is a job description, not yet a form."""
        for selector in _APPLY_SELECTORS:
            if await browser.has_element(selector):
                try:
                    clicked = await browser.click(selector)
                    if clicked:
                        # Wait for the wizard to load after navigation
                        await browser.open_url(await browser.get_current_url() or "")
                        return
                except Exception:
                    continue

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
        max_steps = _CAPABILITIES.max_form_pages
        for _ in range(max_steps):
            has_submit = await browser.has_element("button[type='submit'], [data-automation-id='submitButton']")
            has_next = await browser.has_element(", ".join(_NEXT_SELECTORS))
            if has_submit and not has_next:
                break
            if has_next:
                await browser.click_next()
            else:
                break
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return re.compile(r"WD[-]?(\d{7,})", re.IGNORECASE)
