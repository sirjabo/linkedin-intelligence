from pydantic import BaseModel


class SkillFrequency(BaseModel):
    rank: int
    name: str
    slug: str
    category: str
    frequency_pct: float
    job_count: int
    trend: str  # "stable" for MVP; future: "rising" | "declining" via stored snapshots


class SkillsRadarResponse(BaseModel):
    role: str
    period: str
    total_jobs_analyzed: int
    skills: list[SkillFrequency]


class CompanyHiring(BaseModel):
    rank: int
    name: str
    job_count: int


class MarketTrendItem(BaseModel):
    skill: str
    frequency_pct: float
    job_count: int
    message: str


class MarketTrendsResponse(BaseModel):
    generated_at: str
    role: str | None
    total_jobs_analyzed: int
    top_skills: list[MarketTrendItem]
    top_companies: list[CompanyHiring]
