"""Celery tasks for crawlers."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.crawler.jobs.indeed import run_indeed_crawl
from app.worker import celery_app

logger = get_logger(__name__)


@celery_app.task(name="crawler.indeed")
def crawl_indeed_task(max_pages: int = 50) -> dict:
    logger.info("celery_indeed_start", max_pages=max_pages)
    result = asyncio.run(run_indeed_crawl(max_pages=max_pages))
    return {
        "source": result.source,
        "run_id": result.run_id,
        "items_found": result.items_found,
        "items_new": result.items_new,
        "items_duplicated": result.items_duplicated,
        "errors": result.errors,
        "duration_seconds": result.duration_seconds,
    }
