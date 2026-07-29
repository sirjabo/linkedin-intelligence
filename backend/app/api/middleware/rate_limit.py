"""Rate limiting middleware using Redis — 30/min anonymous, 60/min authenticated."""

from __future__ import annotations

import time

from fastapi import Request, Response
from redis.asyncio import Redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Kept for SlowAPI compatibility / optional per-route use
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[],
    enabled=False,  # We use RateLimitMiddleware instead for auth-aware limits
)

ANON_LIMIT = 30
AUTH_LIMIT = 60
WINDOW_SECONDS = 60


def _client_key(request: Request) -> tuple[str, int]:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return f"rl:auth:{token[:48]}", AUTH_LIMIT
    return f"rl:ip:{get_remote_address(request)}", ANON_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding fixed-window rate limiter backed by Redis INCR."""

    def __init__(self, app, redis_url: str | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip health checks
        if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        key, limit = _client_key(request)
        window = int(time.time()) // WINDOW_SECONDS
        redis_key = f"{key}:{window}"

        try:
            redis = await self._get_redis()
            count = await redis.incr(redis_key)
            if count == 1:
                await redis.expire(redis_key, WINDOW_SECONDS + 1)
            remaining = max(0, limit - count)
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
            }
            if count > limit:
                logger.warning("rate_limit_exceeded", key=key, count=count, limit=limit)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit superado: {limit} requests/min",
                            "docs_url": "https://docs.linkedin-intelligence.com/errors/RATE_LIMIT",
                        }
                    },
                    headers={**headers, "Retry-After": str(WINDOW_SECONDS)},
                )
            response = await call_next(request)
            for h, v in headers.items():
                response.headers[h] = v
            return response
        except Exception as exc:
            # Fail open if Redis is down — don't block API
            logger.warning("rate_limit_redis_failed", error=str(exc))
            return await call_next(request)
