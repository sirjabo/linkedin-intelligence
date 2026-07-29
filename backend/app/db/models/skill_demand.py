import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SkillDemand(Base):
    __tablename__ = "skill_demand"
    __table_args__ = (
        UniqueConstraint(
            "skill_id",
            "role_category",
            "country",
            "period_start",
            name="uq_skill_demand_skill_role_country_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills_catalog.id")
    )
    role_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(10))

    job_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    prev_week_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    trend: Mapped[str | None] = mapped_column(String(20))

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
