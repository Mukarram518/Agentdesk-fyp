"""Document chunking package for AgentDesk knowledge base files."""

from typing import Optional
import uuid

from app.services.document_extractor.base import ExtractedDocument
from app.services.document_chunker.base import (
    ChunkingError,
    ChunkingResult,
    DocumentChunk,
    TokenLimitExceededError,
    TokenizerError,
)
from app.services.document_chunker.language import detect_content_language
from app.services.document_chunker.orchestrator import DocumentChunker
from app.services.document_chunker.splitter import split_text_into_atomic_units
from app.services.document_chunker.tokenizer import (
    E5TokenizerAdapter,
    MockTokenizer,
    Tokenizer,
    clear_e5_tokenizer_cache,
    get_e5_tokenizer,
)

__all__ = [
    "DocumentChunk",
    "ChunkingResult",
    "ChunkingError",
    "TokenLimitExceededError",
    "TokenizerError",
    "Tokenizer",
    "MockTokenizer",
    "E5TokenizerAdapter",
    "get_e5_tokenizer",
    "clear_e5_tokenizer_cache",
    "DocumentChunker",
    "detect_content_language",
    "split_text_into_atomic_units",
    "chunk_document",
]


def chunk_document(
    document: ExtractedDocument,
    source_file_id: uuid.UUID,
    tokenizer: Optional[Tokenizer] = None,
    target_chunk_tokens: int = 400,
    max_payload_tokens: int = 450,
    hard_prefixed_limit: int = 480,
    target_overlap_tokens: int = 60,
) -> ChunkingResult:
    """Convenience entry point for chunking an ExtractedDocument.

    Defaults to deterministic MockTokenizer when no tokenizer is supplied.
    """
    tok = tokenizer or MockTokenizer()
    chunker = DocumentChunker(
        tokenizer=tok,
        target_chunk_tokens=target_chunk_tokens,
        max_payload_tokens=max_payload_tokens,
        hard_prefixed_limit=hard_prefixed_limit,
        target_overlap_tokens=target_overlap_tokens,
    )
    return chunker.chunk_document(document=document, source_file_id=source_file_id)

