"""Embedding providers package."""

import os
from typing import Dict, Optional

from app.providers.embeddings.base import (
    EmbeddingProvider,
    PREFIX_PASSAGE,
    PREFIX_QUERY,
)
from app.providers.embeddings.mock import MockEmbeddingProvider, MOCK_EMBEDDING_DIMENSION
from app.providers.embeddings.local import (
    LocalSentenceTransformerProvider,
    DEFAULT_MODEL_NAME,
    EXPECTED_EMBEDDING_DIMENSION,
)

__all__ = [
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    "LocalSentenceTransformerProvider",
    "MOCK_EMBEDDING_DIMENSION",
    "DEFAULT_MODEL_NAME",
    "EXPECTED_EMBEDDING_DIMENSION",
    "PREFIX_PASSAGE",
    "PREFIX_QUERY",
    "get_embedding_provider",
    "clear_embedding_provider_cache",
]

_PROVIDER_CACHE: Dict[str, EmbeddingProvider] = {}


def get_embedding_provider(
    provider_type: Optional[str] = None,
    *,
    force_reload: bool = False,
) -> EmbeddingProvider:
    """Factory returning the configured embedding provider with process-level singleton caching.

    Defaults to MockEmbeddingProvider in testing environments or when explicitly requested.
    Uses LocalSentenceTransformerProvider for production/development local inference.
    Reuses instances to avoid loading multiple redundant copies of model weights into memory.
    """
    is_testing = os.getenv("ENVIRONMENT") == "testing"
    selected_type = (provider_type or ("mock" if is_testing else "local")).lower().strip()

    if not force_reload and selected_type in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[selected_type]

    if selected_type == "mock":
        provider: EmbeddingProvider = MockEmbeddingProvider()
    elif selected_type == "local":
        provider = LocalSentenceTransformerProvider()
    else:
        raise ValueError(
            f"Unsupported embedding provider type '{provider_type}'. "
            "Supported types are 'mock' and 'local'."
        )

    _PROVIDER_CACHE[selected_type] = provider
    return provider


def clear_embedding_provider_cache() -> None:
    """Clears the provider cache (useful for isolating unit tests)."""
    _PROVIDER_CACHE.clear()
