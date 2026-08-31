import os
import uuid
from typing import List
import aiofiles
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import CVSession
from app.schemas.cv_chat import CVSessionResponse, CVData
from app.services.pdf_extractor import extract_pdf_text
from app.services.pdf_generator import generate_cv_pdf
from app.services.ai_service import parse_cv_text
from app.core.config import settings
from app.core.auth import get_current_user_id

router = APIRouter(prefix="/cv", tags=["cv"])

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=CVSessionResponse)
async def upload_cv(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required")

    all_texts: list[str] = []
    first_filename = files[0].filename or "cv.pdf"
    tmp_paths: list[str] = []

    try:
        for file in files:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail=f"Only PDF files are accepted: {file.filename}")
            tmp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}.pdf")
            tmp_paths.append(tmp_path)
            async with aiofiles.open(tmp_path, "wb") as f:
                content = await file.read()
                await f.write(content)
            text = await extract_pdf_text(tmp_path)
            if text.strip():
                all_texts.append(text)
    finally:
        for p in tmp_paths:
            if os.path.exists(p):
                os.remove(p)

    if not all_texts:
        raise HTTPException(status_code=422, detail="Could not extract text from any PDF")

    raw_text = "\n\n---\n\n".join(all_texts)
    cv_dict = await parse_cv_text(raw_text)

    session = CVSession(
        user_id=user_id,
        original_filename=first_filename,
        original_text=raw_text,
        cv_data=cv_dict,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return CVSessionResponse(
        id=session.id,
        cv_data=CVData.model_validate(session.cv_data),
        created_at=session.created_at,
    )


@router.post("/from-text", response_model=CVSessionResponse)
async def create_cv_from_text(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    raw_text = payload.get("text", "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="text field is required")

    cv_dict = await parse_cv_text(raw_text)

    session = CVSession(
        user_id=user_id,
        original_text=raw_text,
        cv_data=cv_dict,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return CVSessionResponse(
        id=session.id,
        cv_data=CVData.model_validate(session.cv_data),
        created_at=session.created_at,
    )


@router.get("/{session_id}", response_model=CVSessionResponse)
async def get_cv_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(CVSession).where(CVSession.id == session_id, CVSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return CVSessionResponse(
        id=session.id,
        cv_data=CVData.model_validate(session.cv_data) if session.cv_data else None,
        created_at=session.created_at,
    )


@router.get("/{session_id}/pdf")
async def download_cv_pdf(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(CVSession).where(CVSession.id == session_id, CVSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session or not session.cv_data:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_bytes = await generate_cv_pdf(session.cv_data)
    name = (session.cv_data.get("name", "cv") or "cv").replace(" ", "_").lower()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}_optimizado.pdf"'},
    )
