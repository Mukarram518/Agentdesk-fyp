"""Local SentenceTransformers embedding provider adapter for intfloat/multilingual-e5-small."""

import asyncio
import math
from typing import Any, List, Optional

from app.providers.embeddings.base import (
    EmbeddingProvider,
    PREFIX_PASSAGE,
    PREFIX_QUERY,
)

DEFAULT_MODEL_NAME = "intfloat/multilingual-e5-small"
EXPECTED_EMBEDDING_DIMENSION = 384


class LocalSentenceTransformerProvider(EmbeddingProvider):
    """Local embedding provider using the sentence-transformers library.

    Guarantees:
    - Lazy loading: Does not import or instantiate model weights at module import time.
    - Offline-first: Loads from local cache via local_files_only=True by default.
    - Non-blocking: Offloads CPU-bound inference to asyncio.to_thread().
    - Asymmetric prefixing: Supports 'passage: ' (default) and 'query: ' task prefixes.
    - Provider abstraction: Conforms to the standard EmbeddingProvider interface.
    - Strict validation: Verifies output vectors match 384 dimensions, are finite, and unit-normalized.
    - Clean dependency errors: Provides actionable error messages if sentence-transformers is missing.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model_instance: Optional[Any] = None,
        local_files_only: bool = True,
    ) -> None:
        self._model_name = model_name
        self._dimension = EXPECTED_EMBEDDING_DIMENSION
        # Allows injecting a pre-instantiated or mocked model instance (ideal for offline tests)
        self._model = model_instance
        self._local_files_only = local_files_only

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def local_files_only(self) -> bool:
        return self._local_files_only

    @property
    def is_loaded(self) -> bool:
        """Returns True if the underlying model has already been loaded into memory."""
        return self._model is not None

    def _get_model(self) -> Any:
        """Lazily imports and instantiates the SentenceTransformer model on first use."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except (ImportError, ModuleNotFoundError) as err:
                raise RuntimeError(
                    "The 'sentence-transformers' package is required for LocalSentenceTransformerProvider. "
                    "Please install it with 'pip install sentence-transformers'."
                ) from err

            try:
                self._model = SentenceTransformer(
                    self._model_name,
                    local_files_only=self._local_files_only,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load sentence-transformers model '{self._model_name}': {exc}"
                ) from exc

        return self._model

    def _validate_and_convert_vector(self, raw_embedding: Any) -> List[float]:
        """Validates vector dimensions, finite numeric values, and unit normalization."""
        vector: List[float] = (
            raw_embedding.tolist() if hasattr(raw_embedding, "tolist") else list(raw_embedding)
        )

        if len(vector) != self._dimension:
            raise ValueError(
                f"Model output dimension mismatch: expected {self._dimension}, got {len(vector)}."
            )

        norm_sq = 0.0
        for idx, val in enumerate(vector):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise ValueError(
                    f"Model output vector contains non-finite value at index {idx}: {val}."
                )
            norm_sq += float(val) * float(val)

        norm = math.sqrt(norm_sq)
        if abs(norm - 1.0) > 0.01:
            raise ValueError(
                f"Model output vector is not unit-normalized: norm is {norm:.6f}, expected 1.0."
            )

        return vector

    async def embed_text(
        self,
        text: str,
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[float]:
        """Generates a 384-dimensional normalized embedding for a single text string."""
        formatted_text = self.format_prefixed_text(text, prefix=prefix, is_query=is_query)
        model = self._get_model()

        try:
            raw_embedding = await asyncio.to_thread(
                model.encode,
                formatted_text,
                normalize_embeddings=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Model encoding failed: {exc}") from exc

        return self._validate_and_convert_vector(raw_embedding)

    async def embed_batch(
        self,
        texts: List[str],
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[List[float]]:
        """Generates 384-dimensional normalized embeddings for a batch of text strings."""
        if texts is None or not isinstance(texts, list):
            raise ValueError("Batch input must be a list of strings.")
        if not texts:
            return []

        formatted_list = self.format_prefixed_batch(texts, prefix=prefix, is_query=is_query)
        model = self._get_model()

        try:
            raw_embeddings = await asyncio.to_thread(
                model.encode,
                formatted_list,
                normalize_embeddings=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Batch model encoding failed: {exc}") from exc

        return [self._validate_and_convert_vector(raw) for raw in raw_embeddings]
