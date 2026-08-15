import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ApplicationForm(Base):
    __tablename__ = "application_forms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    form_url: Mapped[str | None] = mapped_column(String(2048))
    # manual | playwright (future)
    discovery_method: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    # pending | mapped | ready | submitted
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    human_fields_pending: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fields: Mapped[list["ApplicationFormField"]] = relationship(
        "ApplicationFormField", back_populates="form", cascade="all, delete-orphan", order_by="ApplicationFormField.sort_order"
    )


class ApplicationFormField(Base):
    __tablename__ = "application_form_fields"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("application_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # HTML input type: text | textarea | select | file | checkbox | radio
    field_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    # Semantic classification
    semantic_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Auto-fill: value mapped from candidate data (null = needs human)
    auto_fill_value: Mapped[str | None] = mapped_column(Text)
    # True when this field must be answered by a human (custom essay, captcha, etc.)
    human_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Human-provided answer (set by the user in the UI)
    human_answer: Mapped[str | None] = mapped_column(Text)
    # Options for select/radio fields
    options: Mapped[list | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    form: Mapped[ApplicationForm] = relationship("ApplicationForm", back_populates="fields")
