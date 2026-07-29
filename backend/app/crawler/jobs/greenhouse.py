"""Greenhouse job board crawler — Sprint 002 B-008."""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.crawler.base.base_crawler import BaseCrawler, CrawlResult
from app.crawler.config import RATE_LIMITS

logger = get_logger(__name__)

GREENHOUSE_COMPANIES = [
    "anthropic",
    "notion",
    "figma",
    "vercel",
    "linear",
    "mercadolibre",
    "auth0",
    "globant",
]

TARGET_ROLES = [
    "data engineer",
    "analytics engineer",
    "ai engineer",
    "ml engineer",
    "machine learning",
]


class GreenhouseCrawler(BaseCrawler):
    """Crawl public Greenhouse board APIs for data/AI roles."""

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

    def __init__(self, rate_limit_rps: float | None = None) -> None:
        super().__init__(rate_limit_rps=rate_limit_rps or RATE_LIMITS.get("greenhouse", 0.5))

    def crawl(self) -> CrawlResult:
        started = time.time()
        all_jobs: list[dict[str, Any]] = []
        errors = 0

        for company in GREENHOUSE_COMPANIES:
            try:
                jobs = self.crawl_company(company)
                all_jobs.extend(jobs)
            except Exception as exc:
                errors += 1
                logger.warning(
                    "greenhouse_company_failed",
                    company=company,
                    error=str(exc),
                    run_id=self.run_id,
                )

        duration = time.time() - started
        logger.info(
            "greenhouse_crawl_complete",
            total_jobs=len(all_jobs),
            errors=errors,
            run_id=self.run_id,
        )
        return CrawlResult(
            source="greenhouse",
            run_id=self.run_id,
            items_found=len(all_jobs),
            items_new=len(all_jobs),
            items_duplicated=0,
            errors=errors,
            duration_seconds=duration,
        )

    def parse(self, raw: str) -> list[dict[str, Any]]:
        """Greenhouse responses are JSON; parse is unused for this source."""
        del raw
        return []

    def crawl_company(self, company: str) -> list[dict[str, Any]]:
        """Fetch all jobs for one Greenhouse company board."""
        url = self.BASE_URL.format(company=company)
        try:
            response = self._get(url, params={"content": "true"})
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("greenhouse_fetch_failed", company=company, error=str(exc))
            return []

        jobs = data.get("jobs", [])
        relevant: list[dict[str, Any]] = []

        for job in jobs:
            title_lower = str(job.get("title", "")).lower()
            if any(role in title_lower for role in TARGET_ROLES):
                relevant.append(
                    {
                        "title": job.get("title", ""),
                        "company": company,
                        "location": self._extract_location(job),
                        "url": job.get("absolute_url", ""),
                        "description": job.get("content", ""),
                        "source": "greenhouse",
                        "external_id": str(job.get("id", "")),
                    }
                )

        logger.info(
            "greenhouse_company_crawled",
            company=company,
            total=len(jobs),
            relevant=len(relevant),
        )
        return relevant

    def _extract_location(self, job: dict[str, Any]) -> str:
        offices = job.get("offices") or []
        if offices and isinstance(offices[0], dict):
            return str(offices[0].get("name") or "Remote")
        location = job.get("location")
        if isinstance(location, dict):
            return str(location.get("name") or "Remote")
        return "Remote"
