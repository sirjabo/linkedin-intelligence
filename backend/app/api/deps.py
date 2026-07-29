"""FastAPI dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal

_redis: Redis | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def get_optional_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    """Return token string if Authorization Bearer present; else None."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Stub auth dependency — JWT validation lands in a later sprint."""
    token = await get_optional_auth(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Se requiere autenticación Bearer",
            },
        )
    return {"token": token, "plan": "free"}


DbSession = Annotated[AsyncSession, Depends(get_db)]
OptionalAuth = Annotated[str | None, Depends(get_optional_auth)]
