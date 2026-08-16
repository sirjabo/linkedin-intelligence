"""Remotive.com public API job source."""
import httpx

from app.services.job_sources.base import JobRaw

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
DEFAULT_TIMEOUT = 10.0


def _map_remote_type(candidate_type: str) -> str:
    low = candidate_type.lower()
    if "remote" in low:
        return "remote"
    if "hybrid" in low:
        return "hybrid"
    return "unknown"


def _parse_tags(item: dict) -> list[str]:
    tags: list[str] = []
    for t in item.get("tags", []):
        if isinstance(t, str):
            tags.append(t.strip().lower())
        elif isinstance(t, dict):
            name = t.get("name", "")
            if name:
                tags.append(name.strip().lower())
    return tags


class RemotiveSource:
    """Fetches jobs from the Remotive public API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch(self, query: str, limit: int, category: str | None) -> list[JobRaw]:
        params: dict = {"limit": limit}
        if query:
            params["search"] = query
        if category:
            params["category"] = category

        async with (
            self._client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        ) as client:
            resp = await client.get(REMOTIVE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        jobs: list[JobRaw] = []
        for item in data.get("jobs", []):
            jobs.append(
                JobRaw(
                    external_id=str(item.get("id", "")),
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Worldwide"),
                    remote_type=_map_remote_type(
                        item.get("job_type", "remote")
                    ),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                    tech_tags=_parse_tags(item),
                    salary_range=item.get("salary") or None,
                    published_at=item.get("publication_date"),
                )
            )
        return jobs
