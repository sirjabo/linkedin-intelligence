import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Provided by user or parsed by agent
    title: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    job_url: Mapped[str | None] = mapped_column(String(2048))
    # Parsed by agent
    location: Mapped[str | None] = mapped_column(String(255))
    remote_type: Mapped[str | None] = mapped_column(String(50))   # onsite | hybrid | remote
    seniority: Mapped[str | None] = mapped_column(String(50))     # junior | mid | senior | staff | ...
    employment_type: Mapped[str | None] = mapped_column(String(50))  # full-time | part-time | contract
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    tech_stack: Mapped[list | None] = mapped_column(JSON)
    key_responsibilities: Mapped[list | None] = mapped_column(JSON)
    company_description: Mapped[str | None] = mapped_column(Text)
    parsing_confidence: Mapped[float | None] = mapped_column(Float)
    visa_sponsorship: Mapped[bool | None] = mapped_column(Boolean)   # True = offers sponsorship
    raw_jd: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="analyzed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="jobs")  # type: ignore[name-defined]
    requirements: Mapped[list["JobRequirement"]] = relationship(
        "JobRequirement", back_populates="job", cascade="all, delete-orphan"
    )
    match_analyses: Mapped[list["MatchAnalysis"]] = relationship(  # type: ignore[name-defined]
        "MatchAnalysis", back_populates="job", cascade="all, delete-orphan"
    )


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(50), nullable=False)  # must_have | nice_to_have
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # technical | soft | experience | ...
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    seniority_signal: Mapped[str | None] = mapped_column(String(100))
    classification: Mapped[str | None] = mapped_column(String(50))  # MANDATORY | PREFERRED | INFERRED

    job: Mapped[Job] = relationship("Job", back_populates="requirements")
