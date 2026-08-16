"""ATSAdapter Protocol — specialized knowledge for a specific ATS platform."""
import asyncio
import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from app.core.logging import get_logger
from app.services.browser.adapter import BrowserAutomationAdapter, RawFormField

_log = get_logger(__name__)
_T = TypeVar("_T")


@dataclass(frozen=True)
class ATSCapabilities:
    """Static capability declaration for an ATS adapter.

    Used by the orchestrator to adjust behaviour (e.g. apply confidence
    penalties, surface EEO warnings, skip redundant retries).
    """
    eeo_detection: bool = False        # can detect EEO voluntary-disclosure sections
    multi_page: bool = False           # form spans multiple pages / wizard steps
    max_form_pages: int = 1            # practical upper bound on pages
    iframe_support: bool = False       # form may be embedded in an <iframe>
    custom_questions: bool = False     # adapter surfaces non-standard freeform questions
    requires_apply_click: bool = False # job listing needs an Apply click before form
    has_confirmation_id: bool = False  # adapter regex can extract a submission ID
    confidence_penalty: float = 0.0   # subtract from auto-fill confidence (0.0 = none)
    known_url_patterns: list[str] = field(default_factory=list)  # human-readable examples


async def retry_with_backoff(
    fn: Callable[[], Coroutine[Any, Any, _T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    label: str = "operation",
) -> _T:
    """Retry an async callable with exponential backoff.

    Raises the last exception if all attempts fail.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))
                _log.warning(
                    "ats.retry", label=label, attempt=attempt,
                    max_attempts=max_attempts, delay=delay, error=str(exc),
                )
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


@runtime_checkable
class ATSAdapter(Protocol):
    """Specialized knowledge for a single ATS platform.

    Each adapter knows the URL patterns for its ATS, how to handle
    platform-specific quirks (login walls, GDPR banners, confirmation page
    formats), and provides any label normalization specific to that platform.
    """
    ats_name: str
    url_patterns: list[re.Pattern]

    @property
    def capabilities(self) -> ATSCapabilities:
        """Return the static capability matrix for this adapter."""
        ...

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
