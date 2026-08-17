"""LLM-based skills extraction from job descriptions — Sprint B-005."""

from __future__ import annotations

import json
import re
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.job_posting import JobPosting
from app.engine.cv_parser import KNOWN_SKILLS

logger = get_logger(__name__)

BATCH_SIZE = 50

SKILL_CATEGORIES = frozenset(
    {
        "language",
        "framework",
        "cloud",
        "database",
        "ai_ml",
        "devops",
        "tool",
        "methodology",
        "soft_skill",
        "certification",
    }
)

CATEGORY_HINTS: dict[str, str] = {
    "python": "language",
    "sql": "language",
    "javascript": "language",
    "typescript": "language",
    "java": "language",
    "go": "language",
    "fastapi": "framework",
    "django": "framework",
    "flask": "framework",
    "langchain": "ai_ml",
    "langgraph": "ai_ml",
    "rag": "ai_ml",
    "llm": "ai_ml",
    "pytorch": "ai_ml",
    "tensorflow": "ai_ml",
    "aws": "cloud",
    "gcp": "cloud",
    "azure": "cloud",
    "postgresql": "database",
    "postgres": "database",
    "mongodb": "database",
    "redis": "database",
    "docker": "devops",
    "kubernetes": "devops",
    "terraform": "devops",
    "airflow": "tool",
    "dbt": "tool",
    "n8n": "tool",
    "kafka": "tool",
    "spark": "tool",
    "etl": "methodology",
}


class ExtractedSkill(BaseModel):
    name: str
    category: str = "tool"


class SkillsExtractionResult(BaseModel):
    skills: list[ExtractedSkill] = Field(default_factory=list)


class SkillsExtractor:
    """Extract and categorize skills from job posting descriptions."""

    def __init__(self, use_llm: bool | None = None) -> None:
        self.use_llm = (
            use_llm if use_llm is not None else bool(settings.ANTHROPIC_API_KEY)
        )

    async def extract(self, description: str) -> SkillsExtractionResult:
        if self.use_llm:
            try:
                return await self._extract_with_llm(description)
            except Exception as exc:
                logger.warning("skills_llm_fallback", error=str(exc))
        return self._extract_heuristic(description)

    async def _extract_with_llm(self, description: str) -> SkillsExtractionResult:
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        system = (
            "Extract technical skills from a job description. "
            "Return ONLY valid JSON: "
            '{"skills": [{"name": "Python", "category": "language"}, ...]}. '
            f"Categories must be one of: {', '.join(sorted(SKILL_CATEGORIES))}."
        )
        truncated = description[:6000]
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": truncated}],
        )
        content = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return self._parse_llm_json(content)

    def _parse_llm_json(self, content: str) -> SkillsExtractionResult:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return SkillsExtractionResult(skills=[])
        data = json.loads(match.group(0))
        skills: list[ExtractedSkill] = []
        for item in data.get("skills", []):
            name = str(item.get("name", "")).strip()
            category = str(item.get("category", "tool")).strip()
            if not name:
                continue
            if category not in SKILL_CATEGORIES:
                category = CATEGORY_HINTS.get(name.lower(), "tool")
            skills.append(ExtractedSkill(name=name, category=category))
        return SkillsExtractionResult(skills=skills)

    def _extract_heuristic(self, description: str) -> SkillsExtractionResult:
        lower = description.lower()
        skills: list[ExtractedSkill] = []
        for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
            pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
            if re.search(pattern, lower):
                display = skill.title() if len(skill) > 3 else skill.upper()
                specials = {
                    "python": "Python",
                    "sql": "SQL",
                    "langchain": "LangChain",
                    "langgraph": "LangGraph",
                    "fastapi": "FastAPI",
                    "aws": "AWS",
                    "rag": "RAG",
                    "llm": "LLM",
                    "postgresql": "PostgreSQL",
                    "postgres": "PostgreSQL",
                    "dbt": "dbt",
                    "n8n": "n8n",
                }
                name = specials.get(skill, display)
                category = CATEGORY_HINTS.get(skill, "tool")
                skills.append(ExtractedSkill(name=name, category=category))
        # Deduplicate by lower name
        seen: set[str] = set()
        unique: list[ExtractedSkill] = []
        for s in skills:
            key = s.name.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(s)
        return SkillsExtractionResult(skills=unique)

    async def process_batch(
        self,
        db: AsyncSession,
        batch_size: int = BATCH_SIZE,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Process job postings missing skills, in batches of `batch_size`."""
        stmt = (
            select(JobPosting)
            .where(JobPosting.description_clean.is_not(None))
            .where(
                (JobPosting.skills.is_(None))
                | (JobPosting.skills == [])  # type: ignore[comparison-overlap]
            )
            .order_by(JobPosting.crawled_at.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        else:
            stmt = stmt.limit(batch_size * 20)

        result = await db.execute(stmt)
        jobs = list(result.scalars().all())

        processed = 0
        errors = 0

        for i in range(0, len(jobs), batch_size):
            batch = jobs[i : i + batch_size]
            for job in batch:
                try:
                    description = job.description_clean or job.description_raw or ""
                    extraction = await self.extract(description)
                    skill_names = [s.name for s in extraction.skills]
                    skills_jsonb = {
                        "skills": [s.model_dump() for s in extraction.skills],
                        "by_category": _group_by_category(extraction.skills),
                    }
                    await db.execute(
                        update(JobPosting)
                        .where(JobPosting.id == job.id)
                        .values(skills=skill_names, skills_jsonb=skills_jsonb)
                    )
                    processed += 1
                except Exception as exc:
                    errors += 1
                    logger.warning(
                        "skills_extract_job_failed",
                        job_id=str(job.id),
                        error=str(exc),
                    )
            await db.commit()
            logger.info(
                "skills_batch_done",
                batch_index=i // batch_size,
                processed=processed,
                errors=errors,
            )

        return {"processed": processed, "errors": errors, "total_candidates": len(jobs)}


def _group_by_category(skills: list[ExtractedSkill]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for skill in skills:
        grouped.setdefault(skill.category, []).append(skill.name)
    return grouped
