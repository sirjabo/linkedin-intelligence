"""Form Intelligence: classify form fields and map candidate data to values.

Deterministic first, LLM fallback for unrecognized fields.
Human-in-the-loop for custom essays and fields with no auto-fill source.
"""
import re
from dataclasses import dataclass
from typing import Literal, get_args

from app.services.ai.model_router import route_model

SemanticType = Literal[
    "full_name", "first_name", "last_name",
    "email", "phone",
    "linkedin_url", "portfolio_url", "github_url",
    "location", "city", "country",
    "years_experience",
    "skill_years",         # Sprint F: "Years of Python experience"
    "salary_expectation",
    "work_authorization",
    "cover_letter",
    "cv_file",
    "start_date", "availability",
    "custom_essay",
    "experience_essay",    # Sprint F: open-ended "Tell us about your experience with X"
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
    # Sprint F: skill_years must come BEFORE years_experience to capture "years of Python"
    (re.compile(r"\byears?\b.*(python|java|kotlin|rust|go|ruby|php|swift|scala|react|vue|angular|node|django|flask|spring|rails|docker|kubernetes|k8s|aws|azure|gcp|sql|postgres|mysql|mongo|redis|typescript|javascript|typescript|css|html)\b", re.IGNORECASE), "skill_years"),
    (re.compile(r"\b(python|java|kotlin|rust|go|ruby|php|swift|scala|react|vue|angular|node|django|flask|spring|rails|docker|kubernetes|k8s|aws|azure|gcp|sql|postgres|mysql|mongo|redis|typescript|javascript|css|html)\b.*\byears?\b", re.IGNORECASE), "skill_years"),
    (re.compile(r"\byears?\b.*(experience|exp)\b|\b(experience|exp).*\byears?\b", re.IGNORECASE), "years_experience"),
    (re.compile(r"\bwork[\s_-]?auth(orization)?\b|\bvisa\b|\bsponsorship\b|\bauthorized\b.*(work|us)\b", re.IGNORECASE), "work_authorization"),
    (re.compile(r"\bcover[\s_-]?letter\b", re.IGNORECASE), "cover_letter"),
    (re.compile(r"\bresume\b|curriculum\b|cv\b", re.IGNORECASE), "cv_file"),
    (re.compile(r"\bstart[\s_-]?date\b|earliest\b.*start\b", re.IGNORECASE), "start_date"),
    (re.compile(r"\bavailability\b|available[\s_-]?to[\s_-]?start\b", re.IGNORECASE), "availability"),
    # Sprint F: experience_essay matches open-ended "tell us about your X experience" prompts
    (re.compile(r"\b(tell|describe|share|explain)\b.*(experience|background|journey|work)\b", re.IGNORECASE), "experience_essay"),
    (re.compile(r"\bwhy\b.*(company|role|interest|join|work|here|us|this)\b|(describe|tell|explain)\b", re.IGNORECASE), "custom_essay"),
]

# Sprint F: regex to extract the skill name from a skill_years label
_SKILL_YEARS_EXTRACT = re.compile(
    r"\b(python|java(?:script)?|kotlin|rust|go(?:lang)?|ruby|php|swift|scala|react|vue|angular|"
    r"node(?:\.js)?|django|flask|spring|rails|docker|kubernetes|k8s|aws|azure|gcp|sql|"
    r"postgres(?:ql)?|mysql|mongodb?|redis|typescript|css|html)\b",
    re.IGNORECASE,
)

# Semantic types that can never be auto-filled — always require human input
_ALWAYS_HUMAN = {"phone", "cv_file", "custom_essay", "experience_essay", "unknown"}

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
    # Sprint F: classification metadata
    confidence: float = 1.0          # 0-1; 1.0 = deterministic match, lower for LLM-classified
    classification_source: str = "regex"  # "regex" | "llm" | "default"
    skill_target: str | None = None  # for skill_years: the extracted skill name (e.g. "python")


_ALL_SEMANTIC_TYPES: frozenset[str] = frozenset(get_args(SemanticType))


def classify_field(label: str) -> SemanticType:
    """Return the semantic type for a form field label."""
    for pattern, sem_type in _LABEL_RULES:
        if pattern.search(label):
            return sem_type
    return "unknown"


def extract_skill_target(label: str) -> str | None:
    """For skill_years fields, extract the specific skill name from the label."""
    m = _SKILL_YEARS_EXTRACT.search(label)
    return m.group(1).lower() if m else None


async def classify_field_llm(
    label: str,
    placeholder: str | None = None,
    options: list[str] | None = None,
    field_type: str = "text",
    model: str = route_model("field_classify"),
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


async def classify_field_llm_with_confidence(
    label: str,
    placeholder: str | None = None,
    options: list[str] | None = None,
    field_type: str = "text",
    model: str = route_model("field_classify"),
) -> tuple[SemanticType, float]:
    """LLM classification returning (semantic_type, confidence).

    Confidence is 0.6 for LLM-classified fields (not deterministic).
    """
    sem_type = await classify_field_llm(label, placeholder, options, field_type, model)
    confidence = 0.6 if sem_type != "unknown" else 0.0
    return sem_type, confidence


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
        skill_target: str | None = None

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
            elif sem_type == "skill_years":
                # skill_years: extract the skill name; caller is responsible for resolving years
                skill_target = extract_skill_target(spec.label)
                # mark human_required so the orchestrator routes through CandidateKnowledgeResolver
                human_required = True

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
            confidence=1.0,
            classification_source="regex",
            skill_target=skill_target,
        ))

    return result
