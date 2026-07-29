import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    target_role: Mapped[str | None] = mapped_column(String(100))

    plan: Mapped[str] = mapped_column(String(50), default="free")
    plan_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    linkedin_url: Mapped[str | None] = mapped_column(Text)
    linkedin_data: Mapped[dict | None] = mapped_column(JSONB)

    country: Mapped[str | None] = mapped_column(String(10))
    language: Mapped[str] = mapped_column(String(10), default="es")
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
