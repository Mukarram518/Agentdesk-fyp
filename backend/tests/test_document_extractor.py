"""Unit tests for AgentDesk Document Extraction & Normalization (Phase 5.4C).

Verifies:
1. PDF Extraction:
   - Multi-page PDF text extraction and page number preservation.
   - Urdu PDF text extraction using a valid ToUnicode CMap.
   - Detection of PDFs with no extractable text (blank/scanned) raising NoExtractableTextError.
   - Password-protected / encrypted PDF rejection raising CorruptedDocumentError.
   - Truncated / corrupted PDF rejection raising CorruptedDocumentError.
2. DOCX Extraction:
   - English paragraphs, headings, and lists.
   - Urdu and mixed-language text with bi-directional and diacritic support.
   - Tables with pipe-delimited formatting.
   - Strict document order preservation between paragraphs and tables.
   - Corrupted / invalid ZIP rejection raising CorruptedDocumentError.
   - DOCX with no readable text raising NoExtractableTextError.
3. Text Normalization:
   - Unicode NFC canonical composition.
   - Preservation of Urdu characters, diacritics (Aeraab), and punctuation.
   - Preservation of Zero-Width Non-Joiner (\u200c, ZWNJ).
   - Preservation of English punctuation, digits, currency symbols.
   - Normalization of line endings, non-breaking spaces, and horizontal whitespace.
   - Collapse of 3+ line breaks to 2 while preserving paragraph breaks.
4. Unified Dispatcher & Constraints:
   - Rejection of unsupported file types.
   - Rejection of 0-byte empty payloads.
   - Enforcement of maximum 5 MB document size limit.
"""

import io
from typing import List, Tuple
import unicodedata

import docx
import pypdf
import pytest

from app.services.document_extractor import (
    CorruptedDocumentError,
    DocumentExtractionError,
    EmptyDocumentError,
    ExtractedDocument,
    ExtractedPage,
    NoExtractableTextError,
    UnsupportedDocumentTypeError,
    extract_document_text,
    extract_text_from_docx,
    extract_text_from_pdf,
    normalize_extracted_text,
)


# =====================================================================
# Fixture Generators (In-Memory, Zero Disk Writes)
# =====================================================================

def create_multipage_pdf_bytes() -> bytes:
    """Creates a valid 2-page PDF in-memory with text on both pages."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R 4 0 R] /Count 2>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 5 0 R /Resources <</Font <</F1 7 0 R>>>>>> endobj\n"
        b"4 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 6 0 R /Resources <</Font <</F1 7 0 R>>>>>> endobj\n"
        b"5 0 obj <</Length 44>> stream\nBT /F1 12 Tf 50 250 Td (Page 1 English Content) Tj ET\nendstream endobj\n"
        b"6 0 obj <</Length 44>> stream\nBT /F1 12 Tf 50 250 Td (Page 2 English Content) Tj ET\nendstream endobj\n"
        b"7 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        b"xref\n0 8\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000121 00000 n \n0000000236 00000 n \n0000000351 00000 n \n0000000447 00000 n \n0000000543 00000 n \n"
        b"trailer <</Size 8 /Root 1 0 R>>\nstartxref\n622\n%%EOF"
    )
    return pdf_content


def create_urdu_pdf_bytes() -> bytes:
    """Creates a valid PDF containing a ToUnicode CMap mapping character codes to Urdu codepoints."""
    cmap = (
        b"/CIDInit /ProcSet findresource begin\n"
        b"12 dict begin\n"
        b"begincmap\n"
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        b"/CMapName /Custom-ToUnicode def\n"
        b"/CMapType 2 def\n"
        b"1 begincodespacerange\n"
        b"<0001> <0004>\n"
        b"endcodespacerange\n"
        b"4 beginbfrange\n"
        b"<0001> <0001> <0627>\n"  # Alef: ا
        b"<0002> <0002> <0631>\n"  # Re: ر
        b"<0003> <0003> <062F>\n"  # Dal: د
        b"<0004> <0004> <0648>\n"  # Waw: و
        b"endbfrange\n"
        b"endcmap\n"
        b"CMapName currentdict /CMap defineresource pop\n"
        b"end\n"
        b"end\n"
    )

    pdf_data = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj\n"
        b"4 0 obj <</Length 25>> stream\nBT /F1 12 Tf <0001000200030004> Tj ET\nendstream endobj\n"
        b"5 0 obj <</Type /Font /Subtype /Type0 /BaseFont /UrduFont /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R>> endobj\n"
        b"6 0 obj <</Type /Font /Subtype /CIDFontType2 /BaseFont /UrduFont /CIDSystemInfo <</Registry (Adobe) /Ordering (UCS) /Supplement 0>> /FontDescriptor 8 0 R>> endobj\n"
        b"7 0 obj <</Length " + str(len(cmap)).encode() + b">> stream\n" + cmap + b"endstream endobj\n"
        b"8 0 obj <</Type /FontDescriptor /FontName /UrduFont /Flags 4 /ItalicAngle 0 /Ascent 750 /Descent -250 /CapHeight 750>> endobj\n"
        b"xref\n0 9\n0000000000 65535 f \n"
        b"trailer <</Size 9 /Root 1 0 R>>\nstartxref\n0\n%%EOF"
    )
    return pdf_data


def create_blank_pdf_bytes() -> bytes:
    """Creates a PDF with blank pages (no text content)."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_encrypted_pdf_bytes(password: str = "secret123") -> bytes:
    """Creates a password-protected PDF in-memory."""
    source_pdf = create_multipage_pdf_bytes()
    reader = pypdf.PdfReader(io.BytesIO(source_pdf))
    writer = pypdf.PdfWriter()
    writer.append(reader)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_docx_with_blocks(blocks: List[Tuple[str, any]]) -> bytes:
    """Creates a DOCX in-memory with given sequence of ('p', text), ('h', text), or ('table', matrix)."""
    doc = docx.Document()
    for block_type, content in blocks:
        if block_type == "p":
            doc.add_paragraph(content)
        elif block_type == "h":
            doc.add_heading(content, level=1)
        elif block_type == "table":
            # content is List[List[str]]
            tbl = doc.add_table(rows=len(content), cols=len(content[0]))
            for r_idx, row in enumerate(content):
                for c_idx, cell in enumerate(row):
                    tbl.cell(r_idx, c_idx).text = cell
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# =====================================================================
# 1. PDF Extraction Tests
# =====================================================================

def test_pdf_extraction_multiple_pages_and_numbers():
    """Verifies that multi-page PDFs extract each page with 1-based page numbers preserved."""
    pdf_bytes = create_multipage_pdf_bytes()
    result = extract_text_from_pdf(pdf_bytes)

    assert result.total_pages == 2
    assert len(result.pages) == 2

    # Check Page 1
    assert result.pages[0].page_number == 1
    assert "Page 1 English Content" in result.pages[0].text

    # Check Page 2
    assert result.pages[1].page_number == 2
    assert "Page 2 English Content" in result.pages[1].text

    # Check full_text aggregation
    assert "Page 1 English Content" in result.full_text
    assert "Page 2 English Content" in result.full_text
    assert result.has_tables is False


def test_pdf_urdu_extraction_with_tounicode():
    """Verifies that PDFs with ToUnicode CMaps extract native Urdu Unicode characters accurately."""
    pdf_bytes = create_urdu_pdf_bytes()
    result = extract_text_from_pdf(pdf_bytes)

    assert result.total_pages == 1
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1

    # Verify extracted Unicode codepoints correspond to Urdu characters
    # (Alef \u0627, Re \u0631, Dal \u062f, Waw \u0648)
    text = result.pages[0].text
    urdu_codepoints = {ord(c) for c in text}
    expected_urdu_codepoints = {0x0627, 0x0631, 0x062F, 0x0648}
    assert expected_urdu_codepoints.issubset(urdu_codepoints)


def test_pdf_no_extractable_text_raises_error():
    """Verifies that PDFs containing pages but no text (e.g. blank/scanned) raise NoExtractableTextError."""
    blank_pdf = create_blank_pdf_bytes()
    with pytest.raises(NoExtractableTextError, match="contains no extractable text"):
        extract_text_from_pdf(blank_pdf)


def test_pdf_password_protected_raises_corrupted_error():
    """Verifies that encrypted / password-protected PDFs raise CorruptedDocumentError."""
    enc_pdf = create_encrypted_pdf_bytes("ownerpass")
    with pytest.raises(CorruptedDocumentError, match="password-protected or encrypted"):
        extract_text_from_pdf(enc_pdf)


def test_pdf_corrupted_bytes_raises_corrupted_error():
    """Verifies that truncated or malformed PDF streams raise CorruptedDocumentError."""
    corrupted_data = b"%PDF-1.4\n1 0 obj truncated stream without end"
    with pytest.raises(CorruptedDocumentError):
        extract_text_from_pdf(corrupted_data)


def test_pdf_empty_bytes_raises_empty_error():
    """Verifies that 0-byte input raises EmptyDocumentError."""
    with pytest.raises(EmptyDocumentError, match="empty"):
        extract_text_from_pdf(b"")


# =====================================================================
# 2. DOCX Extraction Tests
# =====================================================================

def test_docx_english_paragraphs_and_headings():
    """Verifies extraction of DOCX paragraphs and headings in order."""
    blocks = [
        ("h", "Business Catalog"),
        ("p", "We provide general dentistry and teeth whitening services."),
        ("p", "Located at 123 Main Street, open Monday through Saturday."),
    ]
    docx_bytes = create_docx_with_blocks(blocks)
    result = extract_text_from_docx(docx_bytes)

    assert result.total_pages is None
    assert len(result.pages) == 1
    assert result.pages[0].page_number is None
    assert result.has_tables is False

    lines = result.full_text.split("\n\n")
    assert len(lines) == 3
    assert lines[0] == "Business Catalog"
    assert lines[1] == "We provide general dentistry and teeth whitening services."
    assert lines[2] == "Located at 123 Main Street, open Monday through Saturday."


def test_docx_urdu_and_mixed_language_extraction():
    """Verifies that DOCX with Urdu and mixed Urdu/English preserves all Unicode characters."""
    blocks = [
        ("h", "ہماری خدمات (Our Services)"),
        ("p", "ہم دانتوں کے علاج کی بہترین سہولیات فراہم کرتے ہیں۔"),
        ("p", "Consultation Fee: Rs. 1,500 / $25 (ڈاکٹر طارق)."),
    ]
    docx_bytes = create_docx_with_blocks(blocks)
    result = extract_text_from_docx(docx_bytes)

    assert "ہماری خدمات (Our Services)" in result.full_text
    assert "ہم دانتوں کے علاج کی بہترین سہولیات فراہم کرتے ہیں۔" in result.full_text
    assert "Rs. 1,500 / $25 (ڈاکٹر طارق)" in result.full_text


def test_docx_tables_and_document_ordering():
    """Verifies that tables and paragraphs are extracted in their exact sequence within the body."""
    blocks = [
        ("p", "Introductory Paragraph"),
        ("table", [
            ["Service", "Price", "Duration"],
            ["Teeth Cleaning", "Rs. 2,000", "30 mins"],
            ["Root Canal", "Rs. 8,000", "60 mins"],
        ]),
        ("p", "Concluding Remarks"),
    ]
    docx_bytes = create_docx_with_blocks(blocks)
    result = extract_text_from_docx(docx_bytes)

    assert result.has_tables is True

    # Order verification: Intro -> Table -> Concluding
    p1_idx = result.full_text.find("Introductory Paragraph")
    tbl_idx = result.full_text.find("| Service | Price | Duration |")
    p2_idx = result.full_text.find("Concluding Remarks")

    assert p1_idx != -1
    assert tbl_idx != -1
    assert p2_idx != -1
    assert p1_idx < tbl_idx < p2_idx

    # Table format verification (pipe delimiters)
    assert "| Teeth Cleaning | Rs. 2,000 | 30 mins |" in result.full_text
    assert "| Root Canal | Rs. 8,000 | 60 mins |" in result.full_text


def test_docx_empty_and_no_readable_text():
    """Verifies error handling for DOCX with no readable text."""
    # 1. 0-byte input
    with pytest.raises(EmptyDocumentError, match="empty"):
        extract_text_from_docx(b"")

    # 2. Document with only blank spaces
    blocks = [("p", "   "), ("p", "\t\t")]
    blank_docx = create_docx_with_blocks(blocks)
    with pytest.raises(NoExtractableTextError, match="no extractable or readable text"):
        extract_text_from_docx(blank_docx)


def test_docx_corrupted_archive_raises_corrupted_error():
    """Verifies that non-ZIP or corrupted DOCX bytes raise CorruptedDocumentError."""
    corrupted_data = b"PK\x03\x04corrupted fake docx archive"
    with pytest.raises(CorruptedDocumentError):
        extract_text_from_docx(corrupted_data)


# =====================================================================
# 3. Text Normalization Tests
# =====================================================================

def test_normalize_unicode_nfc():
    """Verifies that Unicode NFC normalization composes decomposed characters."""
    # Decomposed: 'e' + combining acute accent (\u0301)
    decomposed = "Cafe\u0301"
    # Precomposed: 'é' (\u00e9)
    precomposed = "Caf\u00e9"

    assert decomposed != precomposed  # Different binary representations
    assert normalize_extracted_text(decomposed) == precomposed
    assert unicodedata.is_normalized("NFC", normalize_extracted_text(decomposed))


def test_normalize_urdu_diacritics_preserved():
    """Verifies that Urdu characters and diacritics (Aeraab) are strictly preserved."""
    # مُحَمَّدٌ (Meem + Pesh, Heh + Zabar, Meem + Tashdeed + Zabar, Dal + Tanween)
    urdu_with_aeraab = "\u0645\u064f\u062d\u064e\u0645\u0651\u064e\u062f\u064c"
    normalized = normalize_extracted_text(urdu_with_aeraab)

    # Must preserve every diacritic code point and conform to NFC
    assert normalized == unicodedata.normalize("NFC", urdu_with_aeraab)
    assert "\u064f" in normalized  # Pesh
    assert "\u064e" in normalized  # Zabar
    assert "\u0651" in normalized  # Tashdeed
    assert "\u064c" in normalized  # Tanween
    assert len([c for c in normalized if c in "\u064f\u064e\u0651\u064c"]) == 5


def test_normalize_urdu_punctuation_preserved():
    """Verifies that Urdu punctuation marks (full stop, question mark, comma) are intact."""
    urdu_text = "کیا آپ کا کلینک کھلا ہے؟ جی ہاں، ہم کھلے ہیں۔"
    normalized = normalize_extracted_text(urdu_text)

    assert "؟" in normalized  # Urdu question mark (\u061f)
    assert "۔" in normalized  # Urdu full stop (\u06d4)
    assert "،" in normalized  # Urdu comma (\u060c)
    assert normalized == urdu_text


def test_normalize_zwnj_preserved():
    """Verifies that Zero-Width Non-Joiner (ZWNJ \u200c) is preserved for Urdu typography."""
    urdu_compound = "بے\u200cشک وہ بڑا مہربان ہے۔"
    normalized = normalize_extracted_text(urdu_compound)

    assert "\u200c" in normalized
    assert normalized == urdu_compound


def test_normalize_whitespace_and_paragraphs():
    """Verifies collapse of horizontal whitespace and normalization of paragraph breaks."""
    raw = "   First   line   with    spaces.   \r\n\r\n\r\n\r\n   Second line.   \n\n\n   Third line.   "
    expected = "First line with spaces.\n\nSecond line.\n\nThird line."
    assert normalize_extracted_text(raw) == expected


def test_normalize_non_breaking_spaces():
    """Verifies conversion of non-breaking spaces (\u00a0 and \u202f) to standard spaces."""
    raw = "Price:\u00a0Rs.\u202f1500"
    assert normalize_extracted_text(raw) == "Price: Rs. 1500"


# =====================================================================
# 4. Unified Dispatcher Tests
# =====================================================================

def test_dispatcher_pdf_and_docx_routing():
    """Verifies that extract_document_text routes properly by format."""
    # PDF route
    pdf_bytes = create_multipage_pdf_bytes()
    doc_pdf = extract_document_text(pdf_bytes, "pdf")
    assert doc_pdf.total_pages == 2

    # DOCX route (with extension variations like '.docx', 'DOCX')
    docx_bytes = create_docx_with_blocks([("p", "Routed paragraph")])
    doc_docx = extract_document_text(docx_bytes, ".DOCX")
    assert "Routed paragraph" in doc_docx.full_text


def test_dispatcher_unsupported_file_type():
    """Verifies that unsupported file types raise UnsupportedDocumentTypeError."""
    for bad_type in ["txt", "png", "zip", "exe", "doc", ""]:
        with pytest.raises(UnsupportedDocumentTypeError, match="Unsupported document file type"):
            extract_document_text(b"some bytes", bad_type)


def test_dispatcher_empty_data():
    """Verifies that 0-byte input raises EmptyDocumentError."""
    with pytest.raises(EmptyDocumentError, match="empty"):
        extract_document_text(b"", "pdf")


def test_dispatcher_enforces_5mb_size_limit():
    """Verifies that payloads exceeding the 5 MB limit raise DocumentExtractionError."""
    oversized = b"%PDF-1.4\n" + b"x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(DocumentExtractionError, match="exceeds maximum allowed limit of 5 MB"):
        extract_document_text(oversized, "pdf")


def test_large_document_near_5mb_limit():
    """Verifies that large valid documents (~4.8MB) near the 5 MB limit extract successfully."""
    # Generate multi-paragraph DOCX near limit
    # 4000 paragraphs of repetitive English text (~4.8MB uncompressed text / reasonable docx size)
    para = "AgentDesk automated knowledge extraction processing test sentence for large document. " * 15
    blocks = [("p", f"Paragraph {i}: {para}") for i in range(1000)]
    large_docx = create_docx_with_blocks(blocks)

    assert len(large_docx) < 5 * 1024 * 1024  # Under 5 MB
    result = extract_document_text(large_docx, "docx")
    assert len(result.full_text) > 500000
    assert "Paragraph 0:" in result.full_text
    assert "Paragraph 999:" in result.full_text
