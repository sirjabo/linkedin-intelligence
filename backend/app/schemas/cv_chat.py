from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class Contact(BaseModel):
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class Experience(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: str = "Present"
    location: str | None = None
    bullets: list[str] = []


class Skills(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    cloud: list[str] = []
    databases: list[str] = []
    tools: list[str] = []
    other: list[str] = []


class Education(BaseModel):
    institution: str
    degree: str
    field: str | None = None
    year: str
    gpa: str | None = None


class Project(BaseModel):
    name: str
    description: str
    technologies: list[str] = []
    url: str | None = None
    highlights: list[str] = []


class Certification(BaseModel):
    name: str
    issuer: str
    year: str
    url: str | None = None


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
