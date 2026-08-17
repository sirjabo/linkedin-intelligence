import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CVAnalysis(Base):
    __tablename__ = "cv_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    cv_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_role: Mapped[str] = mapped_column(String(100), nullable=False)
    target_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id")
    )

    ats_score: Mapped[int | None] = mapped_column(Integer)
    keyword_match_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    keywords_found: Mapped[dict | list | None] = mapped_column(JSONB)
    keywords_missing: Mapped[dict | list | None] = mapped_column(JSONB)
    section_scores: Mapped[dict | None] = mapped_column(JSONB)
    suggestions: Mapped[dict | list | None] = mapped_column(JSONB)

    cv_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
