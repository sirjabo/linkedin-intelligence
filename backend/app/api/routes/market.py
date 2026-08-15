"""Market intelligence endpoints — live skill frequencies from external job sources."""
import asyncio
import re
import time
from collections import Counter
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.market import (
    SkillFrequency, SkillsRadarResponse,
    CompanyHiring, MarketTrendItem, MarketTrendsResponse,
)
from app.services.job_sources.base import JobRaw
from app.services.job_sources.remotive import RemotiveSource
from app.services.job_sources.arbeitnow import ArbeitnowSource
from app.services.job_sources.remoteok import RemoteOKSource
from app.db.session import get_db
from app.db.models.market import SkillSnapshot
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

# Salary ranges by role (USD/month, remote LATAM-international market)
_SALARY_RANGES: dict[str, dict] = {
    "ai_engineer": {
        "min_usd": 4000, "max_usd": 12000, "median_usd": 7000,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $2k–$4k · Mid: $4k–$7k · Senior/Lead: $7k–$12k+",
        "sources": ["Remotive", "LinkedIn Jobs", "Glassdoor LATAM 2025"],
    },
    "data_engineer": {
        "min_usd": 3500, "max_usd": 10000, "median_usd": 6000,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $2k–$3.5k · Mid: $3.5k–$6k · Senior: $6k–$10k",
        "sources": ["Remotive", "LinkedIn Jobs", "Glassdoor LATAM 2025"],
    },
    "analytics_engineer": {
        "min_usd": 3000, "max_usd": 9000, "median_usd": 5500,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $2k–$3k · Mid: $3k–$5.5k · Senior: $5.5k–$9k",
        "sources": ["Remotive", "LinkedIn Jobs", "dbt community survey 2025"],
    },
    "ml_engineer": {
        "min_usd": 4500, "max_usd": 14000, "median_usd": 8000,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $2.5k–$4.5k · Mid: $4.5k–$8k · Senior: $8k–$14k+",
        "sources": ["Remotive", "LinkedIn Jobs", "Glassdoor LATAM 2025"],
    },
    "backend_engineer": {
        "min_usd": 3000, "max_usd": 10000, "median_usd": 5500,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $1.5k–$3k · Mid: $3k–$5.5k · Senior: $5.5k–$10k",
        "sources": ["Remotive", "LinkedIn Jobs", "Glassdoor LATAM 2025"],
    },
    "frontend_engineer": {
        "min_usd": 2500, "max_usd": 9000, "median_usd": 5000,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $1.5k–$2.5k · Mid: $2.5k–$5k · Senior: $5k–$9k",
        "sources": ["Remotive", "LinkedIn Jobs", "Glassdoor LATAM 2025"],
    },
    "devops_engineer": {
        "min_usd": 3500, "max_usd": 11000, "median_usd": 6500,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $2k–$3.5k · Mid: $3.5k–$6.5k · Senior/SRE: $6.5k–$11k",
        "sources": ["Remotive", "LinkedIn Jobs", "Glassdoor LATAM 2025"],
    },
    "data_scientist": {
        "min_usd": 3500, "max_usd": 11000, "median_usd": 6500,
        "currency": "USD", "period": "month",
        "notes": "Seniority junior: $2k–$3.5k · Mid: $3.5k–$6.5k · Senior/Staff: $6.5k–$11k",
        "sources": ["Remotive", "LinkedIn Jobs", "Glassdoor LATAM 2025"],
    },
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
    if slug in _TECH_CATEGORIES:
        return _TECH_CATEGORIES[slug]
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
    Results are cached in-memory for 30 minutes per role.
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


async def save_skill_snapshot(role: str, db: AsyncSession) -> None:
    """Persist today's skill frequencies to DB (idempotent — uses upsert logic)."""
    import uuid as _uuid
    jobs, tag_counter = await _aggregate_skills(role)
    n = max(len(jobs), 1)
    today = date.today()

    for slug, count in tag_counter.most_common(50):
        display = slug.replace("+", "++").title().replace("++", "+").replace("Js", "JS")
        existing = await db.execute(
            select(SkillSnapshot).where(
                SkillSnapshot.role == role,
                SkillSnapshot.skill_slug == slug,
                SkillSnapshot.snapshot_date == today,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.frequency_pct = round(count / n * 100, 1)
            row.job_count = count
        else:
            db.add(SkillSnapshot(
                id=_uuid.uuid4(),
                role=role,
                skill_slug=slug,
                skill_name=display,
                category=_categorize(slug),
                frequency_pct=round(count / n * 100, 1),
                job_count=count,
                snapshot_date=today,
            ))
    await db.commit()


async def _get_skill_trends(role: str, db: AsyncSession, days: int = 7) -> dict[str, str]:
    """Return trend direction for each skill by comparing today vs N days ago."""
    today = date.today()
    past = today - timedelta(days=days)

    today_result = await db.execute(
        select(SkillSnapshot.skill_slug, SkillSnapshot.frequency_pct).where(
            SkillSnapshot.role == role,
            SkillSnapshot.snapshot_date == today,
        )
    )
    today_map = {row.skill_slug: row.frequency_pct for row in today_result}

    past_result = await db.execute(
        select(SkillSnapshot.skill_slug, SkillSnapshot.frequency_pct).where(
            SkillSnapshot.role == role,
            SkillSnapshot.snapshot_date == past,
        )
    )
    past_map = {row.skill_slug: row.frequency_pct for row in past_result}

    trends: dict[str, str] = {}
    for slug, freq in today_map.items():
        old = past_map.get(slug)
        if old is None:
            trends[slug] = "new"
        elif freq > old + 2:
            trends[slug] = "rising"
        elif freq < old - 2:
            trends[slug] = "falling"
        else:
            trends[slug] = "stable"
    return trends


@router.get("/roles")
async def list_roles() -> dict:
    """Return supported role slugs."""
    return {"roles": _VALID_ROLES}


@router.get("/skills/{role}", response_model=SkillsRadarResponse)
async def get_skills_radar(
    role: str,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> SkillsRadarResponse:
    """Top skills by frequency for a given role, with historical trend direction."""
    jobs, tag_counter = await _aggregate_skills(role, limit)
    n = max(len(jobs), 1)
    today = date.today().isoformat()

    trends = await _get_skill_trends(role, db)

    skills: list[SkillFrequency] = []
    for rank, (slug, count) in enumerate(tag_counter.most_common(limit), start=1):
        display = slug.replace("+", "++").title().replace("++", "+").replace("Js", "JS")
        skills.append(SkillFrequency(
            rank=rank,
            name=display,
            slug=slug,
            category=_categorize(slug),
            frequency_pct=round(count / n * 100, 1),
            job_count=count,
            trend=trends.get(slug, "stable"),
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


@router.get("/salary/{role}")
async def get_salary_range(role: str) -> dict:
    """Salary ranges by role for remote LATAM-international market (USD/month).

    Data sourced from Remotive job listings, LinkedIn Jobs, and Glassdoor surveys.
    Ranges are approximate and based on 2025 market data.
    """
    data = _SALARY_RANGES.get(role)
    if not data:
        return {
            "role": role,
            "available": False,
            "message": f"No salary data for role '{role}'. Supported: {', '.join(_SALARY_RANGES)}",
        }
    return {
        "role": role,
        "available": True,
        "as_of": "2025",
        **data,
    }


@router.get("/salary")
async def list_salary_ranges() -> dict:
    """All salary ranges for all supported roles."""
    return {
        "as_of": "2025",
        "currency": "USD",
        "period": "month",
        "market": "Remote / LATAM-international",
        "roles": {
            role: {
                "min_usd": data["min_usd"],
                "max_usd": data["max_usd"],
                "median_usd": data["median_usd"],
                "notes": data["notes"],
            }
            for role, data in _SALARY_RANGES.items()
        },
    }
