import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # draft | applied | phone_screen | interview | offer | rejected | withdrawn
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    strategy: Mapped[dict | None] = mapped_column(JSON)  # ApplicationStrategy as JSON
    notes: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="applications")  # type: ignore[name-defined]
    job: Mapped["Job"] = relationship("Job")  # type: ignore[name-defined]
    cv_versions: Mapped[list["CVVersion"]] = relationship(
        "CVVersion", back_populates="application", cascade="all, delete-orphan",
        order_by="CVVersion.created_at"
    )
    cover_letters: Mapped[list["CoverLetter"]] = relationship(
        "CoverLetter", back_populates="application", cascade="all, delete-orphan",
        order_by="CoverLetter.created_at"
    )
    answers: Mapped[list["ApplicationAnswer"]] = relationship(
        "ApplicationAnswer", back_populates="application", cascade="all, delete-orphan"
    )
    events: Mapped[list["ApplicationEvent"]] = relationship(
        "ApplicationEvent", back_populates="application", cascade="all, delete-orphan",
        order_by="ApplicationEvent.occurred_at"
    )
    interview_prep: Mapped["InterviewPrep | None"] = relationship(  # type: ignore[name-defined]
        "InterviewPrep", back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    submission: Mapped["ApplicationSubmission | None"] = relationship(
        "ApplicationSubmission", back_populates="application", uselist=False, cascade="all, delete-orphan"
    )


class CVVersion(Base):
    __tablename__ = "cv_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_adapted: Mapped[str | None] = mapped_column(Text)
    headline_adapted: Mapped[str | None] = mapped_column(String(255))
    skills_ordered: Mapped[list | None] = mapped_column(JSON)
    changes: Mapped[list | None] = mapped_column(JSON)  # list of CVChange dicts
    evidence_refs: Mapped[list | None] = mapped_column(JSON)
    ats_keywords: Mapped[list | None] = mapped_column(JSON)
    validation_result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship("Application", back_populates="cv_versions")


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list | None] = mapped_column(JSON)
    validation_result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship("Application", back_populates="cover_letters")


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship("Application", back_populates="answers")


class ApplicationSubmission(Base):
    __tablename__ = "application_submissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirmation_number: Mapped[str | None] = mapped_column(String(255))
    submission_url: Mapped[str | None] = mapped_column(String(2048))
    # manual | agent | api
    submitted_via: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship("Application", back_populates="submission")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # applied | response | phone_screen | interview | offer | rejected | withdrawn | note
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[Application] = relationship("Application", back_populates="events")
