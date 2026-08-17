"""POST /analyze/cv — accepts JSON (MVP) or multipart (API spec)."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.rate_limit import limiter
from app.core.logging import get_logger
from app.db.models.cv_analysis import CVAnalysis
from app.engine.ats import ATSEngine
from app.engine.linkedin import ProfileParser, ProfileScorer
from app.engine.pdf import PDFParseError, extract_text_from_pdf
from app.schemas.analyze import CVAnalysisRequest, CVAnalysisResponse
from app.schemas.linkedin import LinkedInAnalysisRequest, LinkedInAnalysisResponse

router = APIRouter(prefix="/analyze", tags=["analyze"])
logger = get_logger(__name__)

SUPPORTED_ROLES = frozenset(
    {"ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer"}
)


@router.post("/cv", response_model=CVAnalysisResponse)
@limiter.limit("30/minute")
async def analyze_cv(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CVAnalysisResponse:
    """Analyze a CV and return ATS Score + recommendations."""
    started = time.perf_counter()
    target_role, text, target_job_id = await _parse_request(request)

    if target_role not in SUPPORTED_ROLES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ROLE",
                "message": (
                    f"El rol '{target_role}' no es válido. Roles soportados: "
                    f"{', '.join(sorted(SUPPORTED_ROLES))}"
                ),
                "docs_url": "https://docs.linkedin-intelligence.com/errors/INVALID_ROLE",
            },
        )

    if len(text) < 100:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CV_TOO_SHORT",
                "message": "El CV debe tener al menos 100 caracteres",
            },
        )

    engine = ATSEngine(db)
    result = await engine.analyze(text, target_role)

    analysis_id = uuid.uuid4()
    cv_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    job_uuid = None
    if target_job_id:
        try:
            job_uuid = uuid.UUID(str(target_job_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_JOB_ID",
                    "message": "target_job_id debe ser un UUID válido",
                },
            ) from exc

    record = CVAnalysis(
        id=analysis_id,
        cv_text=text[:50_000],
        target_role=target_role,
        target_job_id=job_uuid,
        ats_score=result.ats_score,
        keyword_match_pct=None,
        keywords_found=[k.model_dump() for k in result.keyword_analysis.found],
        keywords_missing=[k.model_dump() for k in result.keyword_analysis.missing],
        section_scores=result.section_scores.model_dump(),
        suggestions=[r.model_dump() for r in result.recommendations],
        cv_hash=cv_hash,
    )
    db.add(record)
    await db.flush()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "cv_analyzed",
        analysis_id=str(analysis_id),
        score=result.ats_score,
        role=target_role,
        processing_time_ms=elapsed_ms,
    )

    return CVAnalysisResponse(
        analysis_id=analysis_id,
        ats_score=result.ats_score,
        target_role=target_role,  # type: ignore[arg-type]
        summary=result.summary,
        keyword_analysis=result.keyword_analysis,
        section_scores=result.section_scores,
        recommendations=result.recommendations,
        processing_time_ms=elapsed_ms,
    )


async def _parse_request(request: Request) -> tuple[str, str, str | None]:
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            payload: dict[str, Any] = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_JSON", "message": "JSON inválido"},
            ) from exc

        target_role = str(payload.get("target_role") or "")
        if target_role not in SUPPORTED_ROLES:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_ROLE",
                    "message": (
                        f"El rol '{target_role}' no es válido. Roles soportados: "
                        f"{', '.join(sorted(SUPPORTED_ROLES))}"
                    ),
                    "docs_url": "https://docs.linkedin-intelligence.com/errors/INVALID_ROLE",
                },
            )

        try:
            body = CVAnalysisRequest.model_validate(payload)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": str(exc)},
            ) from exc
        return (
            body.target_role,
            body.cv_text,
            str(body.target_job_id) if body.target_job_id else None,
        )

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        target_role = str(form.get("target_role") or "")
        cv_text_raw = form.get("cv_text")
        cv_text = str(cv_text_raw) if cv_text_raw else None
        target_job_id = form.get("target_job_id")
        upload = form.get("file")

        text = ""
        if upload is not None and hasattr(upload, "read"):
            raw = await upload.read()  # type: ignore[union-attr]
            filename = getattr(upload, "filename", "") or ""
            content = getattr(upload, "content_type", "") or ""
            if "pdf" in content.lower() or filename.lower().endswith(".pdf"):
                try:
                    text = extract_text_from_pdf(raw)
                except PDFParseError as exc:
                    raise HTTPException(
                        status_code=422,
                        detail={"code": "PDF_PARSE_ERROR", "message": str(exc)},
                    ) from exc
            else:
                text = raw.decode("utf-8", errors="replace")
        elif cv_text:
            text = cv_text.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "MISSING_CV",
                    "message": "Debés enviar 'cv_text' o un archivo PDF en 'file'",
                },
            )
        job_id = str(target_job_id) if target_job_id else None
        return target_role, text, job_id

    raise HTTPException(
        status_code=415,
        detail={
            "code": "UNSUPPORTED_MEDIA_TYPE",
            "message": "Usá application/json o multipart/form-data",
        },
    )


@router.post("/linkedin", response_model=LinkedInAnalysisResponse)
@limiter.limit("30/minute")
async def analyze_linkedin(request: Request) -> LinkedInAnalysisResponse:
    """Analyze a pasted LinkedIn profile and return section scores."""
    started = time.perf_counter()
    try:
        raw = await request.json()
        payload = LinkedInAnalysisRequest.model_validate(raw)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": str(exc)},
        ) from exc

    if payload.target_role not in SUPPORTED_ROLES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ROLE",
                "message": (
                    f"El rol '{payload.target_role}' no es válido. Roles soportados: "
                    f"{', '.join(sorted(SUPPORTED_ROLES))}"
                ),
            },
        )

    parsed = ProfileParser().parse(payload.profile_text)
    result = ProfileScorer().score(parsed, payload.target_role)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return LinkedInAnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        overall_score=result.overall_score,
        target_role=payload.target_role,
        section_scores={
            "title": result.section_scores.title,
            "about": result.section_scores.about,
            "experience": result.section_scores.experience,
            "skills": result.section_scores.skills,
            "projects": result.section_scores.projects,
            "education": result.section_scores.education,
        },
        title_analysis={
            "current": result.title_analysis.current,
            "issues": result.title_analysis.issues,
            "suggested_variants": result.title_analysis.suggested_variants,
        },
        recommendations=[
            {
                "priority": rec.priority,
                "section": rec.section,
                "message": rec.message,
                "impact": rec.impact,
            }
            for rec in result.recommendations
        ],
        processing_time_ms=elapsed_ms,
    )
