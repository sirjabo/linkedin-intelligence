"""Health check endpoint — brief verification: {"status": "ok"}."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.job_posting import JobPosting

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Return {"status": "ok"} when DB and Redis are reachable."""
    db_ok = await _check_db(db)
    redis_ok = await _check_redis()

    if db_ok and redis_ok:
        # Touch data freshness for observability (non-blocking for status)
        await _check_data_freshness(db)
        return {"status": "ok"}

    logger.warning("health_degraded", database=db_ok, redis=redis_ok)
    return {"status": "error"}


async def _check_db(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("health_db_failed", error=str(exc))
        return False


async def _check_redis() -> bool:
    try:
        redis: Redis = await get_redis()
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
