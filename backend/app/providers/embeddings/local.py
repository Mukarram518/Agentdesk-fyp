"""Local SentenceTransformers embedding provider adapter for multilingual MiniLM."""

from typing import Any, List, Optional

from app.providers.embeddings.base import EmbeddingProvider

DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EXPECTED_EMBEDDING_DIMENSION = 384


class LocalSentenceTransformerProvider(EmbeddingProvider):
    """Local embedding provider using the sentence-transformers library.

    Guarantees:
    - Lazy loading: Does not import or instantiate model weights at module import time.
    - Provider abstraction: Conforms to the standard EmbeddingProvider interface.
    - Strict validation: Verifies output vectors match the expected 384 dimensions.
    - Normalized embeddings: Requests unit-normalized embeddings from the underlying model.
    - Clean dependency errors: Provides actionable error messages if sentence-transformers is missing.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model_instance: Optional[Any] = None,
    ) -> None:
        self._model_name = model_name
        self._dimension = EXPECTED_EMBEDDING_DIMENSION
        # Allows injecting a pre-instantiated or mocked model instance (ideal for offline tests)
        self._model = model_instance

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

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
                self._model = SentenceTransformer(self._model_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load sentence-transformers model '{self._model_name}': {exc}"
                ) from exc

        return self._model

    async def embed_text(self, text: str) -> List[float]:
        """Generates a 384-dimensional normalized embedding for a single text string."""
        sanitized = self.validate_text(text)
        model = self._get_model()

        try:
            raw_embedding = model.encode(sanitized, normalize_embeddings=True)
        except Exception as exc:
            raise RuntimeError(f"Model encoding failed: {exc}") from exc

        # Convert numpy array or tensor to standard Python float list
        vector: List[float] = (
            raw_embedding.tolist() if hasattr(raw_embedding, "tolist") else list(raw_embedding)
        )

        if len(vector) != self._dimension:
            raise ValueError(
                f"Model output dimension mismatch: expected {self._dimension}, got {len(vector)}."
            )

        return vector

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates 384-dimensional normalized embeddings for a batch of text strings."""
        if texts is None or not isinstance(texts, list):
            raise ValueError("Batch input must be a list of strings.")
        if not texts:
            return []

        sanitized_list = self.validate_batch(texts)
        model = self._get_model()

        try:
            raw_embeddings = model.encode(sanitized_list, normalize_embeddings=True)
        except Exception as exc:
            raise RuntimeError(f"Batch model encoding failed: {exc}") from exc

        results: List[List[float]] = []
        for raw in raw_embeddings:
            vec: List[float] = raw.tolist() if hasattr(raw, "tolist") else list(raw)
            if len(vec) != self._dimension:
                raise ValueError(
                    f"Model output dimension mismatch: expected {self._dimension}, got {len(vec)}."
                )
            results.append(vec)

        return results

