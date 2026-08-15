"""ApplicationAgent: generate a tailored application strategy.

Given candidate + job + match analysis, returns actionable guidance for
CV personalization and cover letter writing.
"""
from pydantic import BaseModel, Field
from app.services.ai.provider import LLMProvider, default_provider
from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL = "claude-haiku-4-5-20251001"


# ── Output schema ─────────────────────────────────────────────────────────────

class CVChangeGuidance(BaseModel):
    section: str = Field(description="summary | skills | experience | projects")
    action: str = Field(description="rewrite | reorder | emphasize | de_emphasize")
    rationale: str
    specific_guidance: str


class ApplicationStrategy(BaseModel):
    """How to maximize interview probability without misrepresenting the candidate."""
    overall_approach: str = Field(description="2-3 sentence framing of how to position this candidate")
    cv_changes: list[CVChangeGuidance] = Field(
        default_factory=list,
        description="Ordered list of CV changes to make, highest impact first (max 6)",
    )
    cover_letter_key_points: list[str] = Field(
        default_factory=list,
        description="3-5 specific points the cover letter must address",
    )
    strengths_to_emphasize: list[str] = Field(
        default_factory=list,
        description="Candidate strengths directly relevant to this job (max 5)",
    )
    risks_to_address: list[str] = Field(
        default_factory=list,
        description="Gaps or mismatches the application must proactively address (max 3)",
    )
    # apply_as_is | apply_with_tailoring | stretch | pass
    recommendation: str


# ── System prompt ─────────────────────────────────────────────────────────────

STRATEGY_SYSTEM = """You are a senior career coach and hiring strategist.

Given a candidate's profile, a job opening, and the match analysis, create a concrete application strategy.

Rules:
- Be direct. No vague advice like "highlight your experience."
- Every guidance item must reference something specific in the candidate's profile or the job requirements.
- NEVER suggest inventing skills, changing dates, inventing metrics, or misrepresenting experience.
- Allowed personalizations: reorder content, rewrite summaries, emphasize relevant projects, keyword optimization.
- If the gap is a fundamental dealbreaker, say so honestly in risks_to_address.
- recommendation options: apply_as_is | apply_with_tailoring | stretch | pass"""


# ── Agent function ─────────────────────────────────────────────────────────────

async def generate_strategy(
    candidate_summary: str,
    candidate_skills: list[str],
    candidate_career_level: str | None,
    candidate_location: str | None,
    job_title: str | None,
    job_company: str | None,
    job_seniority: str | None,
    job_tech_stack: list[str],
    requirements_must_have: list[str],
    match_tier: str,
    match_overall_score: float,
    matched_skills: list[str],
    missing_skills: list[str],
    llm_reasoning: str | None,
    provider: LLMProvider = default_provider,
) -> ApplicationStrategy:
    """Generate an application strategy for a specific candidate–job pair."""
    logger.info("application_agent.strategy_start", job_title=job_title, match_tier=match_tier)

    must_have_text = "\n".join(f"- {r}" for r in requirements_must_have) or "- Not specified"
    skills_text = ", ".join(candidate_skills) if candidate_skills else "None listed"
    matched_text = ", ".join(matched_skills) if matched_skills else "None"
    missing_text = ", ".join(missing_skills) if missing_skills else "None"
    tech_stack_text = ", ".join(job_tech_stack) if job_tech_stack else "Not specified"

    user_message = f"""## Candidate
- Career level: {candidate_career_level or "unknown"}
- Location: {candidate_location or "unknown"}
- Summary: {candidate_summary or "No summary"}
- Skills: {skills_text}

## Target Job: {job_title or "Unknown"} at {job_company or "Unknown"}
- Required seniority: {job_seniority or "not specified"}
- Tech stack: {tech_stack_text}
- Must-have requirements:
{must_have_text}

## Match Analysis
- Overall score: {match_overall_score:.2f} ({match_tier})
- Matched skills: {matched_text}
- Missing skills: {missing_text}
- Assessment: {llm_reasoning or "No qualitative assessment available"}

Generate a concrete application strategy for this candidate."""

    result = await provider.structured_output(
        system=STRATEGY_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        schema=ApplicationStrategy,
        model=MODEL,
    )
    logger.info(
        "application_agent.strategy_done",
        recommendation=result.recommendation,
        cv_changes=len(result.cv_changes),
    )
    return result
