"""CV Storage: manages CV PDF files for browser-based form uploads.

MVP strategy: generate a plain-text CV representation and store it locally.
The file is accessible only inside the container — never exposed as a public URL.

Path convention: {UPLOAD_DIR}/cv_pdfs/{candidate_id}/{application_id}.txt
"""
import os
import uuid
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.application import Application

logger = get_logger(__name__)

_CV_SUBDIR = "cv_pdfs"


def _cv_dir(candidate_id: uuid.UUID) -> str:
    return os.path.join(settings.UPLOAD_DIR, _CV_SUBDIR, str(candidate_id))


def get_cv_path(candidate_id: uuid.UUID, application_id: uuid.UUID) -> str:
    return os.path.join(_cv_dir(candidate_id), f"{application_id}.txt")


def cv_exists(candidate_id: uuid.UUID, application_id: uuid.UUID) -> bool:
    return os.path.isfile(get_cv_path(candidate_id, application_id))


def generate_cv_file(
    candidate: Candidate,
    profile: CandidateProfile | None,
    application: Application,
) -> str:
    """Write a text representation of the CV and return its file path."""
    dir_path = _cv_dir(candidate.id)
    os.makedirs(dir_path, exist_ok=True)
    file_path = get_cv_path(candidate.id, application.id)

    lines = _render_cv(candidate, profile)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("cv_file_generated", path=file_path, candidate_id=str(candidate.id))
    return file_path


def _render_cv(candidate: Candidate, profile: CandidateProfile | None) -> list[str]:
    lines: list[str] = []

    name = candidate.name or "Candidate"
    lines += [name.upper(), "=" * len(name), ""]

    if candidate.email:
        lines.append(f"Email: {candidate.email}")
    if candidate.location:
        lines.append(f"Location: {candidate.location}")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d')}")
    lines.append("")

    if not profile:
        lines.append("(No profile data available)")
        return lines

    if profile.summary:
        lines += ["SUMMARY", "-------", profile.summary, ""]

    if profile.experience:
        lines += ["EXPERIENCE", "----------"]
        for exp in (profile.experience or []):
            if not isinstance(exp, dict):
                continue
            title = exp.get("role") or exp.get("title", "")
            company = exp.get("company", "")
            start = exp.get("start_date", "")
            end = exp.get("end_date", "Present")
            lines.append(f"{title} — {company} ({start} – {end})")
            for bullet in (exp.get("bullets") or [])[:4]:
                lines.append(f"  • {bullet}")
            lines.append("")

    if profile.education:
        lines += ["EDUCATION", "---------"]
        for edu in (profile.education or []):
            if not isinstance(edu, dict):
                continue
            degree = edu.get("degree", "")
            field = edu.get("field", "")
            inst = edu.get("institution", "")
            year = edu.get("year") or edu.get("end_year", "")
            lines.append(f"{degree} in {field} — {inst} ({year})")
        lines.append("")

    if profile.skills:
        lines += ["SKILLS", "------"]
        if isinstance(profile.skills, dict):
            for category, skill_list in profile.skills.items():
                if skill_list:
                    lines.append(f"{category.capitalize()}: {', '.join(str(s) for s in skill_list)}")
        elif isinstance(profile.skills, list):
            lines.append(", ".join(str(s) for s in profile.skills))
        lines.append("")

    return lines
