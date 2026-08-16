import contextlib
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.ssrf import validate_url_not_private
from app.db.models.candidate import Candidate, CandidateProfile, CandidateSource, EvidenceRecord
from app.db.models.match import MatchAnalysis
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.candidate import (
    CandidateResponse,
    CandidateUpdate,
    ProfileResponse,
    SourceIngest,
    SourceResponse,
)
from app.services.agents.profile_agent import consolidate_profiles, extract_from_source
from app.services.github_ingestion import fetch_github_profile
from app.services.learning_loop import compute_calibration
from app.services.pdf_extractor import extract_pdf_text
from app.services.profile_optimizer import generate_optimization_report

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
        with contextlib.suppress(OSError):
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

    if payload.source_url:
        validate_url_not_private(payload.source_url)

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


@router.post("/me/sources/github", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def ingest_github_source(
    payload: SourceIngest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateSource:
    """Ingest a GitHub profile via the GitHub public API.

    payload.source_url must be a GitHub profile URL (e.g. https://github.com/username)
    or a plain GitHub username. The API fetches repos, languages, and bio automatically.
    """
    if not payload.source_url:
        raise HTTPException(status_code=400, detail="source_url (GitHub profile URL or username) is required")

    candidate = await _get_candidate_or_404(current_user, db)

    try:
        profile_data = await fetch_github_profile(payload.source_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}") from exc

    # Build a text representation for extraction pipeline compatibility
    skills_text = ", ".join(s["canonical_name"] for s in profile_data.get("skills", []))
    projects_text = "; ".join(
        f"{p['name']}: {p['description']}" for p in profile_data.get("projects", []) if p.get("description")
    )
    raw_text = "\n".join(filter(None, [
        f"Name: {profile_data.get('name', '')}",
        f"Location: {profile_data.get('location', '')}",
        f"Bio: {profile_data.get('summary', '')}",
        f"Skills: {skills_text}",
        f"Projects: {projects_text}",
        f"GitHub: {profile_data.get('github_url', '')}",
    ]))

    source = CandidateSource(
        candidate_id=candidate.id,
        source_type="github",
        source_url=profile_data.get("github_url") or payload.source_url,
        raw_content=raw_text,
        extracted_content=profile_data,
        extraction_confidence=profile_data.get("extraction_confidence", 0.65),
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    logger.info("github_source_ingested", candidate_id=str(candidate.id))
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
        EvidenceRecord.__table__.delete().where(EvidenceRecord.candidate_id == candidate.id)  # type: ignore[attr-defined]
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
        claim = " at ".join(filter(None, [title, company]))
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


@router.get("/me/health")
async def profile_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a profile completeness/health score with per-section breakdown."""
    candidate = await _get_candidate_or_404(current_user, db)

    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = profile_result.scalar_one_or_none()

    sources_result = await db.execute(
        select(CandidateSource).where(CandidateSource.candidate_id == candidate.id)
    )
    source_count = len(sources_result.scalars().all())

    checks = {
        "name": bool(candidate.name),
        "location": bool(candidate.location),
        "target_roles": bool(candidate.target_roles),
        "source_uploaded": source_count > 0,
        "profile_built": profile is not None,
        "summary": bool(profile and profile.summary),
        "skills": bool(profile and profile.skills),
        "experience": bool(profile and profile.experience),
        "education": bool(profile and profile.education),
        "career_level": bool(profile and profile.career_level),
    }

    passed = sum(checks.values())
    total = len(checks)
    score = round(passed / total, 2)

    tips = []
    if not checks["name"]:
        tips.append("Agregá tu nombre completo")
    if not checks["location"]:
        tips.append("Indicá tu ubicación para mejorar el matching de location")
    if not checks["target_roles"]:
        tips.append("Definí tus roles objetivo para recibir mejores recomendaciones")
    if not checks["source_uploaded"]:
        tips.append("Subí tu CV o perfil de LinkedIn")
    elif not checks["profile_built"]:
        tips.append("Reconstruí tu perfil consolidado después de subir fuentes")
    if not checks["skills"]:
        tips.append("Tu perfil no tiene skills identificados — revisá la fuente cargada")
    if not checks["experience"]:
        tips.append("No se encontró experiencia laboral en tu perfil")

    return {
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "tips": tips,
    }


@router.get("/me/learning-insights")
async def get_learning_insights(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return calibration insights derived from match outcomes.

    Aggregates all matches that have an outcome recorded via the feedback endpoint
    and computes whether the scoring engine is over/under-optimistic for this candidate.
    """
    cand_result = await db.execute(select(Candidate).where(Candidate.user_id == current_user.id))
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        return compute_calibration([]).model_dump() if False else {
            "total_outcomes": 0,
            "by_tier": [],
            "overall_interview_rate": None,
            "bias_direction": "insufficient_data",
            "calibration_score": None,
            "insights": ["Create a candidate profile first."],
        }

    rows = await db.execute(
        select(MatchAnalysis.match_tier, MatchAnalysis.outcome)
        .where(MatchAnalysis.candidate_id == candidate.id)
    )
    outcomes = [{"tier": r.match_tier, "outcome": r.outcome} for r in rows]
    report = compute_calibration(outcomes)

    return {
        "total_outcomes": report.total_outcomes,
        "by_tier": [
            {
                "tier": t.tier,
                "total_applications": t.total_applications,
                "outcomes_recorded": t.outcomes_recorded,
                "interview_rate": t.interview_rate,
                "rejection_rate": t.rejection_rate,
                "expected_interview_rate": t.expected_interview_rate,
            }
            for t in report.by_tier
        ],
        "overall_interview_rate": report.overall_interview_rate,
        "bias_direction": report.bias_direction,
        "calibration_score": report.calibration_score,
        "insights": report.insights,
    }


@router.get("/me/profile-optimizer")
async def get_profile_optimizer(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return prioritized profile improvement tips based on match history.

    Aggregates skill gaps across all MatchAnalysis rows for the candidate,
    generates actionable tips, and optionally enriches with an LLM summary.
    """
    candidate = await _get_candidate_or_404(current_user, db)

    # Load profile data
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = profile_result.scalar_one_or_none()
    profile_data: dict = {}
    if profile:
        profile_data = {
            "summary": profile.summary,
            "skills": profile.skills,
            "experience": profile.experience,
            "education": profile.education,
        }

    # Load all match analyses
    analyses_result = await db.execute(
        select(MatchAnalysis)
        .where(MatchAnalysis.candidate_id == candidate.id)
    )
    analyses = [
        {
            "match_tier": row.match_tier,
            "overall_score": row.overall_score,
            "missing_skills": row.missing_skills or [],
            "matched_skills": row.matched_skills or [],
            "llm_gaps": row.llm_gaps or [],
        }
        for row in analyses_result.scalars().all()
    ]

    report = await generate_optimization_report(analyses, profile_data)

    return {
        "total_analyses_reviewed": report.total_analyses_reviewed,
        "summary": report.summary,
        "top_skill_gaps": [
            {"skill": g.skill, "frequency": g.frequency}
            for g in report.top_skill_gaps
        ],
        "tips": [
            {
                "priority": t.priority,
                "category": t.category,
                "tip": t.tip,
                "evidence": t.evidence,
                "impact": t.impact,
            }
            for t in report.tips
        ],
    }


@router.get("/me/benchmark")
async def get_profile_benchmark(
    role: str = "ai_engineer",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compare candidate's skills against market demand for a given role.

    Reads from the SkillSnapshot table (populated by the nightly Celery task)
    for speed and reliability. Falls back to a live aggregate when no snapshot
    data exists yet (first day of deployment).
    """
    from app.api.routes.market import _VALID_ROLES, ROLE_QUERIES, _aggregate_skills, _slugify
    from app.db.models.market import SkillSnapshot

    if role not in ROLE_QUERIES:
        raise HTTPException(status_code=422, detail=f"role must be one of: {', '.join(_VALID_ROLES)}")

    candidate = await _get_candidate_or_404(current_user, db)

    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = profile_result.scalar_one_or_none()

    candidate_skills: set[str] = set()
    if profile and profile.skills:
        skills_data = profile.skills
        if isinstance(skills_data, list):
            for s in skills_data:
                name = s.get("name") or s.get("skill") or (s if isinstance(s, str) else "")
                if name:
                    candidate_skills.add(_slugify(str(name)))
        elif isinstance(skills_data, dict):
            for skill_list in skills_data.values():
                if isinstance(skill_list, list):
                    for s in skill_list:
                        if isinstance(s, str):
                            candidate_skills.add(_slugify(s))

    # Prefer DB snapshot (fast) over live aggregate (slow, external HTTP)
    latest_date_result = await db.execute(
        select(func.max(SkillSnapshot.snapshot_date)).where(SkillSnapshot.role == role)
    )
    latest_date = latest_date_result.scalar_one_or_none()

    top_market: list[tuple[str, float, int]] = []

    if latest_date is not None:
        snapshots_result = await db.execute(
            select(SkillSnapshot)
            .where(SkillSnapshot.role == role, SkillSnapshot.snapshot_date == latest_date)
            .order_by(SkillSnapshot.frequency_pct.desc())
            .limit(30)
        )
        for row in snapshots_result.scalars().all():
            top_market.append((row.skill_slug, row.frequency_pct, row.job_count))
    else:
        _jobs, tag_counter = await _aggregate_skills(role, limit=30)
        for slug, count in tag_counter.most_common(30):
            freq_pct = round(count / len(_jobs) * 100, 1) if _jobs else 0.0
            top_market.append((slug, freq_pct, count))

    matched = []
    missing = []
    for slug, freq_pct, job_count in top_market:
        entry = {"skill": slug, "frequency_pct": freq_pct, "job_count": job_count}
        if slug in candidate_skills or any(slug in cs or cs in slug for cs in candidate_skills if len(cs) >= 3):
            matched.append(entry)
        else:
            missing.append(entry)

    total = len(top_market)
    match_count = len(matched)
    percentile = round(match_count / total * 100) if total else 0

    tier = (
        "Excelente" if percentile >= 75
        else "Bueno" if percentile >= 50
        else "En desarrollo" if percentile >= 25
        else "Inicial"
    )

    return {
        "role": role,
        "percentile": percentile,
        "tier": tier,
        "matched_count": match_count,
        "total_checked": total,
        "matched_skills": matched,
        "missing_skills": missing,
        "profile_has_skills": len(candidate_skills) > 0,
        "message": (
            f"Tenés {match_count} de las {total} skills más demandadas para {role}. "
            f"Estás en el percentil {percentile}."
        ),
    }


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete the current user's account and all associated data (GDPR compliance).

    Cascade deletes: candidate → sources, profile, evidence, jobs, applications, match analyses.
    """
    # Delete the user; all related data is deleted via DB cascade (ondelete="CASCADE")
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user:
        await db.delete(user)
        await db.commit()
    logger.info("account_deleted", user_id=str(current_user.id))
