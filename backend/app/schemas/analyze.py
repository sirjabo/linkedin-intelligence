"""Pydantic schemas for CV analysis — matches docs/07-API_SPEC.md."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

TargetRole = Literal["ai_engineer", "data_engineer", "analytics_engineer"]


class KeywordFound(BaseModel):
    keyword: str
    count: int = Field(ge=0)
    weight: float = Field(ge=0.0, le=1.0)


class KeywordMissing(BaseModel):
    keyword: str
    weight: float = Field(ge=0.0, le=1.0)
    suggested_section: str


class KeywordAnalysis(BaseModel):
    found: list[KeywordFound]
    missing: list[KeywordMissing]


class SectionScores(BaseModel):
    contact: int = Field(ge=0, le=100)
    summary: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    skills: int = Field(ge=0, le=100)
    education: int = Field(ge=0, le=100)
    projects: int = Field(ge=0, le=100)


class Recommendation(BaseModel):
    priority: int = Field(ge=1)
    section: str
    type: Literal["add_keyword", "rewrite_bullet", "add_section"]
    message: str
    impact: Literal["very_high", "high", "medium", "low"]
    original: str | None = None
    suggested: str | None = None


class CVAnalysisRequest(BaseModel):
    cv_text: Annotated[str, Field(min_length=100, max_length=50_000)]
    target_role: TargetRole
    target_job_id: UUID | None = None


class CVAnalysisResponse(BaseModel):
    analysis_id: UUID
    ats_score: Annotated[int, Field(ge=0, le=100)]
    target_role: TargetRole
    summary: str
    keyword_analysis: KeywordAnalysis
    section_scores: SectionScores
    recommendations: list[Recommendation]
    processing_time_ms: int = Field(ge=0)
