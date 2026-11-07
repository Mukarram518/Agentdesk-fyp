"""Domain models and exceptions for AgentDesk document chunking."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import uuid

from app.core.exceptions import AgentDeskException
from app.models.knowledge import KnowledgeLanguage, KnowledgeSourceType


class ChunkingError(AgentDeskException):
    """Base exception for document chunking errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TokenLimitExceededError(ChunkingError):
    """Raised when an un-splittable text unit exceeds the allowable token budget."""


class TokenizerError(ChunkingError):
    """Raised when tokenization fails or tokenizer assets cannot be loaded."""


@dataclass(frozen=True)
class DocumentChunk:
    """Immutable representation of a single extracted document chunk.

    Attributes:
        source_file_id: UUID of the parent KnowledgeFile.
        chunk_index: Contiguous, 0-based integer across the document.
        text: Normalized chunk payload text (persisted to KnowledgeBaseEntry.answer).
        token_count: Raw payload token count (without prefix or special tokens).
        prefixed_token_count: Exact token count including 'passage: ' and <s>, </s>.
        page_number: 1-indexed page number for PDF, or None for DOCX.
        section_title: Detected section heading or None.
        language: Strictly 'en', 'ur', or 'mixed' (satisfies DB CheckConstraint).
    """

    source_file_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int
    prefixed_token_count: int
    page_number: Optional[int]
    section_title: Optional[str]
    language: str

    def to_repository_dict(self) -> Dict[str, Any]:
        """Converts chunk to a dict matching KnowledgeRepository.create_chunks_batch().

        Guarantees:
        - Exact contract alignment with KnowledgeRepository.create_chunks_batch().
        - Sets source_type='document_chunk'.
        - Sets question=None.
        - Sets tags=[].
        - Sets embedding=None and embedding_stale=True (pending worker generation).
        """
        return {
            "source_file_id": self.source_file_id,
            "chunk_index": self.chunk_index,
            "answer": self.text,
            "question": None,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "tags": [],
            "language": self.language,
            "source_type": KnowledgeSourceType.DOCUMENT_CHUNK.value,
            "embedding": None,
            "embedding_stale": True,
            "embedding_model": None,
        }


@dataclass(frozen=True)
class ChunkingResult:
    """Immutable aggregate output of document chunking.

    Attributes:
        source_file_id: UUID of the processed KnowledgeFile.
        chunks: Ordered tuple of DocumentChunk entities.
        total_chunks: Total number of generated chunks.
        total_tokens: Sum of raw payload tokens across all chunks.
        document_language: Predominant language across the entire document ('en', 'ur', or 'mixed').
    """

    source_file_id: uuid.UUID
    chunks: Tuple[DocumentChunk, ...]
    total_chunks: int
    total_tokens: int
    document_language: str

