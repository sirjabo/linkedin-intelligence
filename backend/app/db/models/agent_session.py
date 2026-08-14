"""ApplicationAgentSession — tracks the full lifecycle of browser-based form filling.

State machine:
  initializing → discovering → mapping → awaiting_human → ready_to_fill
    → filling → awaiting_confirm → submitting → submitted
    → failed (terminal error from any state)
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Float, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ApplicationAgentSession(Base):
    __tablename__ = "application_agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── State machine ──────────────────────────────────────────────────────────
    # initializing | discovering | mapping | awaiting_human | ready_to_fill
    # | filling | awaiting_confirm | submitting | submitted | failed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="initializing")

    # ── ATS metadata ──────────────────────────────────────────────────────────
    ats_name: Mapped[str | None] = mapped_column(String(100))
    form_url: Mapped[str | None] = mapped_column(String(2048))

    # ── Field counters ────────────────────────────────────────────────────────
    fields_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fields_auto_filled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fields_human_pending: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fields_confirmed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fields_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Confidence metrics ────────────────────────────────────────────────────
    avg_confidence: Mapped[float | None] = mapped_column(Float)
    min_confidence: Mapped[float | None] = mapped_column(Float)

    # ── Submission outcome ────────────────────────────────────────────────────
    confirmation_id: Mapped[str | None] = mapped_column(String(255))
    final_url: Mapped[str | None] = mapped_column(String(2048))

    # ── Human review flags ─────────────────────────────────────────────────────
    human_review_requested: Mapped[bool] = mapped_column(
        String(1), nullable=False, default="0"
    )
    human_confirmed: Mapped[bool] = mapped_column(
        String(1), nullable=False, default="0"
    )

    # ── Artifacts ─────────────────────────────────────────────────────────────
    screenshot_before_path: Mapped[str | None] = mapped_column(String(1024))
    screenshot_filled_path: Mapped[str | None] = mapped_column(String(1024))
    screenshot_confirm_path: Mapped[str | None] = mapped_column(String(1024))

    # ── Error tracking ────────────────────────────────────────────────────────
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Timestamps ────────────────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    application: Mapped["Application"] = relationship("Application")  # type: ignore[name-defined]

    def transition_to(self, new_status: str) -> None:
        """Update status and set the corresponding timestamp."""
        self.status = new_status
        now = datetime.utcnow()
        if new_status == "discovering":
            pass
        elif new_status == "submitted":
            self.submitted_at = now
            self.completed_at = now
        elif new_status == "failed":
            self.completed_at = now
