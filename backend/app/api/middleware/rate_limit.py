"""Rate limiting helpers — SlowAPI limiter lives on analyze router."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Shared limiter instance (analyze routes attach their own; this keeps imports stable)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[],
)
