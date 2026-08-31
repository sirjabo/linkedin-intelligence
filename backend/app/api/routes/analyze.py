"""Profile analysis endpoints — stateless, no DB writes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.db.models.user import User
from app.services.about_writer import write_about_section
from app.services.linkedin_analyzer import ROLE_LABELS, analyze_linkedin_profile
from app.services.linkedin_fetcher import fetch_linkedin_profile
from app.services.linkedin_rewriter import rewrite_linkedin_sections

logger = get_logger(__name__)
router = APIRouter(prefix="/analyze", tags=["analyze"])

_VALID_ROLES = sorted(ROLE_LABELS.keys())


class LinkedInAnalyzeRequest(BaseModel):
    profile_text: str
    target_role: str = "ai_engineer"
    linkedin_url: str | None = None

    @field_validator("profile_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("profile_text must not be empty")
        return v

    @field_validator("target_role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in ROLE_LABELS:
            raise ValueError(f"target_role must be one of: {', '.join(sorted(ROLE_LABELS))}")
        return v


class LinkedInURLRequest(BaseModel):
    linkedin_url: str
    target_role: str = "ai_engineer"

    @field_validator("target_role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in ROLE_LABELS:
            raise ValueError(f"target_role must be one of: {', '.join(sorted(ROLE_LABELS))}")
        return v


class LinkedInRewriteRequest(BaseModel):
    profile_text: str
    target_role: str = "ai_engineer"
    analysis: dict

    @field_validator("profile_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("profile_text must not be empty")
        return v

    @field_validator("target_role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in ROLE_LABELS:
            raise ValueError(f"target_role must be one of: {', '.join(sorted(ROLE_LABELS))}")
        return v


class AboutWriterRequest(BaseModel):
    target_role: str = "ai_engineer"
    profile_summary: str = ""
    current_about: str | None = None
    key_skills: list[str] | None = None
    achievements: list[str] | None = None

    @field_validator("target_role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in ROLE_LABELS:
            raise ValueError(f"target_role must be one of: {', '.join(sorted(ROLE_LABELS))}")
        return v

    @field_validator("profile_summary")
    @classmethod
    def summary_not_too_short(cls, v: str) -> str:
        if v and len(v.strip()) < 20:
            raise ValueError("profile_summary is too short to be useful")
        return v


@router.post("/linkedin")
@limiter.limit("10/minute")
async def analyze_linkedin(
    request: Request,
    payload: LinkedInAnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Score a LinkedIn profile by section and return optimized title variants."""
    try:
        result = await analyze_linkedin_profile(
            profile_text=payload.profile_text,
            target_role=payload.target_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info(
        "linkedin_analyzed",
        user_id=str(current_user.id),
        role=payload.target_role,
        overall_score=result["overall_score"],
    )
    return result


@router.get("/linkedin/roles")
async def list_analyze_roles() -> dict:
    """Return role slugs supported by the LinkedIn analyzer."""
    return {"roles": _VALID_ROLES}


@router.post("/linkedin-url")
@limiter.limit("5/minute")
async def analyze_linkedin_from_url(
    request: Request,
    payload: LinkedInURLRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Fetch a public LinkedIn profile by URL, extract its text, and analyze it."""
    try:
        profile_text = await fetch_linkedin_profile(payload.linkedin_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        result = await analyze_linkedin_profile(
            profile_text=profile_text,
            target_role=payload.target_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    result["profile_text"] = profile_text
    logger.info("linkedin_url_analyzed", user_id=str(current_user.id), role=payload.target_role)
    return result


@router.post("/linkedin/rewrite")
@limiter.limit("5/minute")
async def rewrite_linkedin(
    request: Request,
    payload: LinkedInRewriteRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate ready-to-copy rewrites for each LinkedIn section based on analysis."""
    try:
        result = await rewrite_linkedin_sections(
            profile_text=payload.profile_text,
            target_role=payload.target_role,
            analysis=payload.analysis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info("linkedin_rewritten", user_id=str(current_user.id), role=payload.target_role)
    return result


@router.post("/about-writer")
@limiter.limit("10/minute")
async def generate_about_section(
    request: Request,
    payload: AboutWriterRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate 3 optimized LinkedIn About section variants using AI.

    Accepts profile context (summary, current About, skills, achievements)
    and returns 3 tone-differentiated variants ready to copy-paste.
    Stateless — no data is persisted.
    """
    try:
        result = await write_about_section(
            profile_summary=payload.profile_summary,
            target_role=payload.target_role,
            current_about=payload.current_about,
            key_skills=payload.key_skills,
            achievements=payload.achievements,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info(
        "about_written",
        user_id=str(current_user.id),
        role=payload.target_role,
    )
    return result
