"""Greenhouse ATS adapter.

URL pattern: boards.greenhouse.io/[company]/jobs/[id]
"""
import re

from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField

# EEO section headers found in Greenhouse forms
_EEO_SECTION_PATTERNS = [
    re.compile(r"equal\s+employment\s+opportunity", re.IGNORECASE),
    re.compile(r"voluntary\s+(self[\s-]?)?disclosure", re.IGNORECASE),
    re.compile(r"demographic\s+information", re.IGNORECASE),
    re.compile(r"\beeo\b", re.IGNORECASE),
]


class GreenhouseAdapter:
    ats_name = "greenhouse"
    url_patterns = [
        re.compile(r"boards\.greenhouse\.io", re.IGNORECASE),
        re.compile(r"greenhouse\.io/.*jobs", re.IGNORECASE),
    ]

    # Greenhouse-specific label normalization (their labels are usually clean)
    _LABEL_OVERRIDES: dict[str, str] = {
        "Resume/CV": "Resume",
        "Cover Letter": "Cover Letter",
        "LinkedIn Profile": "LinkedIn Profile URL",
    }

    def __init__(self) -> None:
        self.sections_visited: list[str] = []
        self.eeo_section_present: bool = False

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        # Greenhouse sometimes shows a GDPR consent banner
        try:
            page_text = await browser.get_page_text()
            if "cookie" in page_text.lower() or "gdpr" in page_text.lower():
                await browser.fill_text("[data-gdpr-consent-accept]", "")
        except Exception:
            pass  # no banner, continue

        # Detect EEO section so the orchestrator can inform the candidate
        try:
            page_text = await browser.get_page_text()
            self.eeo_section_present = any(
                p.search(page_text) for p in _EEO_SECTION_PATTERNS
            )
        except Exception:
            pass

    def normalize_field(self, field: RawFormField) -> RawFormField:
        label = self._LABEL_OVERRIDES.get(field.label, field.label)
        # Track which sections we've seen
        if field.section_title and field.section_title not in self.sections_visited:
            self.sections_visited.append(field.section_title)
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
        return re.compile(r"application\s+(?:id|number|#)[:\s]+([A-Z0-9-]{4,})", re.IGNORECASE)
