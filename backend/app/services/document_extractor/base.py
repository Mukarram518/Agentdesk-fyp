"""Base types and exceptions for AgentDesk document text extraction."""

from dataclasses import dataclass
from typing import Optional, Tuple

from app.core.exceptions import AgentDeskException


# =====================================================================
# Domain Exceptions
# =====================================================================

class DocumentExtractionError(ValueError, AgentDeskException):
    """Base exception for all document text extraction errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class EmptyDocumentError(DocumentExtractionError):
    """Raised when an uploaded document contains no pages, sections, or content blocks."""


class NoExtractableTextError(DocumentExtractionError):
    """Raised when document structure exists but yields no machine-readable text characters.

    Covers image-only/scanned documents, blank pages, and unsupported embedded font encodings.
    """


class CorruptedDocumentError(DocumentExtractionError):
    """Raised when document bytes are truncated, password-protected, encrypted, or malformed."""


class UnsupportedDocumentTypeError(DocumentExtractionError):
    """Raised when attempting extraction on a file type other than 'pdf' or 'docx'."""


# =====================================================================
# Extracted Document Data Structures
# =====================================================================

@dataclass(frozen=True)
class ExtractedPage:
    """Represents text extracted from a single document page or logical block.

    Attributes:
        page_number: 1-indexed page number for page-aware formats (PDF),
                     or None for formats lacking fixed physical pagination (DOCX).
        text: Normalized, non-empty text content of the page.
    """

    page_number: Optional[int]
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    """Immutable result of document text extraction.

    Attributes:
        full_text: Complete normalized document text.
        pages: Immutable tuple of ExtractedPage items.
        total_pages: Total physical page count (e.g. for PDF) or None (for DOCX).
        has_tables: True if one or more tables were detected and extracted.
    """

    full_text: str
    pages: Tuple[ExtractedPage, ...]
    total_pages: Optional[int]
    has_tables: bool = False

