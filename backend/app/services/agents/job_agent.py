"""JobAgent: parses job descriptions into structured requirements.

Uses structured output (tool_use) — never XML tag parsing.
"""
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.sanitize import sanitize_for_prompt
from app.services.ai.cache import llm_cache
from app.services.ai.model_router import route_model
from app.services.ai.provider import LLMProvider, default_provider

logger = get_logger(__name__)

MODEL_PARSE = route_model("jd_parse")


# ── Output schemas ────────────────────────────────────────────────────────────

class RequirementItem(BaseModel):
    description: str
    requirement_type: str = Field(description="must_have | nice_to_have")
    category: str = Field(description="technical | soft | experience | education | domain | certification")
    is_required: bool = True
    seniority_signal: str | None = Field(
        None, description="Signal about required seniority level, e.g. '5+ years', 'senior-level'"
    )
    classification: str | None = Field(
        None, description="MANDATORY (explicitly required), PREFERRED (explicitly preferred), INFERRED (not stated but implied)"
    )


class ParsedJob(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    remote_type: str | None = Field(None, description="onsite | hybrid | remote")
    seniority: str | None = Field(
        None, description="intern | junior | mid | senior | staff | principal | lead | manager"
    )
    employment_type: str | None = Field(None, description="full-time | part-time | contract")
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    tech_stack: list[str] = Field(default_factory=list, description="Core technologies explicitly mentioned")
    requirements: list[RequirementItem] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)
    company_description: str | None = None
    visa_sponsorship: bool | None = Field(None, description="True if company offers visa sponsorship, False if explicitly not, null if not mentioned")
    parsing_confidence: float = Field(ge=0.0, le=1.0, default=0.8)


# ── System prompt ─────────────────────────────────────────────────────────────

PARSE_SYSTEM = """You are an expert at extracting structured information from job descriptions.

Extract every requirement, skill, and attribute mentioned. Follow these rules:
- NEVER invent requirements not in the job description text.
- Classify each requirement: must_have (explicitly required/mandatory) or nice_to_have (preferred/plus).
- For each requirement set classification: MANDATORY (uses words like "required", "must", "mandatory"),
  PREFERRED (uses words like "preferred", "a plus", "nice to have"), or INFERRED (implied but not stated).
- For tech_stack: only technologies explicitly named, no inferences.
- For salary: only extract if explicitly stated — never estimate.
- Set parsing_confidence: 1.0=detailed JD with clear requirements, 0.5=vague JD.
- remote_type: 'remote' if fully remote, 'hybrid' if mixed, 'onsite' if office required, null if unclear.
- seniority: infer from years of experience required or role level; null if unclear.
- visa_sponsorship: true if company explicitly offers sponsorship, false if they state they do not sponsor, null if not mentioned.

Never hallucinate. Stick strictly to what the text says."""


# ── Agent function ─────────────────────────────────────────────────────────────

async def parse_job_description(
    raw_jd: str,
    provider: LLMProvider = default_provider,
) -> ParsedJob:
    """Parse a raw job description into structured requirements and metadata."""
    cached = llm_cache.get("jd_parse", raw_jd)
    if cached is not None:
        logger.info("job_agent.parse_cache_hit", jd_length=len(raw_jd))
        return ParsedJob.model_validate(cached)

    clean_jd, injection_detected = sanitize_for_prompt(raw_jd, max_length=12000, field_name="job_description")
    if injection_detected:
        logger.warning("job_agent.injection_detected", jd_length=len(raw_jd))
    logger.info("job_agent.parse_start", jd_length=len(raw_jd))
    result = await provider.structured_output(
        system=PARSE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Parse this job description and extract all structured information:\n\n{clean_jd}"
        }],
        schema=ParsedJob,
        model=MODEL_PARSE,
    )
    llm_cache.set("jd_parse", raw_jd, result.model_dump())
    logger.info(
        "job_agent.parse_done",
        title=result.title,
        company=result.company,
        requirements_found=len(result.requirements),
        confidence=result.parsing_confidence,
    )
    return result
