"""Celery tasks for market data pipeline — nightly skill snapshots."""
import asyncio

from app.core.logging import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)

_ALL_ROLES = [
    "ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer",
    "backend_engineer", "frontend_engineer", "devops_engineer", "data_scientist",
]


@celery_app.task(name="app.worker.tasks.market.snapshot_all_roles", bind=True, max_retries=3)
def snapshot_all_roles(self):
    """Fetch live skill data for all roles and persist daily snapshots to DB.

    Runs nightly at 2 AM ART via Celery Beat. Uses asyncio.run to call the
    async market pipeline within the sync Celery task context.
    """
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from app.api.routes.market import _CACHE, save_skill_snapshot
        from app.core.config import settings

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        # Clear in-memory cache so we fetch fresh data tonight
        _CACHE.clear()

        results = []
        async with Session() as db:
            for role in _ALL_ROLES:
                try:
                    await save_skill_snapshot(role, db)
                    results.append({"role": role, "status": "ok"})
                    logger.info("market_snapshot_saved", role=role)
                except Exception as exc:
                    results.append({"role": role, "status": "error", "error": str(exc)})
                    logger.error("market_snapshot_failed", role=role, error=str(exc))

        await engine.dispose()
        return results

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("snapshot_all_roles_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300) from exc
