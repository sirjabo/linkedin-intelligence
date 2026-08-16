"""CV Storage: generates and stores personalized CV PDF files.

Produces a real PDF via pdf_generator using CVVersion data (adapted summary,
ordered skills, personalized experience bullets) when available, falling back
to raw profile data otherwise.

Path convention: {UPLOAD_DIR}/cv_pdfs/{candidate_id}/{application_id}.pdf
"""
import os
import uuid

import aiofiles

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.application import Application, CVVersion
from app.db.models.candidate import Candidate, CandidateProfile
from app.services.pdf_generator import generate_cv_pdf

logger = get_logger(__name__)

_CV_SUBDIR = "cv_pdfs"


def _cv_dir(candidate_id: uuid.UUID) -> str:
    return os.path.join(settings.UPLOAD_DIR, _CV_SUBDIR, str(candidate_id))


def get_cv_path(candidate_id: uuid.UUID, application_id: uuid.UUID) -> str:
    return os.path.join(_cv_dir(candidate_id), f"{application_id}.pdf")


def cv_exists(candidate_id: uuid.UUID, application_id: uuid.UUID) -> bool:
    return os.path.isfile(get_cv_path(candidate_id, application_id))


async def generate_cv_file(
    candidate: Candidate,
    profile: CandidateProfile | None,
    application: Application,
) -> str:
    """Generate a personalized PDF CV and return its file path.

    Uses the most recent CVVersion on the application (from the intelligence
    phase) when available, otherwise falls back to the raw CandidateProfile.
    """
    dir_path = _cv_dir(candidate.id)
    os.makedirs(dir_path, exist_ok=True)
    file_path = get_cv_path(candidate.id, application.id)

    cv_version = _latest_cv_version(application)
    cv_data = _build_cv_dict(candidate, profile, cv_version)

    pdf_bytes = await generate_cv_pdf(cv_data)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(pdf_bytes)

    logger.info(
        "cv_pdf_generated",
        path=file_path,
        candidate_id=str(candidate.id),
        bytes=len(pdf_bytes),
        personalized=cv_version is not None,
    )
    return file_path


def _latest_cv_version(application: Application) -> CVVersion | None:
    versions = getattr(application, "cv_versions", None) or []
    if not versions:
        return None
    return max(versions, key=lambda v: v.created_at)


def _build_cv_dict(
    candidate: Candidate,
    profile: CandidateProfile | None,
    cv_version: CVVersion | None,
) -> dict:
    """Build the cv_data dict expected by pdf_generator.generate_cv_pdf()."""
    # Contact info
    contact: dict = {}
    if candidate.email:
        contact["email"] = candidate.email
    if candidate.location:
        contact["location"] = candidate.location

    # LinkedIn from sources
    for src in (candidate.sources or []):
        if src.source_type == "linkedin" and src.source_url:
            contact["linkedin"] = src.source_url
        elif src.source_type == "github" and src.source_url:
            contact["github"] = src.source_url
        elif src.source_type == "portfolio" and src.source_url:
            contact["website"] = src.source_url

    # Summary — prefer adapted version from intelligence phase
    if cv_version and cv_version.summary_adapted:
        summary = cv_version.summary_adapted
    elif profile and profile.summary:
        summary = profile.summary
    else:
        summary = ""

    # Target role — from current title or job title if available
    target_role = ""
    if profile and profile.experience:
        exp = profile.experience[0] if isinstance(profile.experience, list) else None
        if exp and isinstance(exp, dict):
            target_role = exp.get("role") or exp.get("title", "")

    # Skills — prefer ordered list from intelligence phase
    skills: dict[str, list[str]] = {}
    if cv_version and cv_version.skills_ordered:
        skills["languages"] = cv_version.skills_ordered
    elif profile and profile.skills:
        raw = profile.skills
        if isinstance(raw, list):
            skills["languages"] = [str(s) for s in raw]
        elif isinstance(raw, dict):
            skills = {k: [str(x) for x in v] for k, v in raw.items() if v}

    # Experience — use personalized bullets from CVVersion when available
    experience: list[dict] = []
    personalized_bullets: dict[str, list[str]] = {}
    if cv_version and cv_version.experience_personalized:
        for ep in cv_version.experience_personalized:
            if isinstance(ep, dict):
                key = (ep.get("company", "") + "|" + ep.get("title", "")).lower()
                adapted = [
                    bc.get("adapted", bc.get("original", ""))
                    for bc in (ep.get("bullets_adapted") or [])
                    if isinstance(bc, dict)
                ]
                if adapted:
                    personalized_bullets[key] = [s for s in adapted if s is not None]

    if profile and profile.experience:
        for exp in (profile.experience or []):
            if not isinstance(exp, dict):
                continue
            company = exp.get("company", "")
            role = exp.get("role") or exp.get("title", "")
            key = (company + "|" + role).lower()
            bullets = personalized_bullets.get(key) or exp.get("bullets") or []
            experience.append({
                "company": company,
                "role": role,
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", "Present"),
                "location": exp.get("location", ""),
                "bullets": bullets,
            })

    # Education
    education: list[dict] = []
    if profile and profile.education:
        for edu in (profile.education or []):
            if not isinstance(edu, dict):
                continue
            education.append({
                "institution": edu.get("institution", ""),
                "degree": edu.get("degree", ""),
                "field": edu.get("field", ""),
                "year": edu.get("year") or edu.get("end_year", ""),
            })

    # Projects — use personalized descriptions from CVVersion when available
    projects: list[dict] = []
    personalized_proj: dict[str, dict] = {}
    if cv_version and cv_version.projects_personalized:
        for pp in cv_version.projects_personalized:
            if isinstance(pp, dict) and pp.get("name"):
                personalized_proj[pp["name"].lower()] = pp

    if profile and profile.projects:
        for proj in (profile.projects or []):
            if not isinstance(proj, dict):
                continue
            name = proj.get("name", "")
            pp = personalized_proj.get(name.lower())
            description = (
                pp.get("description_adapted") or proj.get("description", "")
            ) if pp else proj.get("description", "")
            highlights = (pp.get("highlights_adapted") or []) if pp else []
            projects.append({
                "name": name,
                "description": description,
                "tech": proj.get("tech") or proj.get("technologies") or [],
                "url": proj.get("url", ""),
                "highlights": highlights,
            })

    return {
        "name": candidate.name or "Candidate",
        "target_role": target_role,
        "contact": contact,
        "summary": summary,
        "experience": experience,
        "skills": skills,
        "education": education,
        "projects": projects,
        "certifications": [],
    }
