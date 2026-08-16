"""Standard Application Answers — candidate-owned reusable answer library."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.db.models.candidate import Candidate
from app.db.models.standard_answers import StandardAnswer
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/answers", tags=["answers"])
logger = get_logger(__name__)

_VALID_TYPES = {
    "salary_expectation",
    "work_authorization",
    "notice_period",
    "why_company",
    "strength",
    "weakness",
    "career_goal",
    "custom",
}


class AnswerCreate(BaseModel):
    question_type: str
    label: str
    answer_text: str
    applies_to_seniority: str | None = None


class AnswerUpdate(BaseModel):
    label: str | None = None
    answer_text: str | None = None
    applies_to_seniority: str | None = None


class AnswerResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    candidate_id: uuid.UUID
    question_type: str
    label: str
    answer_text: str
    applies_to_seniority: str | None


async def _get_candidate(user: User, db: AsyncSession) -> Candidate:
    result = await db.execute(select(Candidate).where(Candidate.user_id == user.id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c


@router.get("", response_model=list[AnswerResponse])
async def list_answers(
    question_type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StandardAnswer]:
    """List all saved answers, optionally filtered by question_type."""
    candidate = await _get_candidate(user, db)
    q = select(StandardAnswer).where(StandardAnswer.candidate_id == candidate.id)
    if question_type:
        q = q.where(StandardAnswer.question_type == question_type)
    result = await db.execute(q.order_by(StandardAnswer.updated_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=AnswerResponse, status_code=status.HTTP_201_CREATED)
async def create_answer(
    payload: AnswerCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StandardAnswer:
    """Save a new standard answer."""
    if payload.question_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"question_type must be one of {sorted(_VALID_TYPES)}")
    if not payload.answer_text.strip():
        raise HTTPException(status_code=400, detail="answer_text cannot be empty")

    candidate = await _get_candidate(user, db)
    answer = StandardAnswer(
        candidate_id=candidate.id,
        question_type=payload.question_type,
        label=payload.label or payload.question_type,
        answer_text=payload.answer_text.strip(),
        applies_to_seniority=payload.applies_to_seniority,
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)
    logger.info("standard_answer_created", candidate_id=str(candidate.id), type=payload.question_type)
    return answer


@router.put("/{answer_id}", response_model=AnswerResponse)
async def update_answer(
    answer_id: uuid.UUID,
    payload: AnswerUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StandardAnswer:
    candidate = await _get_candidate(user, db)
    result = await db.execute(
        select(StandardAnswer).where(
            StandardAnswer.id == answer_id,
            StandardAnswer.candidate_id == candidate.id,
        )
    )
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    if payload.label is not None:
        answer.label = payload.label
    if payload.answer_text is not None:
        answer.answer_text = payload.answer_text.strip()
    if payload.applies_to_seniority is not None:
        answer.applies_to_seniority = payload.applies_to_seniority

    await db.commit()
    return answer


@router.delete("/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_answer(
    answer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    candidate = await _get_candidate(user, db)
    result = await db.execute(
        select(StandardAnswer).where(
            StandardAnswer.id == answer_id,
            StandardAnswer.candidate_id == candidate.id,
        )
    )
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    await db.delete(answer)
    await db.commit()
