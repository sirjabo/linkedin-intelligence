"""Pydantic schemas for Application Agent API endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class AgentStartRequest(BaseModel):
    form_url: str

    @field_validator("form_url")
    @classmethod
    def must_be_https_or_localhost(cls, v: str) -> str:
        if v.startswith(("http://127.0.0.1", "http://localhost")):
            return v  # allow localhost for tests
        if not v.startswith("https://"):
            raise ValueError("form_url must use HTTPS (or localhost for testing)")
        return v


class AgentFieldAnswerRequest(BaseModel):
    field_id: uuid.UUID
    value: str


class AgentSubmitRequest(BaseModel):
    human_confirmed: bool


class AgentFormFieldResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    label: str
    field_type: str
    semantic_type: str
    is_required: bool
    auto_fill_value: str | None
    human_required: bool
    human_answer: str | None
    options: list[str] | None


class ApplicationAnswerResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    question: str
    answer: str
    evidence_refs: list | None
    created_at: datetime


class ApplicationAnswerUpdateRequest(BaseModel):
    answer: str


class AgentSessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    session_id: uuid.UUID
    application_id: uuid.UUID
    status: str
    ats_name: str | None
    form_url: str | None
    fields_total: int
    fields_auto_filled: int
    fields_human_pending: int
    fields_confirmed: int
    avg_confidence: float | None
    confirmation_id: str | None
    final_url: str | None
    error_message: str | None
    pause_metadata: dict | None = None
    fields: list[AgentFormFieldResponse] | None = None

    @classmethod
    def from_session(
        cls,
        session: "ApplicationAgentSession",  # type: ignore[name-defined]
        fields: list | None = None,
    ) -> "AgentSessionResponse":
        return cls(
            session_id=session.id,
            application_id=session.application_id,
            status=session.status,
            ats_name=session.ats_name,
            form_url=session.form_url,
            fields_total=session.fields_total,
            fields_auto_filled=session.fields_auto_filled,
            fields_human_pending=session.fields_human_pending,
            fields_confirmed=session.fields_confirmed,
            avg_confidence=session.avg_confidence,
            confirmation_id=session.confirmation_id,
            final_url=session.final_url,
            error_message=session.error_message,
            pause_metadata=session.pause_metadata,
            fields=[AgentFormFieldResponse.model_validate(f) for f in fields] if fields else None,
        )
