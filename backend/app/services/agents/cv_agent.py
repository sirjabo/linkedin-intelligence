"""CVAgent: personalize a candidate's CV for a specific job.

Allowed: reorder content, rewrite summaries, keyword emphasis, project selection,
         rewrite experience bullets to highlight relevant achievements.
Prohibited: inventing skills, changing dates/titles, fabricating metrics.
Every change includes original text, adapted text, rationale, and evidence reference.
"""
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.ai.model_router import route_model
from app.services.ai.provider import LLMProvider, default_provider

logger = get_logger(__name__)

MODEL = route_model("cv_personalize")


# ── Output schema ─────────────────────────────────────────────────────────────

class CVChange(BaseModel):
    section: str = Field(description="summary | skills | experience | projects | headline")
    original: str = Field(description="The original text before adaptation")
    adapted: str = Field(description="The adapted text after personalization")
    rationale: str = Field(description="Why this change improves fit for this job")
    evidence_ref: str | None = Field(
        None, description="Reference to the experience or skill this builds on"
    )


class BulletChange(BaseModel):
    """A single bullet point rewritten to emphasize job-relevant achievements."""
    original: str = Field(description="Original bullet text verbatim")
    adapted: str = Field(description="Rewritten bullet emphasizing job-relevant aspects")
    reason: str = Field(description="Which job requirement this bullet now highlights")
    job_requirement: str = Field(description="The specific requirement from the JD this addresses")
    evidence_ref: str | None = Field(None, description="Skill or project from the profile that backs this claim")
    confidence: float = Field(default=0.8, description="Confidence that this rewrite is accurate (0-1)")


class ExperiencePersonalized(BaseModel):
    """One experience entry with bullet-level personalization."""
    company: str
    title: str
    bullets_original: list[str] = Field(default_factory=list)
    bullets_adapted: list[BulletChange] = Field(default_factory=list)


class ProjectPersonalized(BaseModel):
    """One project entry with description personalization."""
    name: str
    description_original: str = Field(default="")
    description_adapted: str = Field(default="")
    reason: str = Field(default="")
    highlights_adapted: list[str] = Field(default_factory=list)


class PersonalizedCV(BaseModel):
    """Personalized CV tailored to a specific job opening."""
    summary_adapted: str | None = Field(
        None, description="Rewritten professional summary emphasizing relevant experience"
    )
    headline_adapted: str | None = Field(
        None, description="Adapted headline/title if appropriate"
    )
    skills_ordered: list[str] = Field(
        default_factory=list,
        description="Skills reordered with most relevant ones first",
    )
    ats_keywords_added: list[str] = Field(
        default_factory=list,
        description="Keywords from JD that were organically incorporated (not invented)",
    )
    changes: list[CVChange] = Field(
        default_factory=list,
        description="All changes made, each with original/adapted/rationale (max 8)",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="List of experiences/projects referenced in the personalization",
    )
    experience_personalized: list[ExperiencePersonalized] = Field(
        default_factory=list,
        description="Experience entries with bullet-level rewrites for this job (max 4 entries)",
    )
    projects_personalized: list[ProjectPersonalized] = Field(
        default_factory=list,
        description="Project entries with description adapted for this job (max 3 projects)",
    )


# ── System prompt ─────────────────────────────────────────────────────────────

CV_SYSTEM = """You are an expert CV writer specializing in ATS optimization and job targeting.

Your task: personalize a candidate's CV for a specific job opening, including bullet-level rewrites.

ALLOWED:
- Rewrite the professional summary to emphasize the most relevant aspects
- Reorder skills list to put job-relevant ones first
- Adjust headline/title to match job language (e.g. "Senior Engineer" → "Senior Data Engineer")
- Rewrite experience bullets to highlight the aspects most relevant to the target role
  (same achievement, different emphasis — e.g. lead on "impact" for product roles, "scale" for infra)
- Rewrite project descriptions to emphasize technologies or outcomes the JD cares about
- Add keywords from JD that are organically supported by actual experience

PROHIBITED:
- Inventing skills the candidate doesn't have
- Changing dates, company names, job titles in experience
- Fabricating metrics or achievements not present in the original
- Claiming experience the candidate doesn't have
- Adding technologies not in the original profile
- Confidence > 0.9 when the original bullet is vague and the adaptation is interpretive

For every change, explain what you changed, why it improves fit, and what evidence supports it.
The candidate must be able to defend every claim in an interview.
Produce experience_personalized for the top 3 most relevant experience entries only.
Produce projects_personalized for the top 2 most relevant projects only."""


# ── Agent function ─────────────────────────────────────────────────────────────

async def personalize_cv(
    candidate_summary: str | None,
    candidate_headline: str | None,
    candidate_skills: list[str],
    candidate_career_level: str | None,
    candidate_experience: list | None,
    candidate_projects: list | None,
    job_title: str | None,
    job_company: str | None,
    job_seniority: str | None,
    job_tech_stack: list[str],
    requirements_must_have: list[str],
    strategy_guidance: list[dict],  # CVChangeGuidance list as dicts
    provider: LLMProvider = default_provider,
) -> PersonalizedCV:
    """Produce a personalized CV tailored to the target job."""
    logger.info("cv_agent.personalize_start", job_title=job_title)

    skills_text = ", ".join(candidate_skills[:30]) if candidate_skills else "None"
    tech_stack_text = ", ".join(job_tech_stack) if job_tech_stack else "Not specified"
    must_have_text = "\n".join(f"- {r}" for r in requirements_must_have) or "- Not specified"

    # Serialize experience with bullets (top 5 for context, top 3 for personalization)
    exp_text = ""
    exp_with_bullets = ""
    if candidate_experience:
        for exp in candidate_experience[:5]:
            if isinstance(exp, dict):
                title = exp.get("title") or exp.get("role", "")
                company = exp.get("company", "")
                exp_text += f"- {title} at {company}\n"
        for exp in candidate_experience[:3]:
            if isinstance(exp, dict):
                title = exp.get("title") or exp.get("role", "")
                company = exp.get("company", "")
                bullets = exp.get("bullets") or []
                exp_with_bullets += f"\n**{title} at {company}**\n"
                for b in bullets[:6]:
                    exp_with_bullets += f"  • {b}\n"

    # Serialize projects
    proj_text = ""
    if candidate_projects:
        for proj in candidate_projects[:3]:
            if isinstance(proj, dict):
                name = proj.get("name", "")
                desc = proj.get("description", "")
                proj_text += f"- **{name}**: {desc}\n"

    strategy_text = ""
    for g in strategy_guidance[:6]:
        if isinstance(g, dict):
            strategy_text += f"- [{g.get('section','?')}] {g.get('action','?')}: {g.get('specific_guidance','')}\n"

    user_message = f"""## Candidate Profile
- Career level: {candidate_career_level or "unknown"}
- Current headline: {candidate_headline or "none"}
- Summary: {candidate_summary or "No summary provided"}
- Skills: {skills_text}

## Experience (with bullets for personalization):
{exp_with_bullets or exp_text or "Not provided"}

## Projects:
{proj_text or "Not provided"}

## Target Job: {job_title or "Unknown"} at {job_company or "Unknown"}
- Required seniority: {job_seniority or "not specified"}
- Tech stack: {tech_stack_text}
- Must-have requirements:
{must_have_text}

## Strategy guidance to apply:
{strategy_text or "Optimize for the job requirements listed above"}

Personalize this CV for the job. Output ALL changes including bullet-level rewrites in \
experience_personalized (top 3 relevant experiences) and projects_personalized (top 2 projects)."""

    result = await provider.structured_output(
        system=CV_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        schema=PersonalizedCV,
        model=MODEL,
    )
    logger.info(
        "cv_agent.personalize_done",
        changes_made=len(result.changes),
        ats_keywords=len(result.ats_keywords_added),
    )
    return result
