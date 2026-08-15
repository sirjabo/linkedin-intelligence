import uuid
from datetime import datetime

from pydantic import BaseModel


class TechnicalQuestionResponse(BaseModel):
    question: str
    rationale: str


class BehavioralQuestionResponse(BaseModel):
    question: str
    competency: str


class STARStoryResponse(BaseModel):
    competency: str
    situation: str
    task: str
    action: str
    result: str


class InterviewPrepResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    technical_questions: list[TechnicalQuestionResponse]
    behavioral_questions: list[BehavioralQuestionResponse]
    star_stories: list[STARStoryResponse]
    questions_to_ask: list[str]
    company_research: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
