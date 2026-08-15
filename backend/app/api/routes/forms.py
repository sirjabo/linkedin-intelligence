"""Form Intelligence routes: register, view, and answer application forms."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.models.user import User
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.application import Application
from app.db.models.form import ApplicationForm, ApplicationFormField
from app.api.deps import get_current_user
from app.schemas.form import FormCreate, FormResponse, FormFieldAnswer
from app.services.form_intelligence import map_candidate_to_form, FieldSpec
from app.core.logging import get_logger

router = APIRouter(prefix="/applications", tags=["forms"])
logger = get_logger(__name__)


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


@router.post("/{application_id}/form", response_model=FormResponse, status_code=status.HTTP_201_CREATED)
async def register_form(
    application_id: uuid.UUID,
    payload: FormCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationForm:
    """Register an application form and auto-map candidate data to its fields.

    Pass the form's fields (labels + types) and the system will:
    - Classify each field semantically
    - Auto-fill what it can from the candidate profile
    - Flag fields that need human input
    """
    application = await _get_application_for_user(application_id, current_user, db)

    # Fetch candidate + profile for auto-fill
    cand_result = await db.execute(
        select(Candidate).where(Candidate.id == application.candidate_id)
    )
    candidate = cand_result.scalar_one()

    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = profile_result.scalar_one_or_none()

    # Map form fields
    field_specs = [FieldSpec(
        label=f.label,
        field_type=f.field_type,
        is_required=f.is_required,
        options=f.options,
    ) for f in payload.fields]

    mapped = map_candidate_to_form(
        fields=field_specs,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        candidate_location=candidate.location,
        candidate_salary_min=candidate.salary_min_usd,
        candidate_work_authorization=candidate.work_authorization,
        candidate_availability=candidate.availability,
    )

    human_pending = sum(1 for f in mapped if f.human_required and f.auto_fill_value is None)

    form = ApplicationForm(
        application_id=application.id,
        form_url=payload.form_url,
        status="mapped",
        human_fields_pending=human_pending,
    )
    db.add(form)
    await db.flush()

    for i, mf in enumerate(mapped):
        db.add(ApplicationFormField(
            form_id=form.id,
            label=mf.label,
            field_type=mf.field_type,
            semantic_type=mf.semantic_type,
            is_required=mf.is_required,
            auto_fill_value=mf.auto_fill_value,
            human_required=mf.human_required,
            options=mf.options,
            sort_order=i,
        ))

    await db.commit()

    result = await db.execute(
        select(ApplicationForm)
        .options(selectinload(ApplicationForm.fields))
        .where(ApplicationForm.id == form.id)
    )
    form = result.scalar_one()

    logger.info(
        "form.registered",
        application_id=str(application_id),
        fields=len(mapped),
        human_pending=human_pending,
    )
    return form


@router.get("/{application_id}/form", response_model=FormResponse)
async def get_form(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationForm:
    """Retrieve the registered form for an application."""
    await _get_application_for_user(application_id, current_user, db)

    result = await db.execute(
        select(ApplicationForm)
        .options(selectinload(ApplicationForm.fields))
        .where(ApplicationForm.application_id == application_id)
    )
    form = result.scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No form registered for this application")
    return form


@router.patch("/{application_id}/form/answer", response_model=FormResponse)
async def answer_form_field(
    application_id: uuid.UUID,
    payload: FormFieldAnswer,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationForm:
    """Provide a human answer for a form field that requires manual input."""
    await _get_application_for_user(application_id, current_user, db)

    # Fetch the form
    form_result = await db.execute(
        select(ApplicationForm)
        .options(selectinload(ApplicationForm.fields))
        .where(ApplicationForm.application_id == application_id)
    )
    form = form_result.scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No form registered")

    # Find the field
    field = next((f for f in form.fields if f.id == payload.field_id), None)
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form field not found")

    field.human_answer = payload.human_answer

    # Recalculate pending count
    pending = sum(
        1 for f in form.fields
        if f.human_required and f.auto_fill_value is None and f.human_answer is None
    )
    form.human_fields_pending = pending
    form.status = "ready" if pending == 0 else "mapped"

    await db.commit()

    result = await db.execute(
        select(ApplicationForm)
        .options(selectinload(ApplicationForm.fields))
        .where(ApplicationForm.id == form.id)
    )
    return result.scalar_one()
