"""Phase 6 — Interview preparation agent."""
import json

from pydantic import BaseModel

from app.services.ai.provider import LLMProvider

MODEL = "claude-haiku-4-5-20251001"


class TechnicalQuestion(BaseModel):
    question: str
    rationale: str


class BehavioralQuestion(BaseModel):
    question: str
    competency: str


class STARStory(BaseModel):
    competency: str
    situation: str
    task: str
    action: str
    result: str


class CompanyResearch(BaseModel):
    culture: str
    mission: str
    values: str


class InterviewPrepResult(BaseModel):
    technical_questions: list[TechnicalQuestion]
    behavioral_questions: list[BehavioralQuestion]
    star_stories: list[STARStory]
    questions_to_ask: list[str]
    company_research: CompanyResearch


_SYSTEM = """You are an expert interview coach.
Generate structured interview preparation for the candidate.
Be specific: reference the actual job requirements and the candidate's real experience.
Do NOT invent experience the candidate doesn't have."""


async def generate_interview_prep(
    job_data: dict,
    profile_data: dict,
    strategy_data: dict | None,
    provider: LLMProvider,
) -> InterviewPrepResult:
    user_message = f"""Prepare interview materials for this candidate and job.

JOB:
{json.dumps(job_data, default=str, indent=2)}

CANDIDATE PROFILE:
{json.dumps(profile_data, default=str, indent=2)}

APPLICATION STRATEGY:
{json.dumps(strategy_data, default=str, indent=2) if strategy_data else "Not available"}

Generate:
- 5 technical questions likely to be asked (based on JD requirements)
- 5 behavioral questions targeting key competencies
- 3 STAR story frameworks based on the candidate's actual experience
- 5 thoughtful questions the candidate should ask the interviewer
- Company research summary (culture, mission, values) inferred from JD"""

    result = await provider.structured_output(
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        schema=InterviewPrepResult,
        model=MODEL,
    )
    return result  # type: ignore[return-value]
