"""Pydantic schemas for LinkedIn profile analysis — Sprint 002."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ImpactType = Literal["very_high", "high", "medium", "low"]
TargetRole = Literal[
    "ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer"
]


class LinkedInAnalysisRequest(BaseModel):
    profile_text: str = Field(min_length=50)
    linkedin_url: str = ""
    target_role: TargetRole


class SectionScoresResponse(BaseModel):
    title: float
    about: float
    experience: float
    skills: float
    projects: float
    education: float


class TitleAnalysis(BaseModel):
    current: str
    issues: list[str]
    suggested_variants: list[str]


class RecommendationResponse(BaseModel):
    priority: int
    section: str
    message: str
    impact: ImpactType


class LinkedInAnalysisResponse(BaseModel):
    analysis_id: str
    overall_score: float
    target_role: str
    section_scores: SectionScoresResponse
    title_analysis: TitleAnalysis
    recommendations: list[RecommendationResponse]
    processing_time_ms: int
