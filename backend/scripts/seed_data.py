"""Seed skills catalog, skill_demand, and sample job postings for MVP."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.db.models.job_posting import JobPosting
from app.db.models.skill_demand import SkillDemand
from app.db.models.skills_catalog import SkillsCatalog
from app.db.session import AsyncSessionLocal
from app.engine.ats import FALLBACK_KEYWORDS

configure_logging()
logger = get_logger(__name__)

SAMPLE_DESCRIPTIONS = {
    "ai_engineer": [
        "We are hiring an AI Engineer with strong Python, LangChain, RAG, FastAPI and LLM experience. "
        "You will build agents with LangGraph, use pgvector for embeddings, and deploy on AWS with Docker.",
        "AI Engineer role: experience with OpenAI, Claude, Prompt Engineering, Vector DB, Python, SQL, "
        "and production ML systems using PyTorch. Git and CI/CD required.",
        "Looking for AI Engineers skilled in RAG pipelines, embeddings, FastAPI microservices, "
        "LangChain, Docker, and cloud (AWS/GCP).",
    ],
    "data_engineer": [
        "Data Engineer: Python, SQL, Spark, Airflow, Kafka, AWS. Build ETL pipelines and data lakes. "
        "Experience with PostgreSQL, dbt and Docker preferred.",
        "Senior Data Engineer with Spark, Airflow, Kafka, Terraform, Kubernetes and BigQuery.",
        "We need a Data Engineer proficient in Python, SQL, ETL, Snowflake, Airflow and Git.",
    ],
    "analytics_engineer": [
        "Analytics Engineer: SQL, dbt, Python, Looker, Snowflake. Strong data modeling skills. "
        "Experience with Power BI and Airflow is a plus.",
        "Join our analytics team: dbt, BigQuery, SQL, pandas, Tableau, Git and ETL.",
        "Analytics Engineer with SQL, dbt, Snowflake, Power BI, n8n and Python for data pipelines.",
    ],
}

COMPANIES = [
    "Mercado Libre",
    "Globant",
    "Ualá",
    "Despegar",
    "Auth0",
    "Lemon Cash",
    "Bitso",
    "BBVA",
    "Naranja X",
    "Rappi",
]


def _slugify(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(".", "")
        .replace("_", "-")
    )


async def seed_skills(session: AsyncSession) -> dict[str, uuid.UUID]:
    skill_ids: dict[str, uuid.UUID] = {}
    for role, keywords in FALLBACK_KEYWORDS.items():
        for name, _weight, aliases in keywords:
            existing = await session.execute(
                select(SkillsCatalog).where(SkillsCatalog.slug == _slugify(name))
            )
            skill = existing.scalar_one_or_none()
            if skill is None:
                skill = SkillsCatalog(
                    id=uuid.uuid4(),
                    name=name.lower(),
                    slug=_slugify(name),
                    display_name=name,
                    category=_guess_category(name),
                    aliases=aliases,
                    is_active=True,
                )
                session.add(skill)
                await session.flush()
            skill_ids[name] = skill.id
    await session.commit()
    logger.info("skills_seeded", count=len(skill_ids))
    return skill_ids


def _guess_category(name: str) -> str:
    mapping = {
        "Python": "language",
        "SQL": "language",
        "LangChain": "ai_ml",
        "LangGraph": "ai_ml",
        "RAG": "ai_ml",
        "LLM": "ai_ml",
        "FastAPI": "framework",
        "Docker": "devops",
        "AWS": "cloud",
        "Kubernetes": "devops",
        "Spark": "tool",
        "Airflow": "tool",
        "Kafka": "tool",
        "dbt": "tool",
        "PostgreSQL": "database",
        "ETL": "methodology",
        "Snowflake": "database",
        "BigQuery": "cloud",
        "Git": "tool",
        "Power BI": "tool",
        "Tableau": "tool",
        "Looker": "tool",
        "pandas": "tool",
        "n8n": "tool",
        "PyTorch": "ai_ml",
        "OpenAI": "ai_ml",
        "Embeddings": "ai_ml",
        "Prompt Engineering": "ai_ml",
        "Vector DB": "database",
        "Data Modeling": "methodology",
        "Terraform": "devops",
    }
    return mapping.get(name, "tool")


async def seed_skill_demand(
    session: AsyncSession, skill_ids: dict[str, uuid.UUID], total_jobs: int = 500
) -> None:
    period_end = date.today()
    period_start = period_end - timedelta(days=7)

    for role, keywords in FALLBACK_KEYWORDS.items():
        for name, weight, _aliases in keywords:
            skill_id = skill_ids[name]
            # Map algorithm weight → approximate market frequency for DB storage
            # weight 1.0 → ~90%, 0.85 → ~70%, 0.5 → ~35%, 0.3 → ~20%
            approx_freq = min(95.0, max(10.0, weight * 85.0))
            freq = Decimal(str(round(approx_freq, 2)))
            job_count = int(float(freq) / 100 * total_jobs)
            existing = await session.execute(
                select(SkillDemand).where(
                    SkillDemand.skill_id == skill_id,
                    SkillDemand.role_category == role,
                    SkillDemand.country == "AR",
                    SkillDemand.period_start == period_start,
                )
            )
            if existing.scalar_one_or_none():
                continue
            session.add(
                SkillDemand(
                    id=uuid.uuid4(),
                    skill_id=skill_id,
                    role_category=role,
                    country="AR",
                    job_count=job_count,
                    total_jobs=total_jobs,
                    frequency_pct=freq,
                    prev_week_pct=freq - Decimal("2.0"),
                    change_pct=Decimal("2.0"),
                    trend="rising" if weight >= 0.7 else "stable",
                    period_start=period_start,
                    period_end=period_end,
                )
            )
    await session.commit()
    logger.info("skill_demand_seeded")


async def seed_jobs(session: AsyncSession, target_count: int = 500) -> int:
    result = await session.execute(select(func.count()).select_from(JobPosting))
    current = int(result.scalar_one())
    if current >= target_count:
        logger.info("jobs_already_seeded", count=current)
        return current

    to_create = target_count - current
    roles = list(SAMPLE_DESCRIPTIONS.keys())
    countries = ["AR", "MX", "ES"]

    for i in range(to_create):
        role = roles[i % len(roles)]
        desc_pool = SAMPLE_DESCRIPTIONS[role]
        description = desc_pool[i % len(desc_pool)]
        company = COMPANIES[i % len(COMPANIES)]
        title = f"{role.replace('_', ' ').title()} {i // len(COMPANIES) + 1}"
        country = countries[i % len(countries)]
        external_id = f"seed-{role}-{i}"
        payload = f"{title}|{company}|{description}".lower()
        c_hash = hashlib.sha256(payload.encode()).hexdigest()

        # Heuristic skills from description
        from app.etl.skills_extractor import SkillsExtractor

        extraction = SkillsExtractor(use_llm=False)._extract_heuristic(description)
        skill_names = [s.name for s in extraction.skills]

        session.add(
            JobPosting(
                id=uuid.uuid4(),
                source="indeed",
                external_id=external_id,
                url=f"https://example.com/jobs/{external_id}",
                title=title[:255],
                company=company,
                location={"AR": "Buenos Aires", "MX": "Ciudad de México", "ES": "Madrid"}[
                    country
                ],
                country=country,
                remote=i % 3 == 0,
                role_category=role,
                seniority=["junior", "mid", "senior"][i % 3],
                description_raw=description,
                description_clean=description,
                skills=skill_names,
                skills_jsonb={
                    "skills": [s.model_dump() for s in extraction.skills],
                    "by_category": {},
                },
                content_hash=c_hash,
                posted_at=datetime.now(UTC) - timedelta(days=i % 30),
                crawled_at=datetime.now(UTC),
            )
        )
        if (i + 1) % 100 == 0:
            await session.commit()
            logger.info("jobs_seed_progress", created=i + 1)

    await session.commit()
    logger.info("jobs_seeded", created=to_create)
    return current + to_create


async def main() -> None:
    async with AsyncSessionLocal() as session:
        skill_ids = await seed_skills(session)
        await seed_skill_demand(session, skill_ids, total_jobs=500)
        count = await seed_jobs(session, target_count=500)
        logger.info("seed_complete", jobs=count)


if __name__ == "__main__":
    asyncio.run(main())
