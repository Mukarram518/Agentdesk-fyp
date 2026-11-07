"""PDF text extraction service using pypdf for in-memory, page-aware text processing."""

import io
from typing import List

import pypdf
from pypdf.errors import FileNotDecryptedError, PdfReadError

from app.services.document_extractor.base import (
    CorruptedDocumentError,
    EmptyDocumentError,
    ExtractedDocument,
    ExtractedPage,
    NoExtractableTextError,
)
from app.services.document_extractor.normalizer import normalize_extracted_text


def extract_text_from_pdf(data: bytes) -> ExtractedDocument:
    """Extracts text page-by-page from raw PDF bytes without writing to disk.

    Guarantees:
    - Entire extraction takes place in-memory via io.BytesIO.
    - Preserves 1-based page numbers for each page containing readable text.
    - Preserves paragraph structure and normalizes text via Unicode NFC.
    - Rejects password-protected / encrypted PDFs with CorruptedDocumentError.
    - Rejects corrupted or truncated PDFs with CorruptedDocumentError.
    - Rejects zero-page PDFs with EmptyDocumentError.
    - Rejects PDFs yielding zero extractable text with NoExtractableTextError.
    - Does not expose raw internal library exceptions or file contents.

    Args:
        data: Raw PDF file bytes.

    Returns:
        ExtractedDocument containing normalized page text and metadata.

    Raises:
        EmptyDocumentError: If the document contains zero pages.
        NoExtractableTextError: If pages contain no readable text (e.g. image-only/blank).
        CorruptedDocumentError: If document is password-protected, encrypted, or corrupted.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise CorruptedDocumentError("PDF extraction input must be bytes.")

    if len(data) == 0:
        raise EmptyDocumentError("PDF file is empty (0 bytes).")

    stream = io.BytesIO(data)

    try:
        reader = pypdf.PdfReader(stream)
    except (PdfReadError, ValueError, EOFError, IndexError, KeyError, TypeError) as e:
        raise CorruptedDocumentError("PDF document is corrupted, truncated, or malformed.") from None
    except Exception:
        raise CorruptedDocumentError("Failed to parse PDF document.") from None

    # Check encryption / password protection
    if reader.is_encrypted:
        try:
            # Attempt blank password in case document only has empty user password
            status = reader.decrypt("")
            if status == pypdf.PasswordType.NOT_DECRYPTED or status == 0 or reader.is_encrypted:
                raise CorruptedDocumentError("PDF document is password-protected or encrypted and cannot be extracted.")
        except FileNotDecryptedError:
            raise CorruptedDocumentError("PDF document is password-protected or encrypted and cannot be extracted.") from None
        except CorruptedDocumentError:
            raise
        except Exception:
            raise CorruptedDocumentError("PDF document is encrypted or password-protected.") from None

    # Validate page count
    try:
        total_pages = len(reader.pages)
    except Exception:
        raise CorruptedDocumentError("PDF page directory is corrupted or unreadable.") from None

    if total_pages == 0:
        raise EmptyDocumentError("PDF document contains no pages.")

    # Extract text page by page
    extracted_pages: List[ExtractedPage] = []
    has_any_text = False

    for idx, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except FileNotDecryptedError:
            raise CorruptedDocumentError("PDF page content is encrypted and cannot be extracted.") from None
        except Exception:
            raise CorruptedDocumentError("PDF page content is corrupted or unreadable.") from None

        norm_text = normalize_extracted_text(raw_text)
        if norm_text:
            has_any_text = True
            extracted_pages.append(ExtractedPage(page_number=idx, text=norm_text))

    if not has_any_text or not extracted_pages:
        raise NoExtractableTextError(
            "PDF contains no extractable text. The document may be blank, scanned, image-only, "
            "or use unsupported font encoding."
        )

    full_text = "\n\n".join(p.text for p in extracted_pages)

    return ExtractedDocument(
        full_text=full_text,
        pages=tuple(extracted_pages),
        total_pages=total_pages,
        has_tables=False,
    )
