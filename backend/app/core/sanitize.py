"""Prompt injection sanitization for user-supplied strings sent to LLMs.

Every string that originated from external sources (user input, scraped JD,
form field labels, candidate profile data) must pass through sanitize_for_prompt()
before being interpolated into an LLM prompt.

The sanitizer does NOT modify the semantic meaning of the text. It only:
  1. Truncates strings exceeding max_length to prevent context stuffing.
  2. Removes control sequences commonly used in injection attacks.
  3. Strips leading/trailing whitespace.

It intentionally does NOT strip punctuation, markdown, or HTML tags — those
are handled by the caller when relevant (e.g. before displaying in the UI).
"""
import re

# Patterns that signal an injection attempt — instructions addressed to the model.
_INJECTION_PATTERNS: list[re.Pattern] = [
    # Direct role/instruction overrides
    re.compile(
        r"\bignore\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|text|context|prompt)\b", re.IGNORECASE
    ),
    re.compile(r"\bdo\s+not\s+(follow|obey|adhere\s+to)\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\s+a?\s*\w+\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+(if\s+you\s+(are|were)|a)\b", re.IGNORECASE),
    re.compile(r"\bsystem\s*prompt\b", re.IGNORECASE),
    re.compile(r"\b(new|different|updated)\s+(instructions?|prompt|system|persona)\b", re.IGNORECASE),
    re.compile(r"\bforget\s+(everything|all|your)\b", re.IGNORECASE),
    re.compile(r"\boverride\b.{0,30}\binstructions?\b", re.IGNORECASE),
    re.compile(r"\bdisregard\b", re.IGNORECASE),
    # Jailbreak markers
    re.compile(r"\bDAN\b"),  # "Do Anything Now"
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\btoken\s*smuggl", re.IGNORECASE),
]

# Characters that have no legitimate use in user strings sent to LLMs
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_for_prompt(
    text: str,
    max_length: int = 2000,
    field_name: str = "",
) -> tuple[str, bool]:
    """Sanitize a user-supplied string before interpolation into an LLM prompt.

    Returns:
        (sanitized_text, injection_detected)

    The caller should log a warning and use ErrorCode.LLM_PROMPT_INJECTION when
    injection_detected is True.  The sanitized text has the offending patterns
    replaced with [REDACTED] — it is never silently dropped, so callers can still
    use it (e.g. store the original) while blocking the injection payload.
    """
    if not text:
        return text, False

    injection_detected = False
    sanitized = _CONTROL_CHARS.sub("", text)

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(sanitized):
            injection_detected = True
            sanitized = pattern.sub("[REDACTED]", sanitized)

    sanitized = sanitized.strip()

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "…"

    return sanitized, injection_detected


def sanitize_batch(
    fields: dict[str, str],
    max_length: int = 2000,
) -> tuple[dict[str, str], list[str]]:
    """Sanitize a dict of field_name → value.

    Returns:
        (sanitized_dict, list_of_fields_with_injections)
    """
    result: dict[str, str] = {}
    flagged: list[str] = []
    for key, value in fields.items():
        clean, detected = sanitize_for_prompt(value, max_length=max_length, field_name=key)
        result[key] = clean
        if detected:
            flagged.append(key)
    return result, flagged
