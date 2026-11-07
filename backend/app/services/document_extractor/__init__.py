"""Document text extraction package for AgentDesk knowledge files."""

from app.services.document_extractor.base import (
    CorruptedDocumentError,
    DocumentExtractionError,
    EmptyDocumentError,
    ExtractedDocument,
    ExtractedPage,
    NoExtractableTextError,
    UnsupportedDocumentTypeError,
)
from app.services.document_extractor.docx import extract_text_from_docx
from app.services.document_extractor.normalizer import normalize_extracted_text
from app.services.document_extractor.pdf import extract_text_from_pdf

__all__ = [
    "ExtractedPage",
    "ExtractedDocument",
    "DocumentExtractionError",
    "EmptyDocumentError",
    "NoExtractableTextError",
    "CorruptedDocumentError",
    "UnsupportedDocumentTypeError",
    "extract_document_text",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "normalize_extracted_text",
]

MAX_DOCUMENT_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB


def extract_document_text(
    data: bytes,
    file_type: str,
) -> ExtractedDocument:
    """Unified dispatcher for extracting text from raw document bytes.

    Guarantees:
    - In-memory execution directly from byte payload.
    - Rejects empty payloads and payloads exceeding the 5 MB limit.
    - Validates file type against approved types ('pdf', 'docx').
    - Dispatches to format-specific extractors with full Unicode and ordering guarantees.

    Args:
        data: Raw document byte stream.
        file_type: Document extension or format indicator (e.g. 'pdf', '.docx').

    Returns:
        ExtractedDocument containing normalized text and page/table metadata.

    Raises:
        EmptyDocumentError: If data is empty (0 bytes) or contains no document content.
        DocumentExtractionError: If file exceeds 5 MB limit.
        UnsupportedDocumentTypeError: If file_type is not 'pdf' or 'docx'.
        NoExtractableTextError: If document contains no readable text characters.
        CorruptedDocumentError: If document is malformed, truncated, or password-protected.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise DocumentExtractionError("Document data must be bytes or bytearray.")

    if len(data) == 0:
        raise EmptyDocumentError("Document data is empty (0 bytes).")

    if len(data) > MAX_DOCUMENT_SIZE_BYTES:
        raise DocumentExtractionError(
            f"Document size ({len(data)} bytes) exceeds maximum allowed limit of 5 MB ({MAX_DOCUMENT_SIZE_BYTES} bytes)."
        )

    if not isinstance(file_type, str) or not file_type.strip():
        raise UnsupportedDocumentTypeError(
            f"Unsupported document file type '{file_type}'. File type must be a non-empty string."
        )

    norm_type = file_type.lstrip(".").lower().strip()

    if norm_type == "pdf":
        return extract_text_from_pdf(data)
    elif norm_type == "docx":
        return extract_text_from_docx(data)
    else:
        raise UnsupportedDocumentTypeError(
            f"Unsupported document file type '{file_type}'. Supported types are 'pdf' and 'docx'."
        )
