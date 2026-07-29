"""Base crawler with rate limiting, retries, and structured results."""

from __future__ import annotations

import random
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.crawler.config import USER_AGENT

logger = get_logger(__name__)


@dataclass
class CrawlResult:
    source: str
    run_id: str
    items_found: int
    items_new: int
    items_duplicated: int
    errors: int
    duration_seconds: float


class BaseCrawler(ABC):
    def __init__(self, rate_limit_rps: float = 0.5, timeout: float = 30.0) -> None:
        self.rate_limit_rps = rate_limit_rps
        self._last_request_time = 0.0
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"},
            follow_redirects=True,
        )
        self.run_id = str(uuid.uuid4())

    def _wait_rate_limit(self) -> None:
        min_interval = 1.0 / self.rate_limit_rps if self.rate_limit_rps > 0 else 0
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed + random.uniform(0, 0.5)
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        self._wait_rate_limit()
        response = self.client.get(url, **kwargs)
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "10"))
            logger.warning("crawler_rate_limited", url=url, retry_after=retry_after)
            time.sleep(retry_after)
            response.raise_for_status()
        if response.status_code >= 500:
            response.raise_for_status()
        return response

    def close(self) -> None:
        self.client.close()

    @abstractmethod
    def crawl(self) -> CrawlResult:
        ...

    @abstractmethod
    def parse(self, raw: str) -> list[dict[str, Any]]:
        ...
