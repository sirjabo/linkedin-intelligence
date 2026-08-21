"""GenericFormAgent — LLM-powered fallback for unknown ATS platforms.

Used when no specific adapter matches the URL.
Falls back to: standard form extraction + higher human-required rate.
"""
import re

from app.services.ats.adapter import ATSCapabilities
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField

_CAPABILITIES = ATSCapabilities(
    confidence_penalty=0.15,
)


class GenericFormAgent:
    ats_name = "generic"
    url_patterns: list[re.Pattern] = []  # never matched by pattern

    @property
    def capabilities(self) -> ATSCapabilities:
        return _CAPABILITIES

    # Kept as a class attribute so callers that reference GenericFormAgent.CONFIDENCE_PENALTY
    # continue to work; the canonical value lives in _CAPABILITIES.
    CONFIDENCE_PENALTY: float = _CAPABILITIES.confidence_penalty

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        pass  # generic forms: rely on JS rendering already complete

    def normalize_field(self, field: RawFormField) -> RawFormField:
        return field  # no normalization for unknown ATS

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        await browser.click_submit()
        return await browser.is_confirmation_page()

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        return None  # use generic detector
