import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models.user import User
from app.db.models.candidate import Candidate, CandidateSource, CandidateProfile, EvidenceRecord
from app.api.deps import get_current_user
from app.schemas.candidate import (
    CandidateCreate, CandidateUpdate, CandidateResponse,
    SourceIngest, SourceResponse, ProfileResponse, ConflictResolution,
)
from app.services.pdf_extractor import extract_pdf_text
from app.services.agents.profile_agent import extract_from_source, consolidate_profiles
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = get_logger(__name__)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


async def _get_candidate_or_404(user: User, db: AsyncSession) -> Candidate:
    result = await db.execute(select(Candidate).where(Candidate.user_id == user.id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")
    return candidate


@router.get("/me", response_model=CandidateResponse)
async def get_my_candidate(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Candidate:
    return await _get_candidate_or_404(current_user, db)


@router.put("/me", response_model=CandidateResponse)
async def update_my_candidate(
    payload: CandidateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Candidate:
    candidate = await _get_candidate_or_404(current_user, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(candidate, field, value)
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.post("/me/sources/upload", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv_source(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateSource:
    """Upload a CV PDF and extract structured profile data."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit")

    candidate = await _get_candidate_or_404(current_user, db)

    tmp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}.pdf")
    try:
        async with aiofiles.open(tmp_path, "wb") as f:
            content = await file.read()
            await f.write(content)
        raw_text = await extract_pdf_text(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")

    extracted = await extract_from_source(raw_text, source_type="cv")

    source = CandidateSource(
        candidate_id=candidate.id,
        source_type="cv",
        raw_content=raw_text,
        extracted_content=extracted.model_dump(),
        extraction_confidence=extracted.extraction_confidence,
    )
    db.add(source)

    # Update candidate name/email/location from extraction if not set
    if not candidate.name and extracted.name:
        candidate.name = extracted.name
    if not candidate.email and extracted.email:
        candidate.email = extracted.email
    if not candidate.location and extracted.location:
        candidate.location = extracted.location

    await db.commit()
    await db.refresh(source)
    logger.info("source_uploaded", candidate_id=str(candidate.id), source_type="cv")
    return source


@router.post("/me/sources/text", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def ingest_text_source(
    payload: SourceIngest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateSource:
    """Ingest a text source (LinkedIn paste, GitHub bio, manual input)."""
    valid_types = {"cv", "linkedin", "github", "portfolio", "manual"}
    if payload.source_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"source_type must be one of {valid_types}")
    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is required")

    candidate = await _get_candidate_or_404(current_user, db)
    extracted = await extract_from_source(payload.raw_text, source_type=payload.source_type)

    source = CandidateSource(
        candidate_id=candidate.id,
        source_type=payload.source_type,
        source_url=payload.source_url,
        raw_content=payload.raw_text,
        extracted_content=extracted.model_dump(),
        extraction_confidence=extracted.extraction_confidence,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    logger.info("source_ingested", candidate_id=str(candidate.id), source_type=payload.source_type)
    return source


@router.get("/me/sources", response_model=list[SourceResponse])
async def list_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CandidateSource]:
    candidate = await _get_candidate_or_404(current_user, db)
    result = await db.execute(
        select(CandidateSource)
        .where(CandidateSource.candidate_id == candidate.id)
        .order_by(CandidateSource.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/me/profile/rebuild", response_model=ProfileResponse)
async def rebuild_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Consolidate all sources into a unified candidate profile."""
    candidate = await _get_candidate_or_404(current_user, db)

    result = await db.execute(
        select(CandidateSource).where(CandidateSource.candidate_id == candidate.id)
    )
    sources = list(result.scalars().all())
    if not sources:
        raise HTTPException(status_code=400, detail="No sources found. Upload a CV or add a source first.")

    extracted_pairs = []
    for src in sources:
        if src.extracted_content:
            from app.services.agents.profile_agent import ExtractedProfile
            extracted_pairs.append((src.source_type, ExtractedProfile.model_validate(src.extracted_content)))

    if not extracted_pairs:
        raise HTTPException(status_code=400, detail="Sources have no extracted content yet")

    consolidated = await consolidate_profiles(extracted_pairs)

    # Upsert the profile
    existing = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = existing.scalar_one_or_none()
    if profile:
        profile.summary = consolidated.summary
        profile.professional_identity = consolidated.professional_identity
        profile.career_level = consolidated.career_level
        profile.industries = consolidated.industries
        profile.competencies = consolidated.competencies
        profile.skills = consolidated.skills
        profile.experience = consolidated.experience
        profile.education = consolidated.education
        profile.projects = consolidated.projects
        profile.certifications = consolidated.certifications
        profile.achievements = consolidated.achievements
        profile.conflicts = [c.model_dump() for c in consolidated.conflicts]
        profile.version = (profile.version or 1) + 1
    else:
        profile = CandidateProfile(
            candidate_id=candidate.id,
            summary=consolidated.summary,
            professional_identity=consolidated.professional_identity,
            career_level=consolidated.career_level,
            industries=consolidated.industries,
            competencies=consolidated.competencies,
            skills=consolidated.skills,
            experience=consolidated.experience,
            education=consolidated.education,
            projects=consolidated.projects,
            certifications=consolidated.certifications,
            achievements=consolidated.achievements,
            conflicts=[c.model_dump() for c in consolidated.conflicts],
        )
        db.add(profile)

    # Rebuild evidence records
    await db.execute(
        EvidenceRecord.__table__.delete().where(EvidenceRecord.candidate_id == candidate.id)
    )
    for skill in consolidated.skills:
        for ev in skill.get("evidence", []):
            db.add(EvidenceRecord(
                candidate_id=candidate.id,
                claim=skill.get("canonical_name", ""),
                evidence_type="skill",
                source_ref=skill.get("canonical_name"),
                source_text=ev.get("source_text"),
                strength=ev.get("strength"),
            ))
    for exp in consolidated.experience:
        title = exp.get("title") or exp.get("role") or ""
        company = exp.get("company", "")
        claim = f"{title} at {company}".strip(" at ")
        if claim:
            db.add(EvidenceRecord(
                candidate_id=candidate.id,
                claim=claim,
                evidence_type="experience",
                source_ref=company or title,
                source_text=exp.get("description"),
                strength=1.0,
            ))
    for proj in consolidated.projects:
        name = proj.get("name") or proj.get("title") or ""
        if name:
            db.add(EvidenceRecord(
                candidate_id=candidate.id,
                claim=name,
                evidence_type="project",
                source_ref=name,
                source_text=proj.get("description"),
                strength=0.8,
            ))
    for ach in consolidated.achievements:
        text = ach if isinstance(ach, str) else ach.get("text") or ach.get("description") or ""
        if text:
            db.add(EvidenceRecord(
                candidate_id=candidate.id,
                claim=text[:200],
                evidence_type="achievement",
                source_ref=None,
                source_text=text if len(text) > 200 else None,
                strength=0.9,
            ))

    await db.commit()
    await db.refresh(profile)
    logger.info("profile_rebuilt", candidate_id=str(candidate.id), conflicts=len(consolidated.conflicts))
    return profile


@router.get("/me/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    candidate = await _get_candidate_or_404(current_user, db)
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Call /me/profile/rebuild first.")
    return profile
