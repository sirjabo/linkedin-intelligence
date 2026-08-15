"""Profile analysis endpoints — stateless, no DB writes."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from app.api.deps import get_current_user
from app.db.models.user import User
from app.services.linkedin_analyzer import analyze_linkedin_profile, ROLE_LABELS
from app.core.limiter import limiter
from app.core.logging import get_logger

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


@router.post("/linkedin")
@limiter.limit("10/minute")
async def analyze_linkedin(
    request: Request,
    payload: LinkedInAnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Score a LinkedIn profile by section and return optimized title variants.

    Accepts raw text pasted from a LinkedIn profile page.  Returns section
    scores, keyword gaps for the target role, and ordered recommendations.
    No data is persisted — the analysis is ephemeral.
    """
    try:
        result = await analyze_linkedin_profile(
            profile_text=payload.profile_text,
            target_role=payload.target_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

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
