"""Match routes: run and retrieve match analyses for a job."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.job import Job
from app.db.models.match import MatchAnalysis
from app.api.deps import get_current_user
from app.db.models.user import User
from app.schemas.match import MatchResponse
from app.services.matching.engine import compute_deterministic, tier_from_score, DET_WEIGHT
from app.services.agents.match_agent import reason_about_match
from app.core.logging import get_logger

router = APIRouter(prefix="/jobs", tags=["match"])
logger = get_logger(__name__)


async def _get_job_for_user(
    job_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Job:
    """Fetch a job that belongs to the authenticated user, or 404."""
    result = await db.execute(
        select(Job)
        .join(Candidate, Job.candidate_id == Candidate.id)
        .where(Job.id == job_id, Candidate.user_id == user.id)
        .options(selectinload(Job.requirements))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def _get_candidate_data(
    user: User,
    db: AsyncSession,
) -> tuple[Candidate, CandidateProfile | None]:
    """Fetch the candidate + profile for this user."""
    cand_result = await db.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    )
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No candidate profile found. Upload a LinkedIn profile first.",
        )

    # candidate_id is unique — at most one profile per candidate
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = profile_result.scalar_one_or_none()
    return candidate, profile


@router.post("/{job_id}/match", response_model=MatchResponse, status_code=status.HTTP_200_OK)
async def run_match(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run (or re-run) the hybrid matching analysis for a job.

    Deterministic scoring runs every time. LLM reasoning is included.
    Result is upserted — only one analysis per (candidate, job) pair.
    """
    job = await _get_job_for_user(job_id, user, db)
    candidate, profile = await _get_candidate_data(user, db)

    # ── Deterministic scoring ──────────────────────────────────────────────────
    profile_skills: list[dict] = profile.skills if profile and profile.skills else []
    profile_career_level: str | None = profile.career_level if profile else None
    profile_education: list | None = profile.education if profile else None
    # location lives on Candidate, not CandidateProfile
    candidate_location: str | None = candidate.location

    candidate_salary_pref = (
        candidate.preferences.get("salary_min") if candidate.preferences else None
    )
    det_result = compute_deterministic(
        profile_skills=profile_skills,
        profile_career_level=profile_career_level,
        profile_education=profile_education,
        candidate_location=candidate_location,
        job_seniority=job.seniority,
        job_location=job.location,
        job_remote_type=job.remote_type,
        job_tech_stack=job.tech_stack or [],
        requirements=job.requirements,
        job_salary_max=job.salary_max,
        candidate_salary_pref_min=int(candidate_salary_pref) if candidate_salary_pref is not None else None,
    )

    # ── LLM reasoning ─────────────────────────────────────────────────────────
    must_have = [
        r.description for r in job.requirements if r.requirement_type == "must_have"
    ]
    nice_to_have = [
        r.description for r in job.requirements if r.requirement_type == "nice_to_have"
    ]
    skill_names = [
        s.get("canonical_name", "") for s in profile_skills if s.get("canonical_name")
    ]
    candidate_summary = (
        profile.professional_identity.get("summary", "")
        if profile and profile.professional_identity
        else ""
    )

    llm_result = await reason_about_match(
        candidate_summary=candidate_summary,
        candidate_skills=skill_names,
        candidate_career_level=profile_career_level,
        candidate_location=candidate_location,
        job_title=job.title,
        job_company=job.company,
        job_seniority=job.seniority,
        job_location=job.location,
        job_remote_type=job.remote_type,
        job_tech_stack=job.tech_stack or [],
        requirements_must_have=must_have,
        requirements_nice_to_have=nice_to_have,
        deterministic_score=det_result.overall_score,
        matched_skills=det_result.matched_skills,
        missing_skills=det_result.missing_skills,
    )

    # ── Hybrid score ──────────────────────────────────────────────────────────
    hybrid_score = round(
        det_result.overall_score * DET_WEIGHT + llm_result.score * (1 - DET_WEIGHT), 3
    )
    match_tier = tier_from_score(hybrid_score)

    logger.info(
        "match.run_complete",
        job_id=str(job_id),
        candidate_id=str(candidate.id),
        det_score=det_result.overall_score,
        llm_score=llm_result.score,
        hybrid=hybrid_score,
        tier=match_tier,
    )

    # ── Upsert MatchAnalysis ──────────────────────────────────────────────────
    existing_result = await db.execute(
        select(MatchAnalysis).where(
            MatchAnalysis.candidate_id == candidate.id,
            MatchAnalysis.job_id == job.id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    now = datetime.utcnow()

    if existing:
        existing.overall_score = hybrid_score
        existing.deterministic_score = det_result.overall_score
        existing.llm_score = llm_result.score
        existing.match_tier = match_tier
        existing.skill_overlap_score = det_result.skill_overlap_score
        existing.experience_score = det_result.experience_score
        existing.location_score = det_result.location_score
        existing.education_score = det_result.education_score
        existing.matched_skills = det_result.matched_skills
        existing.missing_skills = det_result.missing_skills
        existing.llm_reasoning = llm_result.reasoning
        existing.llm_strengths = llm_result.strengths
        existing.llm_gaps = llm_result.gaps
        existing.updated_at = now
        analysis = existing
    else:
        analysis = MatchAnalysis(
            id=uuid.uuid4(),
            candidate_id=candidate.id,
            job_id=job.id,
            overall_score=hybrid_score,
            deterministic_score=det_result.overall_score,
            llm_score=llm_result.score,
            match_tier=match_tier,
            skill_overlap_score=det_result.skill_overlap_score,
            experience_score=det_result.experience_score,
            location_score=det_result.location_score,
            education_score=det_result.education_score,
            matched_skills=det_result.matched_skills,
            missing_skills=det_result.missing_skills,
            llm_reasoning=llm_result.reasoning,
            llm_strengths=llm_result.strengths,
            llm_gaps=llm_result.gaps,
            created_at=now,
            updated_at=now,
        )
        db.add(analysis)

    await db.commit()
    await db.refresh(analysis)
    return analysis


@router.get("/{job_id}/match", response_model=MatchResponse)
async def get_match(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve the latest match analysis for a job."""
    await _get_job_for_user(job_id, user, db)

    cand_result = await db.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    )
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No match analysis found")

    result = await db.execute(
        select(MatchAnalysis).where(
            MatchAnalysis.job_id == job_id,
            MatchAnalysis.candidate_id == candidate.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No match analysis found")
    return analysis
