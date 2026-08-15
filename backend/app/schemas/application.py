import uuid
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID


class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    follow_up_date: date | None = None
    applied_at: datetime | None = None


class AnswersRequest(BaseModel):
    questions: list[str] = Field(..., min_length=1)


class EventCreate(BaseModel):
    event_type: str
    notes: str | None = None
    occurred_at: datetime | None = None


class CVVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    application_id: uuid.UUID
    summary_adapted: str | None
    headline_adapted: str | None
    skills_ordered: list | None
    changes: list | None
    evidence_refs: list | None
    ats_keywords: list | None
    validation_result: dict | None
    created_at: datetime


class CoverLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    application_id: uuid.UUID
    content: str
    evidence_refs: list | None
    validation_result: dict | None
    created_at: datetime


class ApplicationAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    application_id: uuid.UUID
    question: str
    answer: str
    evidence_refs: list | None
    created_at: datetime


class ApplicationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    application_id: uuid.UUID
    event_type: str
    notes: str | None
    occurred_at: datetime
    created_at: datetime


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    strategy: dict | None
    notes: str | None
    follow_up_date: date | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cv_versions: list[CVVersionResponse] = []
    cover_letters: list[CoverLetterResponse] = []
    answers: list[ApplicationAnswerResponse] = []
    events: list[ApplicationEventResponse] = []


class SubmissionCreate(BaseModel):
    confirmation_number: str | None = None
    submission_url: str | None = None
    submitted_via: str = "manual"  # manual | agent | api
    notes: str | None = None


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    application_id: uuid.UUID
    submitted_at: datetime
    confirmation_number: str | None
    submission_url: str | None
    submitted_via: str
    notes: str | None
    created_at: datetime


class ApplicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str | None = None
    job_company: str | None = None
    status: str
    notes: str | None
    follow_up_date: date | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FitAnalysisResponse(BaseModel):
    job_fit_score: float
    career_fit_score: float | None
    match_tier: str
    skill_overlap_score: float
    experience_score: float
    location_score: float
    education_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    llm_strengths: list | None
    llm_gaps: list | None
    llm_reasoning: str | None


class DecisionResponse(BaseModel):
    decision: str
    blockers: list[str]
    overall_approach: str | None


class OutcomeCreate(BaseModel):
    outcome: str  # got_interview | offer | rejected | ghosted | withdrew
