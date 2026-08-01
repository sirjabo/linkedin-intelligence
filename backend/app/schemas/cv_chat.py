from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Any


class Contact(BaseModel):
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class Experience(BaseModel):
    company: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = "Present"
    location: str | None = None
    bullets: list[str] = []

    @field_validator("company", "role", "start_date", "end_date", mode="before")
    @classmethod
    def coerce_none_to_str(cls, v: Any) -> str:
        return "" if v is None else str(v)

    @field_validator("bullets", mode="before")
    @classmethod
    def coerce_bullets(cls, v: Any) -> list[str]:
        if not v:
            return []
        return [str(b) for b in v if b is not None]


class Skills(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    cloud: list[str] = []
    databases: list[str] = []
    tools: list[str] = []
    other: list[str] = []

    @field_validator("languages", "frameworks", "cloud", "databases", "tools", "other", mode="before")
    @classmethod
    def coerce_list(cls, v: Any) -> list[str]:
        if not v:
            return []
        return [str(i) for i in v if i is not None]


class Education(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str | None = None
    year: str = ""
    gpa: str | None = None

    @field_validator("institution", "degree", "year", mode="before")
    @classmethod
    def coerce_none_to_str(cls, v: Any) -> str:
        return "" if v is None else str(v)


class Project(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = []
    url: str | None = None
    highlights: list[str] = []

    @field_validator("name", "description", mode="before")
    @classmethod
    def coerce_none_to_str(cls, v: Any) -> str:
        return "" if v is None else str(v)


class Certification(BaseModel):
    name: str = ""
    issuer: str = ""
    year: str = ""
    url: str | None = None

    @field_validator("name", "issuer", "year", mode="before")
    @classmethod
    def coerce_none_to_str(cls, v: Any) -> str:
        return "" if v is None else str(v)


class CVData(BaseModel):
    name: str = ""
    contact: Contact = Contact()
    target_role: str | None = None
    summary: str | None = None
    experience: list[Experience] = []
    skills: Skills = Skills()
    education: list[Education] = []
    projects: list[Project] = []
    certifications: list[Certification] = []

    @field_validator("name", mode="before")
    @classmethod
    def coerce_name(cls, v: Any) -> str:
        return "" if v is None else str(v)


class CVSessionResponse(BaseModel):
    id: UUID
    cv_data: CVData | None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
