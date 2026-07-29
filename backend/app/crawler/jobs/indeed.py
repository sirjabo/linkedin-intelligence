"""Indeed job crawler — docs/08-CRAWLERS.md + Sprint B-004."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.crawler.base.base_crawler import BaseCrawler, CrawlResult
from app.crawler.config import INDEED_DOMAINS, RATE_LIMITS, ROLES_TO_CRAWL
from app.db.models.job_posting import JobPosting

logger = get_logger(__name__)


def content_hash(title: str, company: str, description: str) -> str:
    payload = f"{title.strip().lower()}|{company.strip().lower()}|{description.strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IndeedCrawler(BaseCrawler):
    """Crawl public Indeed search results for target roles in AR/MX/ES."""

    def __init__(self, max_pages: int = 50, session_factory: async_sessionmaker | None = None) -> None:
        super().__init__(rate_limit_rps=RATE_LIMITS["indeed"])
        self.max_pages = max_pages
        self._session_factory = session_factory

    def crawl(self) -> CrawlResult:
        """Sync entrypoint for CLI / Celery."""
        import asyncio

        return asyncio.run(self.crawl_async())

    async def crawl_async(self) -> CrawlResult:
        started = time.time()
        items_found = 0
        items_new = 0
        items_duplicated = 0
        errors = 0

        session_factory = self._session_factory or _default_session_factory()

        for role_query, location, country, role_category in ROLES_TO_CRAWL:
            try:
                jobs = self._crawl_role(role_query, location, country, role_category)
                items_found += len(jobs)
                new, dupes = await self._upsert_jobs(session_factory, jobs)
                items_new += new
                items_duplicated += dupes
                logger.info(
                    "indeed_role_crawled",
                    role=role_query,
                    location=location,
                    found=len(jobs),
                    new=new,
                    duplicated=dupes,
                    run_id=self.run_id,
                )
            except Exception as exc:
                errors += 1
                logger.exception(
                    "indeed_role_failed",
                    role=role_query,
                    location=location,
                    error=str(exc),
                    run_id=self.run_id,
                )

        duration = time.time() - started
        result = CrawlResult(
            source="indeed",
            run_id=self.run_id,
            items_found=items_found,
            items_new=items_new,
            items_duplicated=items_duplicated,
            errors=errors,
            duration_seconds=duration,
        )
        logger.info("indeed_crawl_finished", **result.__dict__)
        self.close()
        return result

    def _crawl_role(
        self,
        role: str,
        location: str,
        country: str,
        role_category: str,
    ) -> list[dict[str, Any]]:
        base = INDEED_DOMAINS.get(country, "https://www.indeed.com")
        jobs: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for page in range(0, self.max_pages * 10, 10):
            params = {"q": role, "l": location, "start": page}
            url = f"{base}/jobs?{urlencode(params)}"
            try:
                response = self._get(url)
            except Exception as exc:
                logger.warning("indeed_page_failed", url=url, error=str(exc))
                break

            if response.status_code == 403:
                logger.warning("indeed_blocked", url=url, status=403)
                break

            page_jobs = self.parse(response.text)
            if not page_jobs:
                break

            added = 0
            for job in page_jobs:
                external_id = job.get("external_id") or content_hash(
                    job.get("title", ""), job.get("company", ""), job.get("description_raw", "")
                )
                if external_id in seen_ids:
                    continue
                seen_ids.add(external_id)
                job["external_id"] = external_id
                job["country"] = country
                job["role_category"] = role_category
                job["source"] = "indeed"
                job["url"] = job.get("url") or url
                job["content_hash"] = content_hash(
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("description_raw", "") or job.get("description_clean", "") or "",
                )
                jobs.append(job)
                added += 1

            if added == 0:
                break

        return jobs

    def parse(self, raw: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(raw, "lxml")
        cards = soup.select(
            "div.job_seen_beacon, div.cardOutline, li.css-5lfssg, div.jobsearch-ResultsList > div"
        )
        if not cards:
            # Fallback: any element with data-jk
            cards = soup.select("[data-jk]")

        jobs: list[dict[str, Any]] = []
        for card in cards:
            try:
                job = self._parse_card(card)
                if job:
                    jobs.append(job)
            except Exception as exc:
                logger.debug("indeed_card_parse_error", error=str(exc))
        return jobs

    def _parse_card(self, card: Any) -> dict[str, Any] | None:
        jk = card.get("data-jk") or ""
        title_el = card.select_one(
            "h2.jobTitle a, h2.jobTitle span, a.jcs-JobTitle, h2 a"
        )
        company_el = card.select_one(
            "[data-testid='company-name'], span.companyName, span.css-1h7lukg"
        )
        location_el = card.select_one(
            "[data-testid='text-location'], div.companyLocation, .locationsContainer"
        )
        snippet_el = card.select_one(
            "[data-testid='job-snippet'], div.job-snippet, .jobCardShelfContainer"
        )

        title = title_el.get_text(" ", strip=True) if title_el else ""
        company = company_el.get_text(" ", strip=True) if company_el else ""
        if not title or not company:
            return None

        href = ""
        if title_el and title_el.name == "a":
            href = title_el.get("href", "")
        elif title_el:
            parent_a = title_el.find_parent("a")
            href = parent_a.get("href", "") if parent_a else ""

        description = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        external_id = jk or content_hash(title, company, description)[:32]

        return {
            "external_id": external_id,
            "title": title[:255],
            "company": company[:255],
            "location": location_el.get_text(" ", strip=True) if location_el else None,
            "description_raw": description,
            "description_clean": _clean_description(description),
            "url": href,
            "remote": bool(re.search(r"remote|remoto|híbrido|hybrid", description, re.I)),
            "posted_at": datetime.now(UTC),
        }

    async def _upsert_jobs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        jobs: list[dict[str, Any]],
    ) -> tuple[int, int]:
        if not jobs:
            return 0, 0

        new_count = 0
        dupe_count = 0

        async with session_factory() as session:
            for job in jobs:
                # Dedup by content hash first
                hash_val = job.get("content_hash")
                if hash_val:
                    existing = await session.execute(
                        select(JobPosting.id).where(JobPosting.content_hash == hash_val).limit(1)
                    )
                    if existing.scalar_one_or_none():
                        dupe_count += 1
                        continue

                stmt = (
                    insert(JobPosting)
                    .values(
                        source=job["source"],
                        external_id=job["external_id"],
                        url=job.get("url"),
                        title=job["title"],
                        company=job["company"],
                        location=job.get("location"),
                        country=job.get("country"),
                        remote=job.get("remote", False),
                        role_category=job.get("role_category"),
                        description_raw=job.get("description_raw"),
                        description_clean=job.get("description_clean"),
                        content_hash=hash_val,
                        posted_at=job.get("posted_at"),
                        crawled_at=datetime.now(UTC),
                    )
                    .on_conflict_do_nothing(constraint="uq_job_postings_source_external_id")
                    .returning(JobPosting.id)
                )
                result = await session.execute(stmt)
                inserted = result.scalar_one_or_none()
                if inserted:
                    new_count += 1
                else:
                    dupe_count += 1
            await session.commit()

        return new_count, dupe_count


def _clean_description(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned


def _default_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def run_indeed_crawl(max_pages: int = 50) -> CrawlResult:
    crawler = IndeedCrawler(max_pages=max_pages)
    return await crawler.crawl_async()
