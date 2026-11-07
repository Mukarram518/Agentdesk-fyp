"""Deterministic Mock Embedding Provider for automated testing and CI."""

import hashlib
import math
from typing import List, Optional

from app.providers.embeddings.base import EmbeddingProvider

# Expected schema vector dimension for intfloat/multilingual-e5-small
MOCK_EMBEDDING_DIMENSION = 384


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock embedding provider for tests and development.

    Guarantees:
    - Never requires external network access, paid APIs, or downloaded weights.
    - Always produces normalized 384-dimensional dense vectors.
    - Strictly deterministic: identical input string always returns the exact same vector.
    - Distinct inputs produce distinct deterministic vectors.
    - Supports E5 task prefixes ('passage: ' and 'query: ').
    - Note: Mock vectors are structurally valid and normalized for pgvector testing,
      but are not semantically meaningful.
    """

    def __init__(
        self,
        dimension: int = MOCK_EMBEDDING_DIMENSION,
        model_name: str = "intfloat/multilingual-e5-small",
    ) -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _generate_vector(self, text: str) -> List[float]:
        """Computes a deterministic, L2-normalized vector from text using SHA-256."""
        seed_hash = hashlib.sha256(text.encode("utf-8")).digest()
        raw_values: List[float] = []

        for i in range(self._dimension):
            # Deterministic combination of input hash and dimension index
            component_hash = hashlib.sha256(seed_hash + i.to_bytes(4, byteorder="big")).digest()
            int_val = int.from_bytes(component_hash[:4], byteorder="big", signed=True)
            raw_values.append(float(int_val))

        # L2-normalize to unit length
        norm = math.sqrt(sum(val * val for val in raw_values))
        if norm == 0.0:
            norm = 1.0

        return [round(val / norm, 7) for val in raw_values]

    async def embed_text(
        self,
        text: str,
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[float]:
        """Generates a deterministic 384-dimensional unit vector for text."""
        formatted = self.format_prefixed_text(text, prefix=prefix, is_query=is_query)
        return self._generate_vector(formatted)

    async def embed_batch(
        self,
        texts: List[str],
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[List[float]]:
        """Generates deterministic 384-dimensional unit vectors for a list of texts."""
        if texts is None or not isinstance(texts, list):
            raise ValueError("Batch input must be a list of strings.")
        if not texts:
            return []

        formatted_list = self.format_prefixed_batch(texts, prefix=prefix, is_query=is_query)
        return [self._generate_vector(t) for t in formatted_list]
