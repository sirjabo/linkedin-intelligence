"""Greenhouse ATS adapter.

URL pattern: boards.greenhouse.io/[company]/jobs/[id]
"""
import re
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


class GreenhouseAdapter:
    ats_name = "greenhouse"
    url_patterns = [
        re.compile(r"boards\.greenhouse\.io", re.I),
        re.compile(r"greenhouse\.io/.*jobs", re.I),
    ]

    # Greenhouse-specific label normalization (their labels are usually clean)
    _LABEL_OVERRIDES: dict[str, str] = {
        "Resume/CV": "Resume",
        "Cover Letter": "Cover Letter",
        "LinkedIn Profile": "LinkedIn Profile URL",
    }

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        # Greenhouse sometimes shows a GDPR consent banner
        try:
            page_text = await browser.get_page_text()
            if "cookie" in page_text.lower() or "gdpr" in page_text.lower():
                await browser.fill_text("[data-gdpr-consent-accept]", "")
        except Exception:
            pass  # no banner, continue

    def normalize_field(self, field: RawFormField) -> RawFormField:
        label = self._LABEL_OVERRIDES.get(field.label, field.label)
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
        # Greenhouse can have multi-page forms — navigate through any intermediate pages
        # before clicking the final Submit.
        max_pages = 10
        for _ in range(max_pages):
            has_next = await browser.has_element("button:has-text('Next'), button:has-text('Continue')")
            has_submit = await browser.has_element("button[type='submit'], input[type='submit']")
            if has_submit and not has_next:
                break
            if has_next:
                await browser.click_next()
            else:
                break
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return re.compile(r"application\s+(?:id|number|#)[:\s]+([A-Z0-9-]{4,})", re.I)
