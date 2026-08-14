"""SmartRecruiters ATS adapter.

URL pattern: careers.smartrecruiters.com/[company]/[job-id]
SmartRecruiters typically has a single-page form with optional multi-step sections.
"""
import re
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


_CONSENT_SELECTORS = [
    "button[id*='cookie']",
    "button[class*='cookie']",
    "button:has-text('Accept')",
    "button:has-text('Accept All')",
    "button:has-text('I agree')",
    "[data-testid='cookie-accept']",
]

_APPLY_SELECTORS = [
    ".apply-button",
    "[data-hook='apply-button']",
    "button:has-text('Apply')",
    "a:has-text('Apply for this job')",
    "a:has-text('Apply now')",
]


class SmartRecruitersAdapter:
    ats_name = "smartrecruiters"
    url_patterns = [
        re.compile(r"smartrecruiters\.com", re.I),
        re.compile(r"careers\.smartrecruiters", re.I),
    ]

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        """Dismiss GDPR/cookie banners; click Apply if on a job listing page."""
        # Dismiss cookie/GDPR consent banner
        for selector in _CONSENT_SELECTORS:
            if await browser.has_element(selector):
                try:
                    await browser.fill_text(selector, "")  # no-op fill just to focus
                except Exception:
                    pass
                try:
                    await browser.click_next()  # fallback click approach
                except Exception:
                    pass
                break

        # If on a job listing (not the apply form), click Apply
        for selector in _APPLY_SELECTORS:
            if await browser.has_element(selector):
                try:
                    await browser.click_next()
                    return
                except Exception:
                    continue

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field  # SmartRecruiters labels are already clean

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        # Multi-step: navigate through wizard pages before final submit
        max_pages = 8
        for _ in range(max_pages):
            has_next = await browser.has_element("button:has-text('Next'), button:has-text('Continue')")
            has_submit = await browser.has_element("button[type='submit']")
            if has_submit and not has_next:
                break
            if has_next:
                await browser.click_next()
            else:
                break
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return re.compile(r"[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}", re.I)
