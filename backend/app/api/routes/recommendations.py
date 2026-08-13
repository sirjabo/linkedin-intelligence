"""Phase 5 — Job Discovery: recommend external jobs ranked by candidate fit."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.recommendation import RecommendationRequest, RecommendedJobResponse
from app.services.job_recommender import rank_jobs
from app.services.job_sources.remotive import RemotiveSource

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


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

    source = RemotiveSource()
    jobs = await source.fetch(query=body.query, limit=limit, category=body.category)

    ranked = rank_jobs(jobs, profile_data)

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
