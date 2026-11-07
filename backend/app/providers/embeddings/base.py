"""Abstract interface for vector embedding providers in AgentDesk."""

from abc import ABC, abstractmethod
from typing import List, Optional

PREFIX_PASSAGE = "passage: "
PREFIX_QUERY = "query: "


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

    @property
    def model_name(self) -> str:
        """Name or identifier of the active embedding model."""
        return "unknown"

    @abstractmethod
    async def embed_text(
        self,
        text: str,
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[float]:
        """Generates a normalized embedding vector for a single text string.

        Args:
            text: Non-empty string to encode into a vector.
            prefix: Optional explicit task prefix ('passage: ', 'query: ', or custom).
            is_query: If True and prefix is None, applies 'query: ' prefix.
                      Defaults to 'passage: ' when prefix is None and is_query is False.

        Returns:
            A list of floats representing the dense embedding vector of length `self.dimension`.

        Raises:
            ValueError: If the text is empty, whitespace-only, or not a string.
            RuntimeError: If model loading or vector computation fails.
        """
        pass

    @abstractmethod
    async def embed_batch(
        self,
        texts: List[str],
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[List[float]]:
        """Generates normalized embedding vectors for a batch of text strings.

        Args:
            texts: List of non-empty strings to encode.
            prefix: Optional explicit task prefix ('passage: ', 'query: ', or custom).
            is_query: If True and prefix is None, applies 'query: ' prefix.
                      Defaults to 'passage: ' when prefix is None and is_query is False.

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

    def format_prefixed_text(
        self,
        text: str,
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> str:
        """Applies task prefixing ('passage: ' or 'query: ') to text.

        Guarantees:
        - If text is already prefixed with 'passage: ' or 'query: ', avoids double-prefixing.
        - If prefix is explicitly specified as empty string (''), returns stripped text.
        - If prefix is explicitly provided, prepends that prefix.
        - If prefix is None and is_query is True, prepends 'query: '.
        - If prefix is None and is_query is False, prepends 'passage: '.
        """
        stripped = self.validate_text(text)
        if stripped.startswith((PREFIX_PASSAGE, PREFIX_QUERY)):
            return stripped
        if prefix is not None:
            return f"{prefix}{stripped}"
        if is_query:
            return f"{PREFIX_QUERY}{stripped}"
        return f"{PREFIX_PASSAGE}{stripped}"

    def format_prefixed_batch(
        self,
        texts: List[str],
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[str]:
        """Applies task prefixing across a list of text strings."""
        if texts is None or not isinstance(texts, list):
            raise ValueError("Batch input must be a list of strings.")
        return [
            self.format_prefixed_text(t, prefix=prefix, is_query=is_query)
            for t in texts
        ]
