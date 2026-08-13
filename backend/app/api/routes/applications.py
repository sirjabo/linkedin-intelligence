"""Application routes: full application lifecycle management."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.job import Job
from app.db.models.match import MatchAnalysis
from app.db.models.application import Application, CVVersion, CoverLetter, ApplicationAnswer, ApplicationEvent
from app.api.deps import get_current_user
from app.db.models.user import User
from app.schemas.application import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse, ApplicationListResponse,
    CVVersionResponse, CoverLetterResponse, ApplicationAnswerResponse, ApplicationEventResponse,
    AnswersRequest, EventCreate,
)
from app.services.agents.application_agent import generate_strategy
from app.services.agents.cv_agent import personalize_cv
from app.services.agents.communication_agent import generate_cover_letter, generate_application_answers
from app.services.claim_validator import validate_claims
from app.core.logging import get_logger

router = APIRouter(prefix="/applications", tags=["applications"])
logger = get_logger(__name__)

_APP_LOAD_OPTIONS = [
    selectinload(Application.cv_versions),
    selectinload(Application.cover_letters),
    selectinload(Application.answers),
    selectinload(Application.events),
]


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_candidate(user: User, db: AsyncSession) -> Candidate:
    result = await db.execute(select(Candidate).where(Candidate.user_id == user.id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="No candidate profile found. Upload a profile first.")
    return candidate


async def _get_application(
    app_id: uuid.UUID, candidate: Candidate, db: AsyncSession, *, load_relations: bool = True
) -> Application:
    opts = _APP_LOAD_OPTIONS if load_relations else []
    q = select(Application).where(
        Application.id == app_id,
        Application.candidate_id == candidate.id,
    )
    for opt in opts:
        q = q.options(opt)
    result = await db.execute(q)
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def _get_profile(candidate: Candidate, db: AsyncSession) -> CandidateProfile | None:
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    return result.scalar_one_or_none()


async def _get_match(candidate_id: uuid.UUID, job_id: uuid.UUID, db: AsyncSession) -> MatchAnalysis:
    result = await db.execute(
        select(MatchAnalysis).where(
            MatchAnalysis.candidate_id == candidate_id,
            MatchAnalysis.job_id == job_id,
        )
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Run the match analysis first (POST /jobs/{job_id}/match).",
        )
    return match


async def _get_job(job_id: uuid.UUID, candidate_id: uuid.UUID, db: AsyncSession) -> Job:
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id, Job.candidate_id == candidate_id)
        .options(selectinload(Job.requirements))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _profile_skills(profile: CandidateProfile | None) -> list[str]:
    if not profile or not profile.skills:
        return []
    return [s.get("canonical_name", "") for s in profile.skills if s.get("canonical_name")]


def _ensure_strategy(application: Application) -> dict:
    """Return cached strategy from application record (or raise if missing)."""
    if not application.strategy:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Generate the CV first (POST /applications/{id}/cv) to build the strategy.",
        )
    return application.strategy


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new application (status=draft)."""
    candidate = await _get_candidate(user, db)

    # Verify job belongs to this candidate
    await _get_job(payload.job_id, candidate.id, db)

    application = Application(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        job_id=payload.job_id,
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(application)
    await db.commit()

    result = await db.execute(
        select(Application).where(Application.id == application.id).options(*_APP_LOAD_OPTIONS)
    )
    return result.scalar_one()


@router.get("", response_model=list[ApplicationListResponse])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    candidate = await _get_candidate(user, db)
    result = await db.execute(
        select(Application, Job.title, Job.company)
        .join(Job, Application.job_id == Job.id, isouter=True)
        .where(Application.candidate_id == candidate.id)
        .order_by(Application.created_at.desc())
    )
    rows = result.all()
    apps = []
    for app, job_title, job_company in rows:
        d = {c.key: getattr(app, c.key) for c in app.__table__.columns}
        d["job_title"] = job_title
        d["job_company"] = job_company
        apps.append(ApplicationListResponse.model_validate(d))
    return apps


@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    candidate = await _get_candidate(user, db)
    return await _get_application(app_id, candidate, db)


@router.patch("/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: uuid.UUID,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    candidate = await _get_candidate(user, db)
    application = await _get_application(app_id, candidate, db)

    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(application, key, value)
    application.updated_at = datetime.utcnow()

    await db.commit()
    return await _get_application(app_id, candidate, db)


@router.post("/{app_id}/cv", response_model=CVVersionResponse, status_code=status.HTTP_201_CREATED)
async def generate_cv(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a personalized CV version for this application.

    Also builds and caches the ApplicationStrategy for subsequent generations.
    """
    candidate = await _get_candidate(user, db)
    application = await _get_application(app_id, candidate, db, load_relations=False)
    job = await _get_job(application.job_id, candidate.id, db)
    match = await _get_match(candidate.id, job.id, db)
    profile = await _get_profile(candidate, db)

    skill_names = _profile_skills(profile)
    candidate_summary = (
        profile.professional_identity.get("summary", "") if profile and profile.professional_identity else ""
    ) or (profile.summary if profile else "")

    must_have = [r.description for r in job.requirements if r.requirement_type == "must_have"]
    nice_to_have = [r.description for r in job.requirements if r.requirement_type == "nice_to_have"]

    # ── Step 1: strategy (generate and cache) ─────────────────────────────────
    if not application.strategy:
        strategy_obj = await generate_strategy(
            candidate_summary=candidate_summary,
            candidate_skills=skill_names,
            candidate_career_level=profile.career_level if profile else None,
            candidate_location=candidate.location,
            job_title=job.title,
            job_company=job.company,
            job_seniority=job.seniority,
            job_tech_stack=job.tech_stack or [],
            requirements_must_have=must_have,
            match_tier=match.match_tier,
            match_overall_score=match.overall_score,
            matched_skills=match.matched_skills or [],
            missing_skills=match.missing_skills or [],
            llm_reasoning=match.llm_reasoning,
        )
        application.strategy = strategy_obj.model_dump()
        application.updated_at = datetime.utcnow()
        await db.flush()

    strategy = application.strategy

    # ── Step 2: personalize CV ─────────────────────────────────────────────────
    cv_result = await personalize_cv(
        candidate_summary=candidate_summary,
        candidate_headline=None,
        candidate_skills=skill_names,
        candidate_career_level=profile.career_level if profile else None,
        candidate_experience=profile.experience if profile else None,
        candidate_projects=profile.projects if profile else None,
        job_title=job.title,
        job_company=job.company,
        job_seniority=job.seniority,
        job_tech_stack=job.tech_stack or [],
        requirements_must_have=must_have,
        strategy_guidance=strategy.get("cv_changes", []),
    )

    # ── Step 3: claim validation ───────────────────────────────────────────────
    all_generated_text = (cv_result.summary_adapted or "") + " ".join(
        c.get("adapted", "") if isinstance(c, dict) else c.adapted
        for c in cv_result.changes
    )
    evidence_records = []  # Will be populated when EvidenceRecord is filled
    validation = validate_claims(all_generated_text, evidence_records)

    cv_version = CVVersion(
        id=uuid.uuid4(),
        application_id=application.id,
        summary_adapted=cv_result.summary_adapted,
        headline_adapted=cv_result.headline_adapted,
        skills_ordered=cv_result.skills_ordered,
        changes=[c.model_dump() for c in cv_result.changes],
        evidence_refs=cv_result.evidence_refs,
        ats_keywords=cv_result.ats_keywords_added,
        validation_result=validation.to_dict(),
        created_at=datetime.utcnow(),
    )
    db.add(cv_version)
    await db.commit()
    await db.refresh(cv_version)

    logger.info(
        "applications.cv_generated",
        app_id=str(app_id),
        changes=len(cv_result.changes),
        unverified_claims=len(validation.unverified_claims),
    )
    return cv_version


@router.post("/{app_id}/cover-letter", response_model=CoverLetterResponse, status_code=status.HTTP_201_CREATED)
async def generate_cover_letter_route(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a cover letter using the cached strategy."""
    candidate = await _get_candidate(user, db)
    application = await _get_application(app_id, candidate, db, load_relations=False)
    strategy = _ensure_strategy(application)
    job = await _get_job(application.job_id, candidate.id, db)
    match = await _get_match(candidate.id, job.id, db)
    profile = await _get_profile(candidate, db)

    skill_names = _profile_skills(profile)
    candidate_summary = (
        profile.professional_identity.get("summary", "") if profile and profile.professional_identity else ""
    ) or (profile.summary if profile else "")

    cl_result = await generate_cover_letter(
        candidate_summary=candidate_summary,
        candidate_skills=skill_names,
        candidate_career_level=profile.career_level if profile else None,
        candidate_location=candidate.location,
        job_title=job.title,
        job_company=job.company,
        job_seniority=job.seniority,
        strengths_to_emphasize=strategy.get("strengths_to_emphasize", []),
        cover_letter_key_points=strategy.get("cover_letter_key_points", []),
        match_tier=match.match_tier,
    )

    validation = validate_claims(cl_result.content, [])

    cover_letter = CoverLetter(
        id=uuid.uuid4(),
        application_id=application.id,
        content=cl_result.content,
        evidence_refs=cl_result.evidence_refs,
        validation_result=validation.to_dict(),
        created_at=datetime.utcnow(),
    )
    db.add(cover_letter)
    await db.commit()
    await db.refresh(cover_letter)
    return cover_letter


@router.post("/{app_id}/answers", response_model=list[ApplicationAnswerResponse], status_code=status.HTTP_201_CREATED)
async def generate_answers(
    app_id: uuid.UUID,
    payload: AnswersRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate answers to application-specific questions."""
    candidate = await _get_candidate(user, db)
    application = await _get_application(app_id, candidate, db, load_relations=False)
    strategy = _ensure_strategy(application)
    job = await _get_job(application.job_id, candidate.id, db)
    profile = await _get_profile(candidate, db)

    skill_names = _profile_skills(profile)
    candidate_summary = (
        profile.professional_identity.get("summary", "") if profile and profile.professional_identity else ""
    ) or (profile.summary if profile else "")

    answer_results = await generate_application_answers(
        candidate_summary=candidate_summary,
        candidate_skills=skill_names,
        candidate_career_level=profile.career_level if profile else None,
        candidate_experience=profile.experience if profile else None,
        job_title=job.title,
        job_company=job.company,
        strengths_to_emphasize=strategy.get("strengths_to_emphasize", []),
        questions=payload.questions,
    )

    now = datetime.utcnow()
    saved = []
    for ar in answer_results:
        ans = ApplicationAnswer(
            id=uuid.uuid4(),
            application_id=application.id,
            question=ar.question,
            answer=ar.answer,
            evidence_refs=ar.evidence_refs,
            created_at=now,
        )
        db.add(ans)
        saved.append(ans)

    await db.commit()
    for ans in saved:
        await db.refresh(ans)
    return saved


@router.post("/{app_id}/events", response_model=ApplicationEventResponse, status_code=status.HTTP_201_CREATED)
async def add_event(
    app_id: uuid.UUID,
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record an application lifecycle event."""
    candidate = await _get_candidate(user, db)
    application = await _get_application(app_id, candidate, db, load_relations=False)

    occurred_at = payload.occurred_at or datetime.utcnow()
    event = ApplicationEvent(
        id=uuid.uuid4(),
        application_id=application.id,
        event_type=payload.event_type,
        notes=payload.notes,
        occurred_at=occurred_at,
        created_at=datetime.utcnow(),
    )
    db.add(event)

    # Auto-advance status on meaningful events
    status_map = {
        "applied": "applied",
        "phone_screen": "phone_screen",
        "interview": "interview",
        "offer": "offer",
        "rejected": "rejected",
        "withdrawn": "withdrawn",
    }
    if payload.event_type in status_map:
        application.status = status_map[payload.event_type]
        application.updated_at = datetime.utcnow()
        if payload.event_type == "applied" and not application.applied_at:
            application.applied_at = occurred_at

    await db.commit()
    await db.refresh(event)
    return event


@router.get("/stats/summary")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return application funnel counts and activity stats."""
    candidate = await _get_candidate(user, db)

    rows = await db.execute(
        select(Application.status, func.count(Application.id).label("count"))
        .where(Application.candidate_id == candidate.id)
        .group_by(Application.status)
    )
    by_status: dict[str, int] = {r.status: r.count for r in rows}

    total = sum(by_status.values())

    funnel_stages = ["draft", "applied", "phone_screen", "interview", "offer", "rejected", "withdrawn"]
    funnel = {stage: by_status.get(stage, 0) for stage in funnel_stages}

    return {
        "total": total,
        "funnel": funnel,
        "active": by_status.get("applied", 0) + by_status.get("phone_screen", 0) + by_status.get("interview", 0),
        "offers": by_status.get("offer", 0),
        "rejected": by_status.get("rejected", 0),
    }
