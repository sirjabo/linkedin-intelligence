"""LRU in-memory cache for expensive LLM calls.

Caches by a deterministic key derived from (operation, input_hash).
TTL is enforced per-entry. Thread-safe via asyncio (single-event-loop assumption).

Usage:
    from app.services.ai.cache import llm_cache

    cached = await llm_cache.get("jd_parse", jd_text)
    if cached is not None:
        return cached
    result = await expensive_llm_call(jd_text)
    await llm_cache.set("jd_parse", jd_text, result)
    return result
"""
import hashlib
import time
from collections import OrderedDict
from typing import Any


class LRUCache:
    """Async-safe LRU cache with per-entry TTL."""

    def __init__(self, max_size: int = 512, default_ttl: int = 3600) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        # OrderedDict preserves insertion order for LRU eviction
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def _make_key(self, namespace: str, *parts: str) -> str:
        combined = namespace + ":" + ":".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def get(self, namespace: str, *content_parts: str) -> Any | None:
        """Return cached value or None if missing/expired."""
        key = self._make_key(namespace, *content_parts)
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        # Move to end (most recently used)
        self._store.move_to_end(key)
        return value

    def set(self, namespace: str, *content_parts_and_value: Any, ttl: int | None = None) -> None:
        """Cache a value. content_parts are all args except the last; last arg is the value."""
        *content_parts, value = content_parts_and_value
        key = self._make_key(namespace, *[str(p) for p in content_parts])
        expires_at = time.monotonic() + (ttl or self._default_ttl)
        self._store[key] = (value, expires_at)
        self._store.move_to_end(key)
        # Evict oldest entries if over capacity
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def invalidate(self, namespace: str, *content_parts: str) -> None:
        key = self._make_key(namespace, *content_parts)
        self._store.pop(key, None)

    def clear_namespace(self, namespace: str) -> int:
        prefix = hashlib.sha256(namespace.encode()).hexdigest()[:8]
        to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in to_delete:
            del self._store[k]
        return len(to_delete)

    @property
    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict[str, int]:
        now = time.monotonic()
        expired = sum(1 for _, (_, exp) in self._store.items() if exp < now)
        return {"total": len(self._store), "expired": expired, "active": len(self._store) - expired}


# Singleton — import this everywhere
llm_cache = LRUCache(max_size=512, default_ttl=3600)
