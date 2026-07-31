import os
import uuid
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

router = APIRouter(prefix="/cv", tags=["cv"])

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=CVSessionResponse)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save file temporarily
    tmp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}.pdf")
    try:
        async with aiofiles.open(tmp_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # Extract text
        raw_text = await extract_pdf_text(tmp_path)
        if not raw_text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text from PDF")

        # Parse into structured CV data via AI
        cv_dict = await parse_cv_text(raw_text)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Store in DB
    session = CVSession(
        original_filename=file.filename,
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
):
    raw_text = payload.get("text", "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="text field is required")

    cv_dict = await parse_cv_text(raw_text)

    session = CVSession(
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
):
    result = await db.execute(select(CVSession).where(CVSession.id == session_id))
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
):
    result = await db.execute(select(CVSession).where(CVSession.id == session_id))
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
