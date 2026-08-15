"""Market intelligence persistence — daily skill frequency snapshots."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SkillSnapshot(Base):
    __tablename__ = "skill_snapshots"
    __table_args__ = (
        UniqueConstraint("role", "skill_slug", "snapshot_date", name="uq_skill_snapshot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    skill_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    frequency_pct: Mapped[float] = mapped_column(Float, nullable=False)
    job_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
