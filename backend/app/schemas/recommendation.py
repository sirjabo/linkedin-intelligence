from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    query: str = ""
    limit: int = 20
    category: str | None = None
    sources: list[str] | None = None  # None = all available; e.g. ["remotive", "arbeitnow", "remoteok"]


class RecommendedJobResponse(BaseModel):
    external_id: str
    title: str
    company: str
    location: str
    remote_type: str
    url: str
    tech_tags: list[str]
    salary_range: str | None
    published_at: str | None
    score: float
    matched_keywords: list[str]
