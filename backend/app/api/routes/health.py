"""Health check endpoint — brief verification: {"status": "ok"}."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.job_posting import JobPosting
from app.db.session import AsyncSessionLocal

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Always return the MVP contract. Side checks are logged, never blocking."""
    await _check_db()
    await _check_redis()
    return {"status": "ok"}


async def _check_db() -> bool:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            await _check_data_freshness(db)
        return True
    except Exception as exc:
        logger.warning("health_db_failed", error=str(exc))
        return False


async def _check_redis() -> bool:
    if settings.REDIS_URL.startswith("memory://"):
        return True
    try:
        redis = await get_redis()
        pong = await redis.ping()
        return bool(pong)
    except Exception as exc:
        logger.warning("health_redis_failed", error=str(exc))
        return False


async def _check_data_freshness(db: AsyncSession) -> bool:
    try:
        threshold = datetime.now(UTC) - timedelta(hours=settings.DATA_FRESHNESS_HOURS)
        result = await db.execute(select(func.max(JobPosting.crawled_at)))
        latest = result.scalar_one_or_none()
        if latest is None:
            return False
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        return latest >= threshold
    except Exception as exc:
        logger.warning("health_freshness_failed", error=str(exc))
        return False
