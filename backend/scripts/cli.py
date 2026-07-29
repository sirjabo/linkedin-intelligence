"""CLI entrypoints."""

from __future__ import annotations

import argparse
import asyncio

from app.core.logging import configure_logging, get_logger
from app.crawler.jobs.indeed import run_indeed_crawl
from app.db.session import AsyncSessionLocal
from app.etl.skills_extractor import SkillsExtractor

configure_logging()
logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    crawl = sub.add_parser("crawl-indeed", help="Run Indeed crawler")
    crawl.add_argument("--max-pages", type=int, default=5)

    skills = sub.add_parser("extract-skills", help="Extract skills from job postings")
    skills.add_argument("--limit", type=int, default=500)

    sub.add_parser("seed", help="Seed catalog + sample jobs")

    args = parser.parse_args()

    if args.command == "crawl-indeed":
        result = asyncio.run(run_indeed_crawl(max_pages=args.max_pages))
        logger.info("crawl_done", **result.__dict__)
    elif args.command == "extract-skills":
        async def _extract() -> dict:
            async with AsyncSessionLocal() as session:
                extractor = SkillsExtractor()
                return await extractor.process_batch(session, limit=args.limit)

        out = asyncio.run(_extract())
        logger.info("extract_done", **out)
    elif args.command == "seed":
        from scripts.seed_data import main as seed_main

        asyncio.run(seed_main())


if __name__ == "__main__":
    main()
