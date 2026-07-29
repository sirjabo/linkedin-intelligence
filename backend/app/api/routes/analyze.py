"""POST /analyze/cv — CV ATS analysis endpoint."""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.deps import DbSession
from app.core.logging import get_logger
from app.db.models.cv_analysis import CVAnalysis
from app.engine.ats import ATSEngine
from app.engine.pdf import PDFParseError, extract_text_from_pdf
from app.schemas.analyze import CVAnalysisResponse

router = APIRouter(prefix="/analyze", tags=["analyze"])
logger = get_logger(__name__)

SUPPORTED_ROLES = frozenset({"ai_engineer", "data_engineer", "analytics_engineer"})


@router.post("/cv", response_model=CVAnalysisResponse)
async def analyze_cv(
    db: DbSession,
    target_role: Annotated[str, Form(...)],
    cv_text: Annotated[str | None, Form()] = None,
    target_job_id: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(None),
) -> CVAnalysisResponse:
    """Analyze a CV (PDF or plain text) and return ATS Score + recommendations."""
    started = time.perf_counter()

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

    text = await _resolve_cv_text(cv_text, file)
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
            job_uuid = uuid.UUID(target_job_id)
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


async def _resolve_cv_text(cv_text: str | None, file: UploadFile | None) -> str:
    if file is not None and file.filename:
        content_type = (file.content_type or "").lower()
        raw = await file.read()
        if "pdf" in content_type or (file.filename or "").lower().endswith(".pdf"):
            try:
                return extract_text_from_pdf(raw)
            except PDFParseError as exc:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "PDF_PARSE_ERROR", "message": str(exc)},
                ) from exc
        # Treat as plain text upload
        return raw.decode("utf-8", errors="replace")

    if cv_text and cv_text.strip():
        return cv_text.strip()

    raise HTTPException(
        status_code=400,
        detail={
            "code": "MISSING_CV",
            "message": "Debés enviar 'cv_text' o un archivo PDF en 'file'",
        },
    )
