"""Phase 6 — Interview preparation agent."""
from pydantic import BaseModel

from app.services.ai.provider import LLMProvider


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


class InterviewPrepResult(BaseModel):
    technical_questions: list[TechnicalQuestion]
    behavioral_questions: list[BehavioralQuestion]
    star_stories: list[STARStory]
    questions_to_ask: list[str]
    company_research: dict  # {culture, mission, values}


_TOOL_SCHEMA = {
    "name": "generate_interview_prep",
    "description": "Generate comprehensive interview preparation materials.",
    "input_schema": {
        "type": "object",
        "properties": {
            "technical_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["question", "rationale"],
                },
            },
            "behavioral_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "competency": {"type": "string"},
                    },
                    "required": ["question", "competency"],
                },
            },
            "star_stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "competency": {"type": "string"},
                        "situation": {"type": "string"},
                        "task": {"type": "string"},
                        "action": {"type": "string"},
                        "result": {"type": "string"},
                    },
                    "required": ["competency", "situation", "task", "action", "result"],
                },
            },
            "questions_to_ask": {
                "type": "array",
                "items": {"type": "string"},
            },
            "company_research": {
                "type": "object",
                "properties": {
                    "culture": {"type": "string"},
                    "mission": {"type": "string"},
                    "values": {"type": "string"},
                },
                "required": ["culture", "mission", "values"],
            },
        },
        "required": [
            "technical_questions",
            "behavioral_questions",
            "star_stories",
            "questions_to_ask",
            "company_research",
        ],
    },
}


async def generate_interview_prep(
    job_data: dict,
    profile_data: dict,
    strategy_data: dict | None,
    provider: LLMProvider,
) -> InterviewPrepResult:
    prompt = f"""You are an expert interview coach preparing a candidate for a job interview.

JOB:
{job_data}

CANDIDATE PROFILE:
{profile_data}

APPLICATION STRATEGY:
{strategy_data or "Not available"}

Generate comprehensive interview preparation materials:
1. 5 technical questions likely to be asked (based on the JD requirements)
2. 5 behavioral questions targeting key competencies for this role
3. 3 STAR story frameworks the candidate can adapt from their experience
4. 5 thoughtful questions the candidate should ask the interviewer
5. Brief company research summary (culture, mission, values) inferred from the JD

Use the generate_interview_prep tool to return structured output."""

    result = await provider.generate(
        prompt=prompt,
        tools=[_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "generate_interview_prep"},
    )

    return InterviewPrepResult(**result)
