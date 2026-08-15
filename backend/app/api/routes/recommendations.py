"""Phase 14 — Job Radar: recommend external jobs ranked by candidate fit.

Supports multiple job sources (Remotive, Arbeitnow, RemoteOK) queried in parallel.
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.models.candidate import Candidate
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.recommendation import RecommendationRequest, RecommendedJobResponse
from app.services.job_recommender import rank_jobs
from app.services.job_sources.base import JobRaw
from app.services.job_sources.remotive import RemotiveSource
from app.services.job_sources.arbeitnow import ArbeitnowSource
from app.services.job_sources.remoteok import RemoteOKSource
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

_ALL_SOURCES = {
    "remotive": RemotiveSource,
    "arbeitnow": ArbeitnowSource,
    "remoteok": RemoteOKSource,
}


async def _fetch_safe(source_name: str, source_cls, query: str, limit: int, category: str | None) -> list[JobRaw]:
    """Fetch from one source; return empty list on any error."""
    try:
        src = source_cls()
        return await src.fetch(query=query, limit=limit, category=category)
    except Exception as exc:
        logger.warning("job_source_failed", source=source_name, error=str(exc))
        return []


@router.get("/sources")
async def list_sources() -> dict:
    """Return the available job source names."""
    return {"sources": sorted(_ALL_SOURCES.keys())}


@router.post("", response_model=list[RecommendedJobResponse], status_code=200)
async def get_recommendations(
    body: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Load candidate + profile
    result = await db.execute(
        select(Candidate)
        .where(Candidate.user_id == current_user.id)
        .options(selectinload(Candidate.profile))
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    profile_data: dict = {}
    if candidate.profile:
        p = candidate.profile
        profile_data = {
            "summary": p.summary,
            "skills": p.skills,
            "experience": p.experience,
            "education": p.education,
        }

    limit = max(1, min(body.limit, 50))

    # Determine which sources to query
    requested = set(body.sources) if body.sources else set(_ALL_SOURCES.keys())
    active_sources = {k: v for k, v in _ALL_SOURCES.items() if k in requested}
    if not active_sources:
        active_sources = _ALL_SOURCES

    # Fetch from all active sources in parallel; per-source limit to avoid huge sets
    per_source_limit = max(limit, 20)
    tasks = [
        _fetch_safe(name, cls, body.query, per_source_limit, body.category)
        for name, cls in active_sources.items()
    ]
    results = await asyncio.gather(*tasks)

    all_jobs: list[JobRaw] = []
    for batch in results:
        all_jobs.extend(batch)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_jobs: list[JobRaw] = []
    for job in all_jobs:
        if job.url and job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)

    ranked = rank_jobs(unique_jobs, profile_data)[:limit]

    return [
        RecommendedJobResponse(
            external_id=s.job.external_id,
            title=s.job.title,
            company=s.job.company,
            location=s.job.location,
            remote_type=s.job.remote_type,
            url=s.job.url,
            tech_tags=s.job.tech_tags,
            salary_range=s.job.salary_range,
            published_at=s.job.published_at,
            score=s.score,
            matched_keywords=s.matched_keywords,
        )
        for s in ranked
    ]
