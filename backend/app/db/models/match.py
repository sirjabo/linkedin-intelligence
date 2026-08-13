import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, ForeignKey, JSON, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class MatchAnalysis(Base):
    __tablename__ = "match_analyses"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_match_candidate_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Hybrid score (deterministic * 0.6 + llm * 0.4)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    deterministic_score: Mapped[float] = mapped_column(Float, nullable=False)
    llm_score: Mapped[float | None] = mapped_column(Float)
    match_tier: Mapped[str] = mapped_column(String(50), nullable=False)  # excellent|strong|moderate|weak|poor
    # Deterministic components
    skill_overlap_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_score: Mapped[float] = mapped_column(Float, nullable=False)
    location_score: Mapped[float] = mapped_column(Float, nullable=False)
    education_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Skill detail
    matched_skills: Mapped[list | None] = mapped_column(JSON)
    missing_skills: Mapped[list | None] = mapped_column(JSON)
    # LLM output
    llm_reasoning: Mapped[str | None] = mapped_column(Text)
    llm_strengths: Mapped[list | None] = mapped_column(JSON)
    llm_gaps: Mapped[list | None] = mapped_column(JSON)
    # Learning loop: actual outcome recorded by the user after applying
    # Values: "offer" | "interview" | "phone_screen" | "rejected" | "no_response" | None
    outcome: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate: Mapped["Candidate"] = relationship("Candidate")  # type: ignore[name-defined]
    job: Mapped["Job"] = relationship("Job", back_populates="match_analyses")  # type: ignore[name-defined]
