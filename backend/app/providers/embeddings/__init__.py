"""Embedding providers package."""

import os
from typing import Optional

from app.providers.embeddings.base import EmbeddingProvider
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
    "get_embedding_provider",
]


def get_embedding_provider(provider_type: Optional[str] = None) -> EmbeddingProvider:
    """Factory returning the configured embedding provider.

    Defaults to MockEmbeddingProvider in testing environments or when explicitly requested.
    Uses LocalSentenceTransformerProvider for production/development local inference.
    """
    is_testing = os.getenv("ENVIRONMENT") == "testing"
    selected_type = (provider_type or ("mock" if is_testing else "local")).lower().strip()

    if selected_type == "mock":
        return MockEmbeddingProvider()
    elif selected_type == "local":
        return LocalSentenceTransformerProvider()
    else:
        raise ValueError(
            f"Unsupported embedding provider type '{provider_type}'. "
            "Supported types are 'mock' and 'local'."
        )

