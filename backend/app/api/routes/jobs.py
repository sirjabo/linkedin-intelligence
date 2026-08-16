import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.db.models.candidate import Candidate
from app.db.models.job import Job, JobRequirement
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.job import JobAnalyze, JobCreate, JobResponse, ParsedJobResponse
from app.services.agents.job_agent import parse_job_description


def _jd_hash(raw_jd: str) -> str:
    """Stable fingerprint for deduplication — lowercased, whitespace-normalized."""
    normalized = " ".join(raw_jd.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)


async def _get_candidate_or_404(user: User, db: AsyncSession) -> Candidate:
    result = await db.execute(select(Candidate).where(Candidate.user_id == user.id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")
    return candidate


@router.post("/analyze", response_model=ParsedJobResponse)
async def analyze_job(
    payload: JobAnalyze,
    current_user: User = Depends(get_current_user),
) -> ParsedJobResponse:
    """Parse a job description without saving — useful for previewing before saving."""
    parsed = await parse_job_description(payload.raw_jd)
    # User-supplied fields take precedence over parsed values
    if payload.title:
        parsed.title = payload.title
    if payload.company:
        parsed.company = payload.company
    return ParsedJobResponse(
        title=parsed.title,
        company=parsed.company,
        location=parsed.location,
        remote_type=parsed.remote_type,
        seniority=parsed.seniority,
        employment_type=parsed.employment_type,
        salary_min=parsed.salary_min,
        salary_max=parsed.salary_max,
        salary_currency=parsed.salary_currency,
        tech_stack=parsed.tech_stack,
        requirements=[r.model_dump() for r in parsed.requirements],
        key_responsibilities=parsed.key_responsibilities,
        company_description=parsed.company_description,
        visa_sponsorship=parsed.visa_sponsorship,
        parsing_confidence=parsed.parsing_confidence,
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    """Parse a job description and save it to the candidate's tracked jobs.

    Returns HTTP 200 with the existing job if the same JD was already saved (dedup).
    Returns HTTP 201 on first save.
    """
    candidate = await _get_candidate_or_404(current_user, db)

    # Deduplication check before expensive LLM parse
    jd_fingerprint = _jd_hash(payload.raw_jd)
    existing_result = await db.execute(
        select(Job)
        .options(selectinload(Job.requirements))
        .where(Job.candidate_id == candidate.id, Job.jd_hash == jd_fingerprint)
    )
    existing_job = existing_result.scalar_one_or_none()
    if existing_job:
        logger.info("job_dedup_hit", job_id=str(existing_job.id), candidate_id=str(candidate.id))
        return existing_job

    parsed = await parse_job_description(payload.raw_jd)

    job = Job(
        candidate_id=candidate.id,
        jd_hash=jd_fingerprint,
        title=payload.title or parsed.title,
        company=payload.company or parsed.company,
        job_url=payload.job_url,
        location=parsed.location,
        remote_type=parsed.remote_type,
        seniority=parsed.seniority,
        employment_type=parsed.employment_type,
        salary_min=parsed.salary_min,
        salary_max=parsed.salary_max,
        salary_currency=parsed.salary_currency,
        tech_stack=parsed.tech_stack,
        key_responsibilities=parsed.key_responsibilities,
        company_description=parsed.company_description,
        parsing_confidence=parsed.parsing_confidence,
        visa_sponsorship=parsed.visa_sponsorship,
        raw_jd=payload.raw_jd,
        status="analyzed",
    )
    db.add(job)
    await db.flush()

    for req in parsed.requirements:
        db.add(JobRequirement(
            job_id=job.id,
            description=req.description,
            requirement_type=req.requirement_type,
            category=req.category,
            is_required=req.is_required,
            seniority_signal=req.seniority_signal,
            classification=req.classification,
        ))

    await db.commit()

    # Reload with requirements eagerly to avoid lazy-load error during serialization
    result = await db.execute(
        select(Job).options(selectinload(Job.requirements)).where(Job.id == job.id)
    )
    job = result.scalar_one()
    logger.info("job_created", job_id=str(job.id), candidate_id=str(candidate.id), requirements=len(job.requirements))
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
) -> list[Job]:
    """List the current user's saved jobs, newest first."""
    candidate = await _get_candidate_or_404(current_user, db)
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.requirements))
        .where(Job.candidate_id == candidate.id)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    """Get a specific job by ID — only accessible to the owning user."""
    candidate = await _get_candidate_or_404(current_user, db)
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.requirements))
        .where(Job.id == job_id, Job.candidate_id == candidate.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
