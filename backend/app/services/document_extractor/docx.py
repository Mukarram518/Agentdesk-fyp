"""DOCX text extraction service using python-docx for ordered paragraphs and tables."""

import io
from typing import List
import zipfile

import docx
from docx.opc.exceptions import OpcError, PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.services.document_extractor.base import (
    CorruptedDocumentError,
    EmptyDocumentError,
    ExtractedDocument,
    ExtractedPage,
    NoExtractableTextError,
)
from app.services.document_extractor.normalizer import normalize_extracted_text


def extract_text_from_docx(data: bytes) -> ExtractedDocument:
    """Extracts text, headings, and tables from raw DOCX bytes in document sequence.

    Guarantees:
    - Entire extraction takes place in-memory via io.BytesIO.
    - Preserves exact document order between paragraphs, headings, and tables by
      iterating underlying body elements.
    - Formats table rows with pipe delimiters (' | ').
    - Preserves full Unicode content (Urdu, English, mixed-language, punctuation).
    - Sets page numbers to None (as DOCX has no fixed physical pagination).
    - Rejects empty, corrupted, or unreadable archives with domain exceptions.
    - Does not extract images or attempt OCR.

    Args:
        data: Raw DOCX file bytes.

    Returns:
        ExtractedDocument containing normalized content and table metadata.

    Raises:
        EmptyDocumentError: If the document is 0 bytes or contains no body elements.
        NoExtractableTextError: If the document contains elements but zero readable text.
        CorruptedDocumentError: If the package is corrupted, truncated, or unreadable.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise CorruptedDocumentError("DOCX extraction input must be bytes.")

    if len(data) == 0:
        raise EmptyDocumentError("DOCX file is empty (0 bytes).")

    stream = io.BytesIO(data)

    try:
        doc = docx.Document(stream)
    except (PackageNotFoundError, OpcError, zipfile.BadZipFile, KeyError, ValueError, EOFError):
        raise CorruptedDocumentError("DOCX document package is corrupted or malformed.") from None
    except Exception:
        raise CorruptedDocumentError("Failed to parse DOCX document.") from None

    blocks: List[str] = []
    has_tables = False

    try:
        body_elements = doc.element.body
        if body_elements is None or len(body_elements) == 0:
            raise EmptyDocumentError("DOCX document contains no content elements.")

        for child in body_elements:
            # Check for paragraph element (<w:p>)
            if child.tag.endswith("p"):
                p = Paragraph(child, doc)
                norm_p = normalize_extracted_text(p.text)
                if norm_p:
                    blocks.append(norm_p)

            # Check for table element (<w:tbl>)
            elif child.tag.endswith("tbl"):
                tbl = Table(child, doc)
                table_rows: List[str] = []

                for row in tbl.rows:
                    row_cells = [normalize_extracted_text(cell.text) for cell in row.cells]
                    # Only include row if at least one cell has text
                    if any(row_cells):
                        table_rows.append(f"| {' | '.join(row_cells)} |")

                if table_rows:
                    has_tables = True
                    blocks.append("\n".join(table_rows))

    except (KeyError, IndexError, ValueError, TypeError) as e:
        raise CorruptedDocumentError("DOCX body structure is corrupted or unreadable.") from None

    if not blocks:
        raise NoExtractableTextError("DOCX document contains no extractable or readable text.")

    full_text = "\n\n".join(blocks)

    # DOCX does not have fixed physical pages; page_number is None
    page = ExtractedPage(page_number=None, text=full_text)

    return ExtractedDocument(
        full_text=full_text,
        pages=(page,),
        total_pages=None,
        has_tables=has_tables,
    )

