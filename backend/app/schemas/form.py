from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FormFieldInput(BaseModel):
    label: str
    field_type: str = "text"
    is_required: bool = True
    options: list[str] | None = None


class FormCreate(BaseModel):
    form_url: str | None = None
    fields: list[FormFieldInput]


class FormFieldAnswer(BaseModel):
    field_id: UUID
    human_answer: str


class FormFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    form_id: UUID
    label: str
    field_type: str
    semantic_type: str
    is_required: bool
    auto_fill_value: str | None
    human_required: bool
    human_answer: str | None
    options: list | None
    sort_order: int


class FormResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    form_url: str | None
    discovery_method: str
    status: str
    human_fields_pending: int
    fields: list[FormFieldResponse] = []
    created_at: datetime
    updated_at: datetime
