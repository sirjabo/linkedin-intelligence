"""CommunicationAgent: generate cover letters and application Q&A.

All output includes evidence_refs so ClaimValidator can cross-check.
"""
from pydantic import BaseModel, Field
from app.services.ai.provider import LLMProvider, default_provider
from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL = "claude-haiku-4-5-20251001"


# ── Output schemas ─────────────────────────────────────────────────────────────

class CoverLetterResult(BaseModel):
    content: str = Field(description="Full cover letter text (4-5 paragraphs)")
    key_points_addressed: list[str] = Field(
        default_factory=list,
        description="Which of the strategy key points were addressed",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Specific experiences/skills referenced in the letter",
    )


class AnswerResult(BaseModel):
    question: str
    answer: str = Field(description="Concise, specific answer (150-250 words)")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Experiences or skills the answer draws on",
    )


class ApplicationAnswers(BaseModel):
    answers: list[AnswerResult]


# ── System prompts ─────────────────────────────────────────────────────────────

COVER_LETTER_SYSTEM = """You are an expert career writer specializing in tech industry cover letters.

Rules:
- Be specific. Reference the company name and job title directly.
- No generic phrases like "I am excited to apply" without a specific reason.
- Every claim about the candidate must be supported by actual experience.
- Keep it professional, clear, and under 400 words.
- Structure: (1) hook/why this job, (2) strongest relevant experience, (3) specific technical fit, (4) cultural/team fit, (5) call to action.
- NEVER invent metrics, skills, or experiences not provided in the profile."""

ANSWERS_SYSTEM = """You are a career coach helping candidates answer application questions.

Rules:
- Answer each question specifically using ONLY the provided candidate experience.
- Use the STAR format when appropriate (Situation, Task, Action, Result).
- Be concrete: name specific technologies, teams, outcomes.
- If the candidate's experience doesn't directly answer the question, be honest and pivot to the most relevant experience.
- Keep each answer under 250 words.
- NEVER fabricate experience."""


# ── Agent functions ─────────────────────────────────────────────────────────────

async def generate_cover_letter(
    candidate_summary: str | None,
    candidate_skills: list[str],
    candidate_career_level: str | None,
    candidate_location: str | None,
    job_title: str | None,
    job_company: str | None,
    job_seniority: str | None,
    strengths_to_emphasize: list[str],
    cover_letter_key_points: list[str],
    match_tier: str,
    provider: LLMProvider = default_provider,
) -> CoverLetterResult:
    """Generate a targeted cover letter for the application."""
    logger.info("communication_agent.cover_letter_start", job_title=job_title)

    skills_text = ", ".join(candidate_skills[:20]) if candidate_skills else "None listed"
    strengths_text = "\n".join(f"- {s}" for s in strengths_to_emphasize) or "- Not specified"
    key_points_text = "\n".join(f"- {p}" for p in cover_letter_key_points) or "- Not specified"

    user_message = f"""## Candidate
- Career level: {candidate_career_level or "unknown"}
- Location: {candidate_location or "unknown"}
- Summary: {candidate_summary or "No summary"}
- Key skills: {skills_text}

## Target Position: {job_title or "Unknown"} at {job_company or "Unknown"}
- Required seniority: {job_seniority or "not specified"}
- Match quality: {match_tier}

## Strengths to emphasize:
{strengths_text}

## Key points the letter must address:
{key_points_text}

Write a professional cover letter for this position."""

    result = await provider.structured_output(
        system=COVER_LETTER_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        schema=CoverLetterResult,
        model=MODEL,
    )
    logger.info("communication_agent.cover_letter_done", length=len(result.content))
    return result


async def generate_application_answers(
    candidate_summary: str | None,
    candidate_skills: list[str],
    candidate_career_level: str | None,
    candidate_experience: list | None,
    job_title: str | None,
    job_company: str | None,
    strengths_to_emphasize: list[str],
    questions: list[str],
    provider: LLMProvider = default_provider,
) -> list[AnswerResult]:
    """Generate answers to application-specific questions."""
    logger.info("communication_agent.answers_start", question_count=len(questions))

    skills_text = ", ".join(candidate_skills[:20]) if candidate_skills else "None listed"
    strengths_text = ", ".join(strengths_to_emphasize) or "Not specified"

    exp_text = ""
    if candidate_experience:
        for exp in candidate_experience[:5]:
            if isinstance(exp, dict):
                title = exp.get("title", "")
                company = exp.get("company", "")
                exp_text += f"- {title} at {company}\n"

    questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    user_message = f"""## Candidate
- Career level: {candidate_career_level or "unknown"}
- Summary: {candidate_summary or "No summary"}
- Skills: {skills_text}
- Key strengths: {strengths_text}

Experience:
{exp_text or "Not provided"}

## Target Position: {job_title or "Unknown"} at {job_company or "Unknown"}

## Questions to answer:
{questions_text}

Provide a specific, concrete answer for each question."""

    result = await provider.structured_output(
        system=ANSWERS_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        schema=ApplicationAnswers,
        model=MODEL,
    )
    logger.info("communication_agent.answers_done", answers_generated=len(result.answers))
    return result.answers
