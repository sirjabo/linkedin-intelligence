"""Embedding provider abstraction — generates dense vector representations of text.

Provider selection (auto-detected from env):
  OPENAI_API_KEY set → OpenAIEmbeddingProvider (text-embedding-3-small, 1536 dims)
  else               → NullEmbeddingProvider  (returns None — semantic scoring skipped)

Inject MockEmbeddingProvider in tests for deterministic behaviour without API calls.
"""
import hashlib
import math
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def dim(self) -> int: ...

    async def embed(self, texts: list[str]) -> list[list[float]] | None: ...


class NullEmbeddingProvider:
    """Used when no embedding API key is configured. Semantic scoring is disabled."""

    @property
    def dim(self) -> int:
        return 0

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        return None


class MockEmbeddingProvider:
    """Deterministic fake embeddings derived from content hash. For tests only."""

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            raw = [(b / 255.0) * 2 - 1 for b in digest[: self._dim]]
            norm = math.sqrt(sum(v * v for v in raw)) or 1.0
            result.append([v / norm for v in raw])
        return result


class OpenAIEmbeddingProvider:
    """OpenAI text-embedding-3-small (1536 dims). Requires openai>=1.0.0."""

    MODEL = "text-embedding-3-small"
    DIM = 1536

    def __init__(self, api_key: str) -> None:
        import openai  # lazy import — only required when key is set

        self._client = openai.AsyncOpenAI(api_key=api_key)

    @property
    def dim(self) -> int:
        return self.DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        truncated = [t[:8000] for t in texts]
        resp = await self._client.embeddings.create(model=self.MODEL, input=truncated)
        return [item.embedding for item in resp.data]


def get_embedding_provider() -> EmbeddingProvider:
    """Return the best available provider based on env config."""
    from app.core.config import settings  # local import avoids circular at module load

    if settings.OPENAI_API_KEY:
        return OpenAIEmbeddingProvider(settings.OPENAI_API_KEY)
    return NullEmbeddingProvider()


_default_provider: EmbeddingProvider | None = None


def default_embedding_provider() -> EmbeddingProvider:
    """Lazy singleton — reuses one provider instance per process."""
    global _default_provider
    if _default_provider is None:
        _default_provider = get_embedding_provider()
    return _default_provider
