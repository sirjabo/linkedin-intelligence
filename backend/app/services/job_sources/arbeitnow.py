"""Arbeitnow.com free public job board API (no auth required).

API docs: https://www.arbeitnow.com/api/job-board-api
Returns tech jobs worldwide with visa sponsorship option.
"""
import httpx

from app.services.job_sources.base import JobRaw

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
DEFAULT_TIMEOUT = 10.0


def _remote_type(item: dict) -> str:
    if item.get("remote"):
        return "remote"
    if "hybrid" in (item.get("location") or "").lower():
        return "hybrid"
    return "onsite"


def _extract_tags(item: dict) -> list[str]:
    tags: list[str] = []
    for t in item.get("tags", []):
        if isinstance(t, str):
            tags.append(t.strip().lower())
    return tags


class ArbeitnowSource:
    """Fetches tech jobs from Arbeitnow's free public API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch(self, query: str, limit: int, category: str | None) -> list[JobRaw]:
        async with (
            self._client if self._client
            else httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        ) as client:
            resp = await client.get(ARBEITNOW_URL, params={"page": 1})
            resp.raise_for_status()
            data = resp.json()

        query_tokens = {q.lower() for q in (query or "").split() if q}
        jobs: list[JobRaw] = []

        for item in data.get("data", []):
            title = item.get("title", "")
            description = item.get("description", "")
            tags = _extract_tags(item)

            # Filter by query if provided
            if query_tokens:
                searchable = (title + " " + " ".join(tags) + " " + description[:500]).lower()
                if not any(tok in searchable for tok in query_tokens):
                    continue

            jobs.append(JobRaw(
                external_id=str(item.get("slug", item.get("id", ""))),
                title=title,
                company=item.get("company_name", ""),
                location=item.get("location", "Worldwide"),
                remote_type=_remote_type(item),
                url=item.get("url", ""),
                description=description,
                tech_tags=tags,
                salary_range=None,
                published_at=item.get("created_at"),
            ))

            if len(jobs) >= limit:
                break

        return jobs
