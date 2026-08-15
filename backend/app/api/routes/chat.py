import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import CVSession, ChatMessage
from app.schemas.cv_chat import ChatRequest, ChatMessageResponse
from app.services.ai_service import stream_cv_chat
from app.core.auth import get_current_user_id

router = APIRouter(prefix="/cv", tags=["chat"])


def _apply_cv_update(cv_data: dict, update: dict) -> dict:
    section = update.get("section")
    if not section:
        return cv_data

    cv = dict(cv_data)

    if section == "summary":
        cv["summary"] = update.get("content", "")
    elif section == "name":
        cv["name"] = update.get("content", "")
    elif section == "target_role":
        cv["target_role"] = update.get("content", "")
    elif section == "skills":
        cv["skills"] = update.get("content", {})
    elif section == "experience":
        index = update.get("index")
        field = update.get("field")
        content = update.get("content")
        if index is not None and field and cv.get("experience") and index < len(cv["experience"]):
            exp = dict(cv["experience"][index])
            exp[field] = content
            cv["experience"] = [
                e if i != index else exp for i, e in enumerate(cv["experience"])
            ]
        elif content and isinstance(content, list):
            cv["experience"] = content
    elif section in ("education", "projects", "certifications"):
        content = update.get("content")
        if content is not None:
            cv[section] = content

    return cv


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
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

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return messages


@router.post("/{session_id}/chat")
async def chat(
    session_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(CVSession).where(CVSession.id == session_id, CVSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session or not session.cv_data:
        raise HTTPException(status_code=404, detail="Session not found")

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
    ]

    user_msg = ChatMessage(session_id=session.id, role="user", content=request.message)
    db.add(user_msg)
    await db.commit()

    cv_data = dict(session.cv_data)
    cv_updates_collected = []
    assistant_text_parts = []

    async def event_generator():
        try:
            async for event in stream_cv_chat(cv_data, history, request.message):
                yield event
                if event.startswith("data: "):
                    try:
                        payload = json.loads(event[6:])
                        if payload.get("type") == "text":
                            assistant_text_parts.append(payload.get("content", ""))
                        elif payload.get("type") == "cv_update":
                            cv_updates_collected.append(payload)
                    except json.JSONDecodeError:
                        pass
        finally:
            try:
                full_text = "".join(assistant_text_parts).strip()
                if full_text:
                    asst_msg = ChatMessage(session_id=session.id, role="assistant", content=full_text)
                    db.add(asst_msg)

                updated_cv = cv_data
                for update in cv_updates_collected:
                    update_payload = {k: v for k, v in update.items() if k != "type"}
                    updated_cv = _apply_cv_update(updated_cv, update_payload)

                session.cv_data = updated_cv
                await db.commit()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
