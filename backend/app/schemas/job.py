from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobAnalyze(BaseModel):
    raw_jd: str = Field(..., min_length=50, description="Raw job description text (min 50 chars)")
    title: str | None = None
    company: str | None = None
    job_url: str | None = None


class JobCreate(BaseModel):
    raw_jd: str = Field(..., min_length=50, description="Raw job description text (min 50 chars)")
    title: str | None = None
    company: str | None = None
    job_url: str | None = None


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    description: str
    requirement_type: str
    category: str
    is_required: bool
    seniority_signal: str | None
    classification: str | None = None  # MANDATORY | PREFERRED | INFERRED


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    title: str | None
    company: str | None
    location: str | None
    remote_type: str | None
    seniority: str | None
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    tech_stack: list | None
    key_responsibilities: list | None
    company_description: str | None
    parsing_confidence: float | None
    visa_sponsorship: bool | None = None
    job_url: str | None
    status: str
    requirements: list[RequirementResponse] = []
    created_at: datetime
    updated_at: datetime


class ParsedJobResponse(BaseModel):
    """Transient result of /jobs/analyze — not persisted to DB."""
    title: str | None
    company: str | None
    location: str | None
    remote_type: str | None
    seniority: str | None
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    tech_stack: list[str]
    requirements: list[dict]
    key_responsibilities: list[str]
    company_description: str | None
    visa_sponsorship: bool | None = None
    parsing_confidence: float
