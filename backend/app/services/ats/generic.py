"""GenericFormAgent — LLM-powered fallback for unknown ATS platforms.

Used when no specific adapter matches the URL.
Falls back to: standard form extraction + higher human-required rate.
"""
import re
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


class GenericFormAgent:
    ats_name = "generic"
    url_patterns: list[re.Pattern] = []  # never matched by pattern

    # For unknown ATS, we trust form extraction but increase human review rate
    # by NOT normalizing — the orchestrator will use lower confidence thresholds
    CONFIDENCE_PENALTY = 0.15  # subtract from auto-fill confidence for generic forms

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        # For generic forms, wait a bit longer for JS rendering
        pass

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field  # no normalization for unknown ATS

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None  # use generic detector
