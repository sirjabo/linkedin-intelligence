"""Celery tasks for ETL."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.etl.skills_extractor import SkillsExtractor
from app.worker import celery_app

logger = get_logger(__name__)


@celery_app.task(name="etl.extract_skills")
def extract_skills_task(limit: int | None = 500) -> dict:
    async def _run() -> dict:
        extractor = SkillsExtractor()
        async with AsyncSessionLocal() as session:
            return await extractor.process_batch(session, limit=limit)

    logger.info("celery_skills_extract_start", limit=limit)
    return asyncio.run(_run())
