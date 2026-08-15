"""RemoteOK.com public API (no auth required).

Endpoint: https://remoteok.com/api?tag={tag}
Rate limit: 1 req / 60s per tag recommended.
"""
import httpx

from app.services.job_sources.base import JobRaw

REMOTEOK_URL = "https://remoteok.com/api"
DEFAULT_TIMEOUT = 12.0


def _extract_tags(item: dict) -> list[str]:
    tags: list[str] = []
    for t in item.get("tags", []):
        if isinstance(t, str):
            tags.append(t.strip().lower())
    return tags


def _salary_string(item: dict) -> str | None:
    lo = item.get("salary_min")
    hi = item.get("salary_max")
    if lo and hi:
        return f"${lo:,}–${hi:,}"
    if lo:
        return f"${lo:,}+"
    return None


class RemoteOKSource:
    """Fetches remote-only tech jobs from RemoteOK's public API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch(self, query: str, limit: int, category: str | None) -> list[JobRaw]:
        # RemoteOK uses the first word of the query as a tag filter
        tag = (query or "").split()[0].lower() if query else ""
        params = {}
        if tag:
            params["tag"] = tag

        async with (
            self._client if self._client
            else httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers={"User-Agent": "JobRadar/1.0"})
        ) as client:
            resp = await client.get(REMOTEOK_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        # API returns a legal notice as the first element — skip it
        jobs: list[JobRaw] = []
        for item in data:
            if not isinstance(item, dict) or item.get("legal"):
                continue

            title = item.get("position", "")
            if not title:
                continue

            jobs.append(JobRaw(
                external_id=str(item.get("id", item.get("slug", ""))),
                title=title,
                company=item.get("company", ""),
                location=item.get("location") or "Remote",
                remote_type="remote",
                url=item.get("url", ""),
                description=item.get("description", ""),
                tech_tags=_extract_tags(item),
                salary_range=_salary_string(item),
                published_at=item.get("date"),
            ))

            if len(jobs) >= limit:
                break

        return jobs
