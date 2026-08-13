import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class InterviewPrep(Base):
    __tablename__ = "interview_preps"
    __table_args__ = (UniqueConstraint("application_id", name="uq_interview_prep_application"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    technical_questions: Mapped[list | None] = mapped_column(JSON)  # list of {question, rationale}
    behavioral_questions: Mapped[list | None] = mapped_column(JSON)  # list of {question, competency}
    star_stories: Mapped[list | None] = mapped_column(JSON)         # list of {situation, task, action, result, competency}
    questions_to_ask: Mapped[list | None] = mapped_column(JSON)     # list of str
    company_research: Mapped[dict | None] = mapped_column(JSON)     # {culture, mission, values}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    application: Mapped["Application"] = relationship(  # type: ignore[name-defined]
        "Application", back_populates="interview_prep"
    )
