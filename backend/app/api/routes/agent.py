"""Application Agent API: browser-based form discovery, auto-fill, and submission.

POST /applications/{id}/agent/start       — discover form, resolve fields
GET  /applications/{id}/agent/status      — get current session + fields
POST /applications/{id}/agent/answer/{field_id} — provide human answer
POST /applications/{id}/agent/preview     — get all fields for review before submit
POST /applications/{id}/agent/submit      — submit (requires human_confirmed=True)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.db.models.agent_session import ApplicationAgentSession
from app.db.models.application import Application, ApplicationAnswer
from app.db.models.candidate import Candidate
from app.db.models.form import ApplicationForm, ApplicationFormField
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.agent import (
    AgentFieldAnswerRequest,
    AgentSessionResponse,
    AgentStartRequest,
    AgentSubmitRequest,
    ApplicationAnswerResponse,
    ApplicationAnswerUpdateRequest,
)
from app.services.application_agent_orchestrator import AgentError, ApplicationAgentOrchestrator

router = APIRouter(prefix="/applications", tags=["agent"])
logger = get_logger(__name__)
_orchestrator = ApplicationAgentOrchestrator()


async def _get_application_for_user(
    application_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Application:
    result = await db.execute(
        select(Application)
        .join(Candidate, Application.candidate_id == Candidate.id)
        .where(Application.id == application_id, Candidate.user_id == user.id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def _get_latest_session(application_id: uuid.UUID, db: AsyncSession) -> ApplicationAgentSession | None:
    result = await db.execute(
        select(ApplicationAgentSession)
        .where(ApplicationAgentSession.application_id == application_id)
        .order_by(ApplicationAgentSession.created_at.desc())
    )
    return result.scalars().first()


async def _get_session_fields(application_id: uuid.UUID, db: AsyncSession) -> list[ApplicationFormField]:
    result = await db.execute(
        select(ApplicationForm)
        .options(selectinload(ApplicationForm.fields))
        .where(ApplicationForm.application_id == application_id)
    )
    form = result.scalar_one_or_none()
    return form.fields if form else []


@router.post("/{application_id}/agent/start", response_model=AgentSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def start_agent(
    request: Request,
    application_id: uuid.UUID,
    payload: AgentStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentSessionResponse:
    """Discover the application form and resolve all fields from candidate data.

    Launches a headless browser, navigates to the form URL, extracts all fields,
    and maps candidate data to auto-fillable answers. Returns session + field list.
    """
    await _get_application_for_user(application_id, current_user, db)

    try:
        session = await _orchestrator.start(
            application_id=application_id,
            form_url=payload.form_url,
            db=db,
        )
    except AgentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    fields = await _get_session_fields(application_id, db)
    return AgentSessionResponse.from_session(session, fields)


@router.get("/{application_id}/agent/status", response_model=AgentSessionResponse)
async def get_agent_status(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentSessionResponse:
    """Get the current agent session status and field list."""
    await _get_application_for_user(application_id, current_user, db)

    session = await _get_latest_session(application_id, db)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No agent session found for this application")

    fields = await _get_session_fields(application_id, db)
    return AgentSessionResponse.from_session(session, fields)


@router.post("/{application_id}/agent/answer/{field_id}", response_model=AgentSessionResponse)
async def answer_field(
    application_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: AgentFieldAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentSessionResponse:
    """Provide a human answer for a field that requires manual input."""
    await _get_application_for_user(application_id, current_user, db)

    # Verify field belongs to this application's form
    form_result = await db.execute(
        select(ApplicationForm)
        .options(selectinload(ApplicationForm.fields))
        .where(ApplicationForm.application_id == application_id)
    )
    form = form_result.scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No form found for this application")

    db_field = next((f for f in form.fields if f.id == field_id), None)
    if not db_field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form field not found")

    db_field.human_answer = payload.value

    # Recalculate pending
    pending = sum(
        1 for f in form.fields
        if f.human_required and f.auto_fill_value is None and f.human_answer is None
    )
    form.human_fields_pending = pending
    form.status = "ready" if pending == 0 else "mapped"
    await db.commit()

    # Update session
    session = await _get_latest_session(application_id, db)
    if session:
        session.fields_human_pending = pending
        if pending == 0 and session.status == "awaiting_human":
            session.status = "ready_to_fill"
        await db.commit()

    return AgentSessionResponse.from_session(
        session or ApplicationAgentSession(
            id=uuid.uuid4(), application_id=application_id,
            status="awaiting_human", fields_total=0, fields_auto_filled=0,
            fields_human_pending=pending, fields_confirmed=0,
        ),
        form.fields,
    )


@router.post("/{application_id}/agent/preview", response_model=AgentSessionResponse)
async def preview_agent(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentSessionResponse:
    """Return current field values for human review before submission."""
    await _get_application_for_user(application_id, current_user, db)

    session = await _get_latest_session(application_id, db)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No agent session found")

    fields = await _get_session_fields(application_id, db)
    return AgentSessionResponse.from_session(session, fields)


@router.post("/{application_id}/agent/submit", response_model=AgentSessionResponse)
async def submit_agent(
    application_id: uuid.UUID,
    payload: AgentSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentSessionResponse:
    """Fill the form in a headless browser and submit.

    Requires human_confirmed=True. Will raise 400 without it.
    """
    await _get_application_for_user(application_id, current_user, db)

    if not payload.human_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="human_confirmed must be true — the user must explicitly confirm before submission",
        )

    session = await _get_latest_session(application_id, db)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No agent session found")

    if session.status != "ready_to_fill":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session status is '{session.status}' — must be 'ready_to_fill' before submitting",
        )

    try:
        session = await _orchestrator.submit(
            session_id=session.id,
            human_confirmed=payload.human_confirmed,
            db=db,
        )
    except AgentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    fields = await _get_session_fields(application_id, db)
    return AgentSessionResponse.from_session(session, fields)


@router.get("/{application_id}/agent/answers", response_model=list[ApplicationAnswerResponse])
async def list_agent_answers(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationAnswerResponse]:
    """Return all stored answers (question/answer pairs) for this application."""
    await _get_application_for_user(application_id, current_user, db)

    result = await db.execute(
        select(ApplicationAnswer)
        .where(ApplicationAnswer.application_id == application_id)
        .order_by(ApplicationAnswer.created_at)
    )
    rows = result.scalars().all()
    return [ApplicationAnswerResponse.model_validate(r) for r in rows]


@router.patch(
    "/{application_id}/agent/answers/{answer_id}",
    response_model=ApplicationAnswerResponse,
)
async def update_agent_answer(
    application_id: uuid.UUID,
    answer_id: uuid.UUID,
    payload: ApplicationAnswerUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationAnswerResponse:
    """Edit the text of a stored answer."""
    await _get_application_for_user(application_id, current_user, db)

    result = await db.execute(
        select(ApplicationAnswer).where(
            ApplicationAnswer.id == answer_id,
            ApplicationAnswer.application_id == application_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")

    row.answer = payload.answer
    await db.commit()
    await db.refresh(row)
    return ApplicationAnswerResponse.model_validate(row)
