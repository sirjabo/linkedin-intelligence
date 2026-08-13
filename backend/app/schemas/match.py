import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    overall_score: float
    deterministic_score: float
    llm_score: float | None
    match_tier: str
    skill_overlap_score: float
    experience_score: float
    location_score: float
    education_score: float
    matched_skills: list | None
    missing_skills: list | None
    llm_reasoning: str | None
    llm_strengths: list | None
    llm_gaps: list | None
    outcome: str | None = None
    created_at: datetime
    updated_at: datetime


class MatchFeedback(BaseModel):
    outcome: str  # offer | interview | phone_screen | rejected | no_response
