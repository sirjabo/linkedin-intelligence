"""Form Intelligence: classify form fields and map candidate data to values.

Deterministic first, LLM fallback for unrecognized fields.
Human-in-the-loop for custom essays and fields with no auto-fill source.
"""
import re
from dataclasses import dataclass
from typing import Literal, get_args

SemanticType = Literal[
    "full_name", "first_name", "last_name",
    "email", "phone",
    "linkedin_url", "portfolio_url", "github_url",
    "location", "city", "country",
    "years_experience",
    "salary_expectation",
    "work_authorization",
    "cover_letter",
    "cv_file",
    "start_date", "availability",
    "custom_essay",
    "unknown",
]

# Maps label keywords → semantic type. First match wins.
_LABEL_RULES: list[tuple[re.Pattern, SemanticType]] = [
    (re.compile(r"\bfull[\s_-]?name\b", re.IGNORECASE), "full_name"),
    (re.compile(r"\bfirst[\s_-]?name\b", re.IGNORECASE), "first_name"),
    (re.compile(r"\blast[\s_-]?name\b|surname\b|family[\s_-]?name\b", re.IGNORECASE), "last_name"),
    (re.compile(r"\bemail\b|e-mail\b", re.IGNORECASE), "email"),
    (re.compile(r"\bphone\b|mobile\b|telephone\b", re.IGNORECASE), "phone"),
    (re.compile(r"\blinkedin\b", re.IGNORECASE), "linkedin_url"),
    (re.compile(r"\bportfolio\b|personal[\s_-]?site\b|website\b", re.IGNORECASE), "portfolio_url"),
    (re.compile(r"\bgithub\b|gitlab\b|bitbucket\b", re.IGNORECASE), "github_url"),
    (re.compile(r"\bcity\b", re.IGNORECASE), "city"),
    (re.compile(r"\bcountry\b|nation\b", re.IGNORECASE), "country"),
    (re.compile(r"\blocation\b|address\b|where[\s_-]?are\b", re.IGNORECASE), "location"),
    (re.compile(r"\bsalary\b|\bcompensation\b|\bexpected\b.*(pay|wage|sal)\b|(pay|wage|sal)\b.*\bexpected\b", re.IGNORECASE), "salary_expectation"),
    (re.compile(r"\byears?\b.*(experience|exp)\b|\b(experience|exp).*\byears?\b", re.IGNORECASE), "years_experience"),
    (re.compile(r"\bwork[\s_-]?auth(orization)?\b|\bvisa\b|\bsponsorship\b|\bauthorized\b.*(work|us)\b", re.IGNORECASE), "work_authorization"),
    (re.compile(r"\bcover[\s_-]?letter\b", re.IGNORECASE), "cover_letter"),
    (re.compile(r"\bresume\b|curriculum\b|cv\b", re.IGNORECASE), "cv_file"),
    (re.compile(r"\bstart[\s_-]?date\b|earliest\b.*start\b", re.IGNORECASE), "start_date"),
    (re.compile(r"\bavailability\b|available[\s_-]?to[\s_-]?start\b", re.IGNORECASE), "availability"),
    (re.compile(r"\bwhy\b.*(company|role|interest|join|work|here|us|this)\b|(describe|tell|explain)\b", re.IGNORECASE), "custom_essay"),
]

# Semantic types that can never be auto-filled — always require human input
_ALWAYS_HUMAN = {"phone", "cv_file", "custom_essay", "unknown"}

# Semantic types where auto-fill value comes from the candidate record
_CANDIDATE_FIELD_MAP: dict[SemanticType, str] = {
    "email": "email",
    "location": "location",
    "salary_expectation": "salary_min_usd",
    "work_authorization": "work_authorization",
    "availability": "availability",
}


@dataclass
class FieldSpec:
    """Input spec from the user describing a form field."""
    label: str
    field_type: str = "text"
    is_required: bool = True
    options: list[str] | None = None


@dataclass
class MappedField:
    label: str
    field_type: str
    semantic_type: SemanticType
    is_required: bool
    auto_fill_value: str | None
    human_required: bool
    options: list[str] | None = None


_ALL_SEMANTIC_TYPES: frozenset[str] = frozenset(get_args(SemanticType))


def classify_field(label: str) -> SemanticType:
    """Return the semantic type for a form field label."""
    for pattern, sem_type in _LABEL_RULES:
        if pattern.search(label):
            return sem_type
    return "unknown"


async def classify_field_llm(
    label: str,
    placeholder: str | None = None,
    options: list[str] | None = None,
    field_type: str = "text",
    model: str = "claude-haiku-4-5-20251001",
) -> SemanticType:
    """LLM fallback for fields that didn't match any regex rule.

    Calls Anthropic haiku with a minimal prompt; returns 'unknown' on any failure.
    """
    try:
        import anthropic

        from app.core.config import settings

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        types_list = ", ".join(sorted(_ALL_SEMANTIC_TYPES))
        extra = ""
        if placeholder:
            extra += f"\nPlaceholder: {placeholder}"
        if options:
            extra += f"\nOptions: {options[:10]}"  # cap to avoid huge prompts

        resp = await client.messages.create(
            model=model,
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": (
                    f"Classify this form field into exactly ONE of: {types_list}\n"
                    f"Label: {label}\nField type: {field_type}{extra}\n"
                    f"Reply with ONLY the type name."
                ),
            }],
        )
        block = resp.content[0]
        if not hasattr(block, "text"):
            return "unknown"
        candidate = block.text.strip().lower().replace("-", "_")  # type: ignore[union-attr]
        if candidate in _ALL_SEMANTIC_TYPES:
            return candidate  # type: ignore[return-value]
    except Exception:
        pass
    return "unknown"


def map_candidate_to_form(
    fields: list[FieldSpec],
    candidate_name: str | None,
    candidate_email: str | None,
    candidate_location: str | None,
    candidate_salary_min: int | None,
    candidate_work_authorization: str | None,
    candidate_availability: str | None,
) -> list[MappedField]:
    """Classify form fields and auto-fill from candidate data where possible.

    Returns a list of MappedField objects ready for form submission or human review.
    """
    candidate_data: dict[str, str | None] = {
        "email": candidate_email,
        "location": candidate_location,
        "salary_min_usd": str(candidate_salary_min) if candidate_salary_min else None,
        "work_authorization": candidate_work_authorization,
        "availability": candidate_availability,
    }

    result: list[MappedField] = []
    for _i, spec in enumerate(fields):
        sem_type = classify_field(spec.label)
        auto_fill: str | None = None
        human_required = sem_type in _ALWAYS_HUMAN

        # Auto-fill based on semantic type
        if not human_required:
            if sem_type == "full_name" and candidate_name:
                auto_fill = candidate_name
            elif sem_type == "first_name" and candidate_name:
                parts = candidate_name.strip().split()
                auto_fill = parts[0] if parts else None
            elif sem_type == "last_name" and candidate_name:
                parts = candidate_name.strip().split()
                auto_fill = parts[-1] if len(parts) > 1 else None
            elif sem_type in _CANDIDATE_FIELD_MAP:
                field_key = _CANDIDATE_FIELD_MAP[sem_type]
                auto_fill = candidate_data.get(field_key)

        if auto_fill is None and not human_required:
            human_required = True  # no source → needs human

        result.append(MappedField(
            label=spec.label,
            field_type=spec.field_type,
            semantic_type=sem_type,
            is_required=spec.is_required,
            auto_fill_value=auto_fill,
            human_required=human_required,
            options=spec.options,
        ))

    return result
