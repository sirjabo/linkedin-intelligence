"""BrowserAutomationAdapter protocol + RawForm data classes.

Domain logic never imports Playwright directly — it only uses this protocol.
The PlaywrightAdapter (playwright_adapter.py) is the concrete implementation.
"""
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# ── RawForm data model ────────────────────────────────────────────────────────

@dataclass
class RawFormField:
    """A single field extracted from a real web form."""
    field_id: str           # HTML id or generated from name/index
    name: str               # HTML name attribute
    label: str              # visible label text (from label[for], aria-label, placeholder)
    field_type: str         # text | email | tel | file | select | textarea | checkbox | radio | url | number | hidden
    is_required: bool
    options: list[str] | None = None       # values for select / radio
    placeholder: str | None = None
    css_selector: str = ""                  # selector for browser interaction
    section_title: str | None = None        # nearest fieldset legend / section heading
    aria_label: str | None = None


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

    async def select_option(self, css_selector: str, value: str) -> bool: ...

    async def check_checkbox(self, css_selector: str, checked: bool) -> bool: ...

    async def upload_file(self, css_selector: str, file_path: str) -> bool: ...

    async def click_submit(self) -> PageState: ...

    async def click_next(self) -> PageState: ...

    async def capture_screenshot(self) -> bytes: ...

    async def get_page_text(self) -> str: ...

    async def is_confirmation_page(self) -> bool: ...

    async def extract_confirmation_id(self) -> str | None: ...

    async def close(self) -> None: ...
