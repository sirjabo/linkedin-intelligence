import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, ForeignKey, Integer, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    target_roles: Mapped[list | None] = mapped_column(JSON)
    preferences: Mapped[dict | None] = mapped_column(JSON)
    # Knowledge Base 2.0 fields
    work_authorization: Mapped[str | None] = mapped_column(String(100))   # citizen|permanent_resident|visa_required|open_to_sponsorship
    availability: Mapped[str | None] = mapped_column(String(50))           # immediate|two_weeks|one_month|three_months|not_looking
    career_goals: Mapped[str | None] = mapped_column(Text)
    salary_min_usd: Mapped[int | None] = mapped_column(Integer)
    languages: Mapped[list | None] = mapped_column(JSON)                   # [{"language": "English", "level": "native"}, ...]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="candidate")  # type: ignore[name-defined]
    sources: Mapped[list["CandidateSource"]] = relationship(
        "CandidateSource", back_populates="candidate", cascade="all, delete-orphan"
    )
    profile: Mapped["CandidateProfile | None"] = relationship(
        "CandidateProfile", back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    evidence_records: Mapped[list["EvidenceRecord"]] = relationship(
        "EvidenceRecord", back_populates="candidate", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(  # type: ignore[name-defined]
        "Job", back_populates="candidate", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(  # type: ignore[name-defined]
        "Application", back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateSource(Base):
    __tablename__ = "candidate_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # cv, linkedin, github, portfolio, manual
    source_url: Mapped[str | None] = mapped_column(String(2048))
    raw_content: Mapped[str | None] = mapped_column(Text)
    extracted_content: Mapped[dict | None] = mapped_column(JSON)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="sources")


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    professional_identity: Mapped[dict | None] = mapped_column(JSON)
    career_level: Mapped[str | None] = mapped_column(String(50))
    industries: Mapped[list | None] = mapped_column(JSON)
    competencies: Mapped[list | None] = mapped_column(JSON)
    skills: Mapped[list | None] = mapped_column(JSON)
    experience: Mapped[list | None] = mapped_column(JSON)
    education: Mapped[list | None] = mapped_column(JSON)
    projects: Mapped[list | None] = mapped_column(JSON)
    certifications: Mapped[list | None] = mapped_column(JSON)
    achievements: Mapped[list | None] = mapped_column(JSON)
    conflicts: Mapped[list | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rebuilt_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="profile")


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)  # experience, skill, project, education, achievement
    source_ref: Mapped[str | None] = mapped_column(String(512))
    source_text: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="evidence_records")
