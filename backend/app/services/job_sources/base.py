"""Base types for external job source integrations."""
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class JobRaw:
    """A job posting fetched from an external source."""
    external_id: str
    title: str
    company: str
    location: str
    remote_type: str  # remote | hybrid | onsite | unknown
    url: str
    description: str
    tech_tags: list[str] = field(default_factory=list)
    salary_range: str | None = None
    published_at: str | None = None


@runtime_checkable
class JobSource(Protocol):
    """Protocol that all external job sources must satisfy."""

    async def fetch(self, query: str, limit: int, category: str | None) -> list[JobRaw]:
        """Fetch jobs matching the given query."""
        ...
