"""Market intelligence endpoints — live skill frequencies from external job sources."""
import asyncio
import re
import time
from collections import Counter
from datetime import date, datetime
from fastapi import APIRouter, Query

from app.schemas.market import (
    SkillFrequency, SkillsRadarResponse,
    CompanyHiring, MarketTrendItem, MarketTrendsResponse,
)
from app.services.job_sources.base import JobRaw
from app.services.job_sources.remotive import RemotiveSource
from app.services.job_sources.arbeitnow import ArbeitnowSource
from app.services.job_sources.remoteok import RemoteOKSource
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/market", tags=["market"])

_ALL_SOURCES = {
    "remotive": RemotiveSource,
    "arbeitnow": ArbeitnowSource,
    "remoteok": RemoteOKSource,
}

ROLE_QUERIES: dict[str, str] = {
    "ai_engineer": "AI Engineer",
    "data_engineer": "Data Engineer",
    "analytics_engineer": "Analytics Engineer",
    "ml_engineer": "Machine Learning Engineer",
    "backend_engineer": "Backend Engineer Python",
    "frontend_engineer": "Frontend Engineer React",
    "devops_engineer": "DevOps Engineer",
    "data_scientist": "Data Scientist",
}

_VALID_ROLES = sorted(ROLE_QUERIES.keys())

_TECH_CATEGORIES: dict[str, str] = {
    "python": "language", "javascript": "language", "typescript": "language",
    "java": "language", "golang": "language", "rust": "language", "ruby": "language",
    "scala": "language", "kotlin": "language", "swift": "language", "php": "language",
    "rlang": "language", "sql": "language", "bash": "language", "c++": "language",
    "react": "frontend", "vue": "frontend", "angular": "frontend", "nextjs": "frontend",
    "svelte": "frontend", "tailwind": "frontend", "graphql": "frontend",
    "fastapi": "backend", "django": "backend", "flask": "backend", "express": "backend",
    "node": "backend", "spring": "backend", "rails": "backend", "laravel": "backend",
    "langchain": "ai_ml", "langgraph": "ai_ml", "openai": "ai_ml", "pytorch": "ai_ml",
    "tensorflow": "ai_ml", "scikit": "ai_ml", "huggingface": "ai_ml", "llm": "ai_ml",
    "rag": "ai_ml", "mlflow": "ai_ml", "dbt": "data", "spark": "data",
    "airflow": "data", "kafka": "data", "snowflake": "data", "databricks": "data",
    "pandas": "data", "numpy": "data", "polars": "data", "duckdb": "data",
    "aws": "cloud", "gcp": "cloud", "azure": "cloud", "terraform": "cloud",
    "docker": "cloud", "kubernetes": "cloud", "k8s": "cloud", "pulumi": "cloud",
    "postgres": "database", "postgresql": "database", "mysql": "database",
    "mongodb": "database", "redis": "database", "elasticsearch": "database",
    "pgvector": "database", "pinecone": "database", "weaviate": "database",
    "git": "tools", "github": "tools", "gitlab": "tools", "jira": "tools",
}

_SLUG_RE = re.compile(r"[^a-z0-9+#.]")

# In-memory TTL cache: key → (payload, expires_at)
_CACHE: dict[str, tuple[object, float]] = {}
_CACHE_TTL = 1800  # 30 minutes


def _cache_get(key: str) -> object | None:
    entry = _CACHE.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    _CACHE.pop(key, None)
    return None


def _cache_set(key: str, value: object) -> None:
    _CACHE[key] = (value, time.monotonic() + _CACHE_TTL)


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("", name.lower().replace(" ", ""))


def _categorize(slug: str) -> str:
    # Exact match first
    if slug in _TECH_CATEGORIES:
        return _TECH_CATEGORIES[slug]
    # Substring match — only for keys >= 4 chars to avoid false positives ("r", "go")
    for key, cat in _TECH_CATEGORIES.items():
        if len(key) >= 4 and (key in slug or slug in key):
            return cat
    return "other"


async def _fetch_safe(source_name: str, source_cls, query: str, limit: int) -> list[JobRaw]:
    try:
        src = source_cls()
        return await src.fetch(query=query, limit=limit, category=None)
    except Exception as exc:
        logger.warning("market_source_failed", source=source_name, query=query, error=str(exc))
        return []


async def _aggregate_skills(role: str, limit: int = 50) -> tuple[list[JobRaw], Counter]:
    """Fetch jobs for role from all sources and count tech tag frequencies.

    Results are cached in-memory for 30 minutes per role to avoid hammering
    external job boards on every request.
    """
    cache_key = f"skills:{role}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    query = ROLE_QUERIES.get(role, role.replace("_", " ").title())
    per_source = max(40, limit)

    tasks = [
        _fetch_safe(name, cls, query, per_source)
        for name, cls in _ALL_SOURCES.items()
    ]
    batches = await asyncio.gather(*tasks)

    # Deduplicate by URL
    seen: set[str] = set()
    jobs: list[JobRaw] = []
    for batch in batches:
        for job in batch:
            if job.url and job.url not in seen:
                seen.add(job.url)
                jobs.append(job)

    tag_counter: Counter = Counter()
    for job in jobs:
        for tag in job.tech_tags:
            tag_counter[_slugify(tag)] += 1

    result = (jobs, tag_counter)
    _cache_set(cache_key, result)
    return result


@router.get("/roles")
async def list_roles() -> dict:
    """Return supported role slugs."""
    return {"roles": _VALID_ROLES}


@router.get("/skills/{role}", response_model=SkillsRadarResponse)
async def get_skills_radar(
    role: str,
    limit: int = Query(default=30, ge=1, le=100),
) -> SkillsRadarResponse:
    """Top skills by frequency for a given role, sourced live from job boards."""
    jobs, tag_counter = await _aggregate_skills(role, limit)
    n = max(len(jobs), 1)
    today = date.today().isoformat()

    skills: list[SkillFrequency] = []
    for rank, (slug, count) in enumerate(tag_counter.most_common(limit), start=1):
        # Rebuild a display name: capitalize each token
        display = slug.replace("+", "++").title().replace("++", "+").replace("Js", "JS")
        skills.append(SkillFrequency(
            rank=rank,
            name=display,
            slug=slug,
            category=_categorize(slug),
            frequency_pct=round(count / n * 100, 1),
            job_count=count,
            trend="stable",
        ))

    return SkillsRadarResponse(
        role=role,
        period=today,
        total_jobs_analyzed=len(jobs),
        skills=skills,
    )


@router.get("/trends", response_model=MarketTrendsResponse)
async def get_market_trends(
    role: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> MarketTrendsResponse:
    """Top skills and companies currently hiring, optionally filtered by role."""
    effective_role = role if role in ROLE_QUERIES else "ai_engineer"
    jobs, tag_counter = await _aggregate_skills(effective_role, limit)
    n = max(len(jobs), 1)
    now = datetime.utcnow().isoformat() + "Z"

    top_skills = [
        MarketTrendItem(
            skill=slug.replace("+", "++").title().replace("++", "+").replace("Js", "JS"),
            frequency_pct=round(count / n * 100, 1),
            job_count=count,
            message=f"{slug} aparece en el {round(count/n*100)}% de las ofertas de {effective_role}",
        )
        for slug, count in tag_counter.most_common(limit)
    ]

    # Company frequency
    company_counter: Counter = Counter()
    for job in jobs:
        if job.company:
            company_counter[job.company.strip()] += 1

    top_companies = [
        CompanyHiring(rank=i + 1, name=name, job_count=cnt)
        for i, (name, cnt) in enumerate(company_counter.most_common(10))
    ]

    return MarketTrendsResponse(
        generated_at=now,
        role=effective_role,
        total_jobs_analyzed=n,
        top_skills=top_skills,
        top_companies=top_companies,
    )
