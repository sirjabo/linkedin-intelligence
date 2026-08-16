"""ApplicationAgent: generate a tailored application strategy.

Given candidate + job + match analysis, returns actionable guidance for
CV personalization and cover letter writing.
"""
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.ai.model_router import route_model
from app.services.ai.provider import LLMProvider, default_provider

logger = get_logger(__name__)

MODEL = route_model("strategy")


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

    # Sprint E: enriched strategy fields
    positioning: str = Field(
        default="",
        description=(
            "1-sentence candidate positioning statement: how they should frame themselves "
            "for THIS specific role (e.g. 'Senior backend engineer moving into platform engineering')"
        ),
    )
    target_narrative: str = Field(
        default="",
        description=(
            "2-3 sentence narrative arc: where the candidate has been, "
            "where they are, why THIS role is the natural next step"
        ),
    )
    keywords_for_form: list[str] = Field(
        default_factory=list,
        description=(
            "ATS-critical keywords from the job posting that the candidate legitimately has "
            "and should include verbatim in form essays (max 10)"
        ),
    )
    answer_strategy: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Mapping of common custom-essay questions to a 1-sentence answer angle. "
            "Keys are question patterns, values are the specific angle to take. "
            "E.g. {'Why do you want to join us?': 'Emphasize their open-source commitment and the team size.'}"
        ),
    )
    interview_preparation_strategy: list[str] = Field(
        default_factory=list,
        description=(
            "3-5 interview preparation tips specific to this role and company. "
            "Reference actual technologies or requirements from the job description."
        ),
    )
    claims_to_avoid: list[str] = Field(
        default_factory=list,
        description=(
            "Skills or accomplishments the candidate should NOT claim because "
            "they cannot defend them in an interview (max 5)"
        ),
    )
    company_specific_angle: str = Field(
        default="",
        description=(
            "1-2 sentences on what makes THIS company interesting to this candidate, "
            "grounded in publicly known facts (product, culture, mission)"
        ),
    )


# ── System prompt ─────────────────────────────────────────────────────────────

STRATEGY_SYSTEM = """You are a senior career coach and hiring strategist.

Given a candidate's profile, a job opening, and the match analysis, create a concrete application strategy.

Core rules:
- Be direct. No vague advice like "highlight your experience."
- Every guidance item must reference something specific in the candidate's profile or the job requirements.
- NEVER suggest inventing skills, changing dates, inventing metrics, or misrepresenting experience.
- Allowed personalizations: reorder content, rewrite summaries, emphasize relevant projects, keyword optimization.
- If the gap is a fundamental dealbreaker, say so honestly in risks_to_address.
- recommendation options: apply_as_is | apply_with_tailoring | stretch | pass

For the enriched strategy fields:
- positioning: one crisp sentence, role-specific, no buzzwords
- target_narrative: tells a coherent career story leading to THIS role
- keywords_for_form: only real skills the candidate has, verbatim from the job description
- answer_strategy: practical essay angles; key = question pattern, value = 1-sentence angle
- interview_preparation_strategy: concrete, role-specific (e.g. "Prepare a STAR story for Kubernetes migrations")
- claims_to_avoid: skills or metrics the candidate cannot defend under probing questions
- company_specific_angle: grounded in public information (product direction, engineering blog, mission)"""


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

Generate a complete application strategy including positioning, narrative, keywords_for_form, \
answer_strategy, interview_preparation_strategy, claims_to_avoid, and company_specific_angle."""

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
