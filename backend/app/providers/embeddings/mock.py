"""Deterministic Mock Embedding Provider for automated testing and CI."""

import hashlib
import math
from typing import List

from app.providers.embeddings.base import EmbeddingProvider

# Expected schema vector dimension for sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
MOCK_EMBEDDING_DIMENSION = 384


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock embedding provider for tests and development.

    Guarantees:
    - Never requires external network access, paid APIs, or downloaded weights.
    - Always produces normalized 384-dimensional dense vectors.
    - Strictly deterministic: identical input string always returns the exact same vector.
    - Distinct inputs produce distinct deterministic vectors.
    - Note: Mock vectors are structurally valid and normalized for pgvector testing,
      but are not semantically meaningful.
    """

    def __init__(self, dimension: int = MOCK_EMBEDDING_DIMENSION) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

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

    async def embed_text(self, text: str) -> List[float]:
        """Generates a deterministic 384-dimensional unit vector for text."""
        sanitized = self.validate_text(text)
        return self._generate_vector(sanitized)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates deterministic 384-dimensional unit vectors for a list of texts."""
        if texts is None or not isinstance(texts, list):
            raise ValueError("Batch input must be a list of strings.")
        if not texts:
            return []

        sanitized_list = [self.validate_text(t) for t in texts]
        return [self._generate_vector(t) for t in sanitized_list]

