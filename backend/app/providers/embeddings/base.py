"""Abstract interface for vector embedding providers in AgentDesk."""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract base class for vector embedding providers.

    All embedding providers in AgentDesk must conform to this interface.
    This guarantees provider-independence across local models, mock testing providers,
    and any future inference adapters.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Output embedding vector dimensionality (384 for AgentDesk multilingual schema)."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generates a normalized embedding vector for a single text string.

        Args:
            text: Non-empty string to encode into a vector.

        Returns:
            A list of floats representing the dense embedding vector of length `self.dimension`.

        Raises:
            ValueError: If the text is empty, whitespace-only, or not a string.
            RuntimeError: If model loading or vector computation fails.
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates normalized embedding vectors for a batch of text strings.

        Args:
            texts: List of non-empty strings to encode.

        Returns:
            A list of dense embedding vectors, preserving the exact input order.
            Returns an empty list if `texts` is empty.

        Raises:
            ValueError: If `texts` is not a list, or any item in `texts` is empty or not a string.
            RuntimeError: If model loading or vector computation fails.
        """
        pass

    def validate_text(self, text: str) -> str:
        """Helper to validate and sanitize a single text input string.

        Args:
            text: Input string to validate.

        Returns:
            Stripped text string.

        Raises:
            ValueError: If text is None, not a string, or whitespace-only.
        """
        if text is None or not isinstance(text, str):
            raise ValueError("Text input must be a non-null string.")
        stripped = text.strip()
        if not stripped:
            raise ValueError("Text input cannot be empty or whitespace-only.")
        return stripped

    def validate_batch(self, texts: List[str]) -> List[str]:
        """Helper to validate and sanitize a batch of text input strings.

        Args:
            texts: List of strings to validate.

        Returns:
            List of stripped text strings.

        Raises:
            ValueError: If texts is None, not a list, or contains empty/invalid items.
        """
        if texts is None or not isinstance(texts, list):
            raise ValueError("Batch input must be a list of strings.")
        return [self.validate_text(t) for t in texts]

