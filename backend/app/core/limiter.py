"""Rate limiter singleton — shared across all routes.

Uses Redis as storage backend so rate limits are global across all workers.
Falls back to in-memory if REDIS_URL is not set (local dev only).
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_redis_url = os.environ.get("REDIS_URL", "")
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_redis_url or "memory://",
)
