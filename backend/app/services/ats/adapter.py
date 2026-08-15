"""ATSAdapter Protocol — specialized knowledge for a specific ATS platform."""
import re
from typing import Protocol, runtime_checkable

from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField


@runtime_checkable
class ATSAdapter(Protocol):
    """Specialized knowledge for a single ATS platform.

    Each adapter knows the URL patterns for its ATS, how to handle
    platform-specific quirks (login walls, GDPR banners, confirmation page
    formats), and provides any label normalization specific to that platform.
    """
    ats_name: str
    url_patterns: list[re.Pattern]

    async def before_discover(self, browser: BrowserAutomationAdapter) -> None:
        """Handle anything that blocks form access (cookie banners, etc.)."""
        ...

    def normalize_field(self, field: RawFormField) -> RawFormField:
        """Apply ATS-specific label normalization (no-op by default)."""
        ...

    async def submit(self, browser: BrowserAutomationAdapter) -> bool:
        """Execute the submit action. Return True if confirmation page reached."""
        ...

    def extract_confirmation_id_pattern(self) -> re.Pattern | None:
        """Override platform-specific confirmation ID pattern if needed."""
        ...
