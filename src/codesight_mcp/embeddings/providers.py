"""Embedding providers for semantic code search.

fastembed downloads ONNX model assets (~100 MB) on first use.
This is opt-in via ``pip install codesight-mcp[semantic]``.

Phase 3 will add Anthropic and OpenAI providers — see TODO markers below.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding provider backed by fastembed (ONNX runtime).

    Downloads model assets (~100 MB) on first instantiation if not cached.
    """

    def __init__(self, model: str = "BAAI/bge-base-en-v1.5") -> None:
        self._model_name = model
        try:
            from fastembed import TextEmbedding  # noqa: WPS433
        except ImportError as exc:
            raise ImportError(
                "Semantic search requires fastembed. Install with: pip install codesight-mcp[semantic]"
            ) from exc

        self._model = TextEmbedding(model_name=model)

        # Eager dimension probe — embed a single token to determine vector size
        probe = list(self._model.embed(["_"]))
        self._dimensions: int = len(probe[0])

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using the local ONNX model."""
        if not texts:
            return []
        return [[float(x) for x in v] for v in self._model.embed(texts)]

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions


# TODO(Phase 3): AnthropicEmbeddingProvider — uses Anthropic Voyager models
# TODO(Phase 3): OpenAIEmbeddingProvider — uses OpenAI text-embedding models

_NOT_IMPLEMENTED_PROVIDERS = {"anthropic", "openai"}


def get_embedding_provider_or_reason() -> tuple[EmbeddingProvider | None, str]:
    """Like get_embedding_provider but returns (provider, reason) tuple.

    Reasons: "ok", "disabled", "not_implemented:<name>", "not_installed", "unknown:<name>"
    """
    if os.environ.get("CODESIGHT_NO_SEMANTIC") == "1":
        return None, "disabled"

    model = os.environ.get("CODESIGHT_EMBED_MODEL")
    explicit_provider = os.environ.get("CODESIGHT_EMBED_PROVIDER")

    if explicit_provider is not None:
        if explicit_provider in _NOT_IMPLEMENTED_PROVIDERS:
            logger.info(
                "Embedding provider %r is not yet implemented — use 'local' or omit CODESIGHT_EMBED_PROVIDER",
                explicit_provider,
            )
            return None, f"not_implemented:{explicit_provider}"
        if explicit_provider == "local":
            p = _try_local_provider(model)
            return (p, "ok") if p else (None, "not_installed")
        logger.warning("Unknown embedding provider %r — semantic search unavailable", explicit_provider)
        return None, f"unknown:{explicit_provider}"

    # Auto-detect: try fastembed first
    p = _try_local_provider(model)
    return (p, "ok") if p else (None, "not_installed")


def get_embedding_provider() -> EmbeddingProvider | None:
    """Create an embedding provider based on environment configuration.

    Returns ``None`` when semantic search is disabled or no provider is available.

    Environment variables
    ---------------------
    CODESIGHT_NO_SEMANTIC : str
        Set to ``1`` to disable semantic search entirely.
    CODESIGHT_EMBED_PROVIDER : str
        Explicit provider selection (``"local"``).  Unknown values return ``None``.
    CODESIGHT_EMBED_MODEL : str
        Override the default model for the selected provider.
    """
    provider, _ = get_embedding_provider_or_reason()
    return provider


def _try_local_provider(model: str | None) -> LocalEmbeddingProvider | None:
    """Attempt to create a LocalEmbeddingProvider, returning None on ImportError."""
    try:
        if model:
            return LocalEmbeddingProvider(model=model)
        return LocalEmbeddingProvider()
    except ImportError:
        logger.debug("fastembed not installed — semantic search unavailable")
        return None
