"""Phase 6 — Interview Prep routes."""
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.interview import InterviewPrep
from app.db.session import get_db
from app.schemas.interview import InterviewPrepResponse
from app.services.agents.interview_agent import generate_interview_prep
from app.services.ai.provider import AnthropicProvider
from app.db.models.user import User

router = APIRouter(prefix="/applications", tags=["interview"])


async def _get_application_for_user(
    application_id: str, current_user: User, db: AsyncSession
) -> Application:
    try:
        app_uuid = _uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Application not found")
    cand_result = await db.execute(
        select(Candidate).where(Candidate.user_id == current_user.id)
    )
    candidate = cand_result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Not found")

    result = await db.execute(
        select(Application)
        .where(Application.id == app_uuid, Application.candidate_id == candidate.id)
        .options(selectinload(Application.interview_prep))
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.post("/{application_id}/interview-prep", response_model=InterviewPrepResponse, status_code=201)
async def create_interview_prep(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await _get_application_for_user(application_id, current_user, db)

    # Load job and profile data
    from app.db.models.job import Job
    job_result = await db.execute(select(Job).where(Job.id == app.job_id))
    job = job_result.scalar_one_or_none()

    cand_result = await db.execute(
        select(Candidate)
        .where(Candidate.user_id == current_user.id)
        .options(selectinload(Candidate.profile))
    )
    candidate = cand_result.scalar_one_or_none()

    if job:
        job_data = {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "seniority": job.seniority,
            "tech_stack": job.tech_stack,
            "key_responsibilities": job.key_responsibilities,
            "company_description": job.company_description,
            "raw_jd": job.raw_jd,
        }
    else:
        job_data = {}
    profile_data: dict = {}
    if candidate and candidate.profile:
        p = candidate.profile
        profile_data = {
            "summary": p.summary,
            "skills": p.skills,
            "experience": p.experience,
            "education": p.education,
        }
    strategy_data = app.strategy

    provider = AnthropicProvider()
    prep_result = await generate_interview_prep(
        job_data=job_data,
        profile_data=profile_data,
        strategy_data=strategy_data,
        provider=provider,
    )

    # Upsert (one InterviewPrep per application)
    if app.interview_prep:
        ip = app.interview_prep
        ip.technical_questions = [q.model_dump() for q in prep_result.technical_questions]
        ip.behavioral_questions = [q.model_dump() for q in prep_result.behavioral_questions]
        ip.star_stories = [s.model_dump() for s in prep_result.star_stories]
        ip.questions_to_ask = prep_result.questions_to_ask
        ip.company_research = prep_result.company_research.model_dump()
    else:
        ip = InterviewPrep(
            application_id=app.id,
            technical_questions=[q.model_dump() for q in prep_result.technical_questions],
            behavioral_questions=[q.model_dump() for q in prep_result.behavioral_questions],
            star_stories=[s.model_dump() for s in prep_result.star_stories],
            questions_to_ask=prep_result.questions_to_ask,
            company_research=prep_result.company_research.model_dump(),
        )
        db.add(ip)

    await db.commit()
    await db.refresh(ip)
    return ip


@router.get("/{application_id}/interview-prep", response_model=InterviewPrepResponse)
async def get_interview_prep(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await _get_application_for_user(application_id, current_user, db)
    if app.interview_prep is None:
        raise HTTPException(status_code=404, detail="Interview prep not generated yet")
    return app.interview_prep
