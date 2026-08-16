"""MatchAgent: LLM reasoning layer for match analysis.

Pure function — takes structured data, returns structured reasoning.
No DB I/O; no side effects.
"""
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.ai.cache import llm_cache
from app.services.ai.model_router import route_model
from app.services.ai.provider import LLMProvider, default_provider

logger = get_logger(__name__)

MODEL_MATCH = route_model("match_reason")


# ── Output schema ─────────────────────────────────────────────────────────────

class LLMMatchResult(BaseModel):
    """LLM qualitative assessment of a candidate–job match."""
    score: float = Field(ge=0.0, le=1.0, description="Match quality 0.0–1.0")
    reasoning: str = Field(description="2-3 sentence narrative explaining the score")
    strengths: list[str] = Field(
        default_factory=list,
        description="Concrete reasons the candidate is a strong fit (max 5)",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Missing skills or experience areas (max 5)",
    )
    recommendation: str = Field(
        description="apply | apply_with_tailoring | stretch | pass"
    )


# ── System prompt ─────────────────────────────────────────────────────────────

MATCH_SYSTEM = """You are an expert technical recruiter evaluating candidate–job fit.

Given a candidate's profile and a job's requirements, provide an honest assessment.

Scoring guidelines:
- 0.85–1.0: Excellent match — candidate exceeds or perfectly meets all key requirements
- 0.70–0.84: Strong match — minor gaps that are easily learned
- 0.55–0.69: Moderate match — some gaps but transferable skills exist
- 0.40–0.54: Weak match — significant gaps in core requirements
- 0.00–0.39: Poor match — fundamentally different domain or level

Recommendations:
- apply: Strong fit, apply as-is
- apply_with_tailoring: Good fit, highlight specific experiences in cover letter
- stretch: Below requirements but candidate has growth potential
- pass: Not a realistic fit

Be direct and specific. Reference actual skills and requirements.
Never be falsely encouraging. Gaps are as important as strengths."""


# ── Agent function ─────────────────────────────────────────────────────────────

async def reason_about_match(
    candidate_summary: str,
    candidate_skills: list[str],
    candidate_career_level: str | None,
    candidate_location: str | None,
    job_title: str | None,
    job_company: str | None,
    job_seniority: str | None,
    job_location: str | None,
    job_remote_type: str | None,
    job_tech_stack: list[str],
    requirements_must_have: list[str],
    requirements_nice_to_have: list[str],
    deterministic_score: float,
    matched_skills: list[str],
    missing_skills: list[str],
    provider: LLMProvider = default_provider,
) -> LLMMatchResult:
    """Produce a qualitative LLM assessment to complement deterministic scoring."""
    cache_key_parts = [
        candidate_summary or "",
        ",".join(sorted(candidate_skills)),
        candidate_career_level or "",
        job_title or "",
        job_company or "",
        ",".join(sorted(requirements_must_have)),
        str(round(deterministic_score, 3)),
    ]
    cached = llm_cache.get("match_reason", *cache_key_parts)
    if cached is not None:
        logger.info("match_agent.reason_cache_hit", job_title=job_title)
        return LLMMatchResult.model_validate(cached)

    logger.info(
        "match_agent.reason_start",
        job_title=job_title,
        deterministic_score=deterministic_score,
    )

    must_have_text = "\n".join(f"- {r}" for r in requirements_must_have) or "- Not specified"
    nice_to_have_text = "\n".join(f"- {r}" for r in requirements_nice_to_have) or "- Not specified"
    skills_text = ", ".join(candidate_skills) if candidate_skills else "None listed"
    matched_text = ", ".join(matched_skills) if matched_skills else "None"
    missing_text = ", ".join(missing_skills) if missing_skills else "None"
    tech_stack_text = ", ".join(job_tech_stack) if job_tech_stack else "Not specified"

    user_message = f"""## Candidate Profile
- Career level: {candidate_career_level or "unknown"}
- Location: {candidate_location or "unknown"}
- Summary: {candidate_summary or "No summary available"}
- Skills: {skills_text}

## Job: {job_title or "Unknown"} at {job_company or "Unknown"}
- Seniority required: {job_seniority or "not specified"}
- Location: {job_location or "not specified"} ({job_remote_type or "onsite"})
- Tech stack: {tech_stack_text}

### Must-have requirements:
{must_have_text}

### Nice-to-have requirements:
{nice_to_have_text}

## Deterministic pre-analysis
- Overall deterministic score: {deterministic_score:.2f}
- Skills matched: {matched_text}
- Skills missing: {missing_text}

Evaluate this candidate for the job and provide your structured assessment."""

    result = await provider.structured_output(
        system=MATCH_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        schema=LLMMatchResult,
        model=MODEL_MATCH,
    )
    llm_cache.set("match_reason", *cache_key_parts, result.model_dump())
    logger.info(
        "match_agent.reason_done",
        llm_score=result.score,
        recommendation=result.recommendation,
        strengths_count=len(result.strengths),
        gaps_count=len(result.gaps),
    )
    return result
