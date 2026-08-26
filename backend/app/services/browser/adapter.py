"""BrowserAutomationAdapter protocol + RawForm data classes.

Domain logic never imports Playwright directly — it only uses this protocol.
The PlaywrightAdapter (playwright_adapter.py) is the concrete implementation.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class PageBlockerType(Enum):
    """Kind of page-level blocker the agent has detected."""
    CAPTCHA = "captcha"
    AUTH_WALL = "auth_wall"
    ANTI_BOT = "anti_bot"
    MFA = "mfa"
    COOKIE_CONSENT = "cookie_consent"


@dataclass
class PageBlocker:
    """Detected condition that prevents form automation from proceeding safely."""
    blocker_type: PageBlockerType
    description: str
    # If True the agent should pause and wait for human resolution
    requires_human: bool = True

# ── RawForm data model ────────────────────────────────────────────────────────

@dataclass
class RawFormField:
    """A single field extracted from a real web form."""
    field_id: str           # HTML id or generated from name/index
    name: str               # HTML name attribute
    label: str              # visible label text (from label[for], aria-label, placeholder)
    # text | email | tel | file | select | textarea | checkbox | radio | url | number |
    # hidden | custom_select (aria combobox/listbox)
    field_type: str
    is_required: bool
    options: list[str] | None = None       # values for select / radio / custom_select
    placeholder: str | None = None
    css_selector: str = ""                  # selector for browser interaction
    section_title: str | None = None        # nearest fieldset legend / section heading
    aria_label: str | None = None
    is_hidden: bool = False                 # True for hidden file inputs triggered by labels


@dataclass
class RawFormSection:
    title: str | None
    fields: list[RawFormField] = field(default_factory=list)


@dataclass
class RawForm:
    sections: list[RawFormSection] = field(default_factory=list)
    fields: list[RawFormField] = field(default_factory=list)  # flat list for convenience
    page_title: str | None = None
    submit_button_selector: str | None = None
    form_action: str | None = None


@dataclass
class PageState:
    url: str
    title: str | None
    is_loaded: bool = True


@dataclass
class SubmissionResult:
    success: bool
    final_url: str | None = None
    is_confirmation_page: bool = False
    confirmation_text: str | None = None
    confirmation_id: str | None = None
    screenshot: bytes | None = None
    error: str | None = None


# ── Protocol ──────────────────────────────────────────────────────────────────

@runtime_checkable
class BrowserAutomationAdapter(Protocol):
    """Thin interface over a browser. Domain logic never sees selectors."""

    async def open_url(self, url: str) -> PageState: ...

    async def discover_form(self) -> RawForm:
        """Extract all form elements from the current page."""
        ...

    async def fill_text(self, css_selector: str, value: str) -> bool: ...

    async def click(self, css_selector: str) -> bool: ...

    async def select_option(self, css_selector: str, value: str) -> bool: ...

    async def check_checkbox(self, css_selector: str, checked: bool) -> bool: ...

    async def upload_file(self, css_selector: str, file_path: str) -> bool: ...

    async def click_submit(self) -> PageState: ...

    async def click_next(self) -> PageState: ...

    async def capture_screenshot(self) -> bytes: ...

    async def get_page_text(self) -> str: ...

    async def is_confirmation_page(self) -> bool: ...

    async def extract_confirmation_id(self) -> str | None: ...

    async def has_element(self, selector: str) -> bool: ...

    async def switch_to_frame(self, frame_selector: str) -> bool: ...

    async def switch_to_main_frame(self) -> None: ...

    async def get_current_url(self) -> str | None: ...

    async def close(self) -> None: ...

    async def detect_page_blocker(self) -> "PageBlocker | None": ...

    async def wait_for_spa_ready(self, wait_ms: int = 10_000) -> bool: ...

    async def discover_form_in_iframes(self) -> "RawForm | None": ...

    async def handle_custom_select(self, container_selector: str, value: str) -> bool: ...

    async def fill_location_autocomplete(self, selector: str, value: str) -> bool: ...

    async def upload_file_hidden(self, label_selector: str, file_path: str) -> bool: ...
