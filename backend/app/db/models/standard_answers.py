"""StandardAnswer — pre-saved answers a candidate can reuse across applications.

Common question types: salary_expectation, work_authorization, notice_period,
why_this_company, biggest_strength, biggest_weakness, career_goal, custom.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StandardAnswer(Base):
    __tablename__ = "standard_answers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Question category for auto-matching in form intelligence
    question_type: Mapped[str] = mapped_column(
        String(80), nullable=False
    )  # salary_expectation|work_authorization|notice_period|why_company|strength|weakness|career_goal|custom
    # Short label for display ("My standard salary answer")
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # The answer text (max ~2000 chars to stay within form field limits)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional: only use this answer for roles at specific companies or seniority levels
    applies_to_seniority: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    candidate: Mapped["Candidate"] = relationship("Candidate")  # type: ignore[name-defined]
