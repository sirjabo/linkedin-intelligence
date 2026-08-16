"""GitHub public profile ingestion via the GitHub REST API.

Fetches: user bio, public repos (README snippets), languages, pinned-style data.
No authentication required for public profiles (60 req/hour unauthenticated).
Uses a GitHub token from settings if available for higher rate limits.

Security: all URLs validated through SSRF guard before fetch.
"""
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ssrf import validate_url_not_private

logger = get_logger(__name__)

_GH_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "LinkedIn-Intelligence/2.0",
}


def _extract_username(url_or_username: str) -> str:
    """Accept 'https://github.com/torvalds' or 'torvalds' → 'torvalds'."""
    url_or_username = url_or_username.strip().rstrip("/")
    parsed = urlparse(url_or_username)
    if parsed.netloc in {"github.com", "www.github.com"}:
        path = parsed.path.strip("/")
        if "/" in path:
            raise ValueError(f"Expected a profile URL, not a repo URL: {url_or_username!r}")
        return path
    # Treat as plain username if no scheme
    if not parsed.scheme:
        return url_or_username
    raise ValueError(f"Not a GitHub URL: {url_or_username!r}")


async def _gh_get(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    url = f"{_GH_API}{path}"
    validate_url_not_private(url)
    resp = await client.get(url, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()  # type: ignore[return-value]


def _extract_years_from_bio(bio: str) -> int | None:
    """Try to extract years of experience mentioned in bio text."""
    match = re.search(r"(\d+)\+?\s*years?", bio, re.IGNORECASE)
    return int(match.group(1)) if match else None


async def fetch_github_profile(url_or_username: str) -> dict[str, Any]:
    """Fetch a GitHub user's public profile and repos.

    Returns a dict compatible with ExtractedProfile from profile_agent.
    """
    username = _extract_username(url_or_username)
    if not re.match(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$", username):
        raise ValueError(f"Invalid GitHub username: {username!r}")

    token = getattr(settings, "GITHUB_TOKEN", None)
    auth_headers = {**_HEADERS}
    if token:
        auth_headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        try:
            user_data = await _gh_get(client, f"/users/{username}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ValueError(f"GitHub user not found: {username!r}") from exc
            raise

        # Fetch up to 10 most-starred repos for skill inference
        repos_data: list[dict[str, Any]] = []
        try:
            repos_raw = await _gh_get(client, f"/users/{username}/repos?sort=stars&per_page=10&type=owner")
            if isinstance(repos_raw, list):
                repos_data = repos_raw
        except Exception:
            pass

    # Build skills list from repo languages
    language_counts: dict[str, int] = {}
    for repo in repos_data:
        lang = repo.get("language")
        if lang:
            language_counts[lang] = language_counts.get(lang, 0) + 1

    skills = [
        {"canonical_name": lang, "years_experience": None, "confidence": 0.6}
        for lang, _ in sorted(language_counts.items(), key=lambda x: -x[1])
    ]

    # Build experience entries from repos
    projects = []
    for repo in repos_data[:5]:
        name = repo.get("name", "")
        description = repo.get("description") or ""
        stars = repo.get("stargazers_count", 0)
        lang = repo.get("language")
        tech = [lang] if lang else []
        if name:
            projects.append({
                "name": name,
                "description": description,
                "tech": tech,
                "highlights": [f"⭐ {stars} GitHub stars"] if stars > 0 else [],
                "url": repo.get("html_url"),
            })

    bio = user_data.get("bio") or ""
    name = user_data.get("name") or ""
    location = user_data.get("location") or ""
    company = user_data.get("company") or ""
    blog = user_data.get("blog") or ""
    gh_url = user_data.get("html_url") or f"https://github.com/{username}"

    summary_parts = [bio] if bio else []
    if company:
        summary_parts.append(f"Works at {company.lstrip('@')}")
    summary = " | ".join(summary_parts)

    experience = []
    if company:
        experience.append({
            "role": "Software Engineer",
            "company": company.lstrip("@"),
            "start_year": None,
            "end_year": None,
            "bullets": [bio] if bio else [],
            "technologies": list(language_counts.keys())[:5],
        })

    logger.info(
        "github_profile_fetched",
        username=username,
        repos=len(repos_data),
        skills=len(skills),
    )

    return {
        "name": name,
        "email": None,
        "location": location,
        "summary": summary,
        "github_url": gh_url,
        "portfolio_url": blog if blog.startswith("http") else None,
        "skills": skills,
        "experience": experience,
        "education": [],
        "projects": projects,
        "certifications": [],
        "achievements": [],
        "languages": [],
        "extraction_confidence": 0.65,
    }
