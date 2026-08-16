from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CandidateCreate(BaseModel):
    name: str | None = None
    email: str | None = None
    location: str | None = None
    target_roles: list[str] | None = None
    preferences: dict[str, Any] | None = None


class CandidateUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    location: str | None = None
    target_roles: list[str] | None = None
    preferences: dict[str, Any] | None = None
    # Knowledge Base 2.0
    work_authorization: str | None = None
    availability: str | None = None
    career_goals: str | None = None
    salary_min_usd: int | None = None
    languages: list[dict[str, str]] | None = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str | None
    email: str | None
    location: str | None
    target_roles: list[str] | None
    preferences: dict[str, Any] | None
    # Knowledge Base 2.0
    work_authorization: str | None = None
    availability: str | None = None
    career_goals: str | None = None
    salary_min_usd: int | None = None
    languages: list | None = None
    created_at: datetime
    updated_at: datetime


class SourceIngest(BaseModel):
    source_type: str  # cv, linkedin, github, portfolio, manual
    raw_text: str | None = None
    source_url: str | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    source_type: str
    source_url: str | None
    extracted_content: dict[str, Any] | None
    extraction_confidence: float | None
    created_at: datetime


class EvidenceItem(BaseModel):
    claim: str
    evidence_type: str
    source_ref: str | None
    source_text: str | None
    strength: float | None


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    summary: str | None
    professional_identity: dict[str, Any] | None
    career_level: str | None
    industries: list | None
    competencies: list | None
    skills: list | None
    experience: list | None
    education: list | None
    projects: list | None
    certifications: list | None
    achievements: list | None
    conflicts: list | None
    version: int
    rebuilt_at: datetime


class ConflictResolution(BaseModel):
    field: str
    chosen_value: Any
    source: str
