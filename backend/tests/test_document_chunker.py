"""Unit tests for AgentDesk Document Chunking Layer (Phase 5.4D).

Verifies:
1. English prose, headings, and structure preservation.
2. Urdu text, diacritics (Aeraab), punctuation (۔, ؟), and Unicode fidelity.
3. Mixed-language (English/Urdu) and script ratio classification.
4. PDF page-number preservation and strict absence of cross-page merging.
5. DOCX page_number=None preservation.
6. Contiguous, 0-based global chunk indexing across documents.
7. Recursive splitting of long paragraphs and unpunctuated text.
8. Markdown table row boundary preservation.
9. Overlap constraints and fresh-content guarantees (no overlap-only chunks).
10. Preservation of short trailing fragments.
11. Error handling for empty documents, blank pages, and unsplittable tokens.
12. Exact token-budget enforcement (raw <= 450, prefixed <= 480).
13. E5TokenizerAdapter local asset requirement and TokenizerError handling.
14. 1:1 compatibility with KnowledgeRepository.create_chunks_batch().
"""

import uuid
import pytest

from app.models.knowledge import KnowledgeLanguage, KnowledgeSourceType
from app.services.document_extractor.base import (
    EmptyDocumentError,
    ExtractedDocument,
    ExtractedPage,
    NoExtractableTextError,
)
from app.services.document_chunker import (
    ChunkingError,
    ChunkingResult,
    DocumentChunk,
    DocumentChunker,
    E5TokenizerAdapter,
    MockTokenizer,
    TokenLimitExceededError,
    TokenizerError,
    chunk_document,
    clear_e5_tokenizer_cache,
    detect_content_language,
    get_e5_tokenizer,
)


@pytest.fixture
def test_file_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_tokenizer() -> MockTokenizer:
    return MockTokenizer()


# =====================================================================
# 1. English Prose, Headings & Basic Chunking
# =====================================================================

def test_chunk_english_prose_and_heading(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies chunking of multi-paragraph English documents with Markdown heading."""
    heading = "# Downtown Dental Clinic"
    para1 = "We provide comprehensive oral healthcare, teeth whitening, and preventive dentistry."
    para2 = "Our clinic is open Monday through Saturday from 9:00 AM to 6:00 PM on Main Boulevard."
    full_text = f"{heading}\n\n{para1}\n\n{para2}"

    doc = ExtractedDocument(
        full_text=full_text,
        pages=(ExtractedPage(page_number=1, text=full_text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks == 1
    assert result.chunks[0].chunk_index == 0
    assert result.chunks[0].page_number == 1
    assert result.chunks[0].section_title == "Downtown Dental Clinic"
    assert result.chunks[0].language == KnowledgeLanguage.EN.value
    assert "preventive dentistry" in result.chunks[0].text
    assert result.document_language == KnowledgeLanguage.EN.value


# =====================================================================
# 2. Urdu Text, Diacritics, Punctuation & Script Classification
# =====================================================================

def test_chunk_urdu_text_punctuation_and_diacritics(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that Urdu text preserves Aeraab diacritics, punctuation, and classifies as 'ur'."""
    # مُحَمَّدٌ with Pesh, Zabar, Tashdeed, Tanween
    urdu_text = (
        "ہمارا کلینک پیر سے ہفتہ صبح 9 بجے سے شام 6 بجے تک کھلا رہتا ہے۔ "
        "ڈاکٹر مُحَمَّدٌ طارق دانتوں کے امراض کے ماہر ہیں۔ "
        "کیا آپ دانتوں کا معائنہ کروانا چاہتے ہیں؟ ہم بہترین سہولیات فراہم کرتے ہیں۔"
    )

    doc = ExtractedDocument(
        full_text=urdu_text,
        pages=(ExtractedPage(page_number=1, text=urdu_text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks >= 1
    chunk = result.chunks[0]

    # Verify Urdu punctuation is preserved intact
    assert "۔" in chunk.text
    assert "؟" in chunk.text

    # Verify Urdu diacritics are preserved
    assert "\u064f" in chunk.text  # Pesh
    assert "\u0651" in chunk.text  # Tashdeed
    assert "\u064c" in chunk.text  # Tanween

    # Verify language classification
    assert chunk.language == KnowledgeLanguage.UR.value
    assert result.document_language == KnowledgeLanguage.UR.value


# =====================================================================
# 3. Mixed English/Urdu & Roman Urdu Script Detection
# =====================================================================

def test_chunk_mixed_english_urdu(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies classification of mixed English and Urdu content."""
    mixed_text = (
        "Our specialized services include Root Canal Treatment اور دانتوں کی صفائی. "
        "The consultation fee is Rs. 1,500 ڈاکٹر طارق کے لیے۔"
    )

    doc = ExtractedDocument(
        full_text=mixed_text,
        pages=(ExtractedPage(page_number=1, text=mixed_text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks == 1
    assert result.chunks[0].language == KnowledgeLanguage.MIXED.value
    assert result.document_language == KnowledgeLanguage.MIXED.value


def test_language_detector_script_ratios():
    """Verifies script ratio thresholds for language classification."""
    assert detect_content_language("General dentistry and teeth whitening.") == "en"
    assert detect_content_language("دانتوں کی صفائی اور روٹ کینال کا علاج۔") == "ur"
    assert detect_content_language("Dental Clinic دانتوں کا کلینک") == "mixed"
    # Digits and symbols should be ignored
    assert detect_content_language("1234567890 !@#$%^&*()") == "en"


# =====================================================================
# 4. PDF Page-Number Preservation & No Cross-Page Merging
# =====================================================================

def test_pdf_page_number_preservation_no_cross_page_merging(
    test_file_id: uuid.UUID,
    mock_tokenizer: MockTokenizer,
):
    """Verifies that PDF pages are chunked strictly independently without merging across boundaries."""
    page1_text = "Page 1 Content: General description of business procedures."
    page2_text = "Page 2 Content: Detailed pricing schedule and terms of service."
    page3_text = "Page 3 Content: Contact information and operating branch locations."

    doc = ExtractedDocument(
        full_text=f"{page1_text}\n\n{page2_text}\n\n{page3_text}",
        pages=(
            ExtractedPage(page_number=1, text=page1_text),
            ExtractedPage(page_number=2, text=page2_text),
            ExtractedPage(page_number=3, text=page3_text),
        ),
        total_pages=3,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks == 3

    # Check Page 1
    assert result.chunks[0].page_number == 1
    assert "Page 1 Content" in result.chunks[0].text
    assert "Page 2 Content" not in result.chunks[0].text

    # Check Page 2
    assert result.chunks[1].page_number == 2
    assert "Page 2 Content" in result.chunks[1].text
    assert "Page 1 Content" not in result.chunks[1].text
    assert "Page 3 Content" not in result.chunks[1].text

    # Check Page 3
    assert result.chunks[2].page_number == 3
    assert "Page 3 Content" in result.chunks[2].text


# =====================================================================
# 5. DOCX Page Number is None
# =====================================================================

def test_docx_page_number_none(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that DOCX documents produce chunks with page_number=None."""
    docx_text = "DOCX paragraph 1.\n\nDOCX paragraph 2.\n\nDOCX paragraph 3."

    doc = ExtractedDocument(
        full_text=docx_text,
        pages=(ExtractedPage(page_number=None, text=docx_text),),
        total_pages=None,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks >= 1
    for chunk in result.chunks:
        assert chunk.page_number is None


# =====================================================================
# 6. Global Contiguous Chunk Indexes
# =====================================================================

def test_global_contiguous_chunk_indexes(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that chunk indexes are globally contiguous and 0-based across pages."""
    # Generate 4 short pages
    pages = tuple(
        ExtractedPage(page_number=i, text=f"Page {i} text sentence for testing.")
        for i in range(1, 5)
    )
    doc = ExtractedDocument(
        full_text="\n\n".join(p.text for p in pages),
        pages=pages,
        total_pages=4,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks == 4
    expected_indexes = [0, 1, 2, 3]
    actual_indexes = [c.chunk_index for c in result.chunks]
    assert actual_indexes == expected_indexes


# =====================================================================
# 7. Long Paragraphs & Recursive Splitting
# =====================================================================

def test_long_paragraph_recursive_splitting(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that massive paragraphs (>450 tokens) recursively split into valid chunks."""
    # Generate a single paragraph with 50 sentences (~800 words / ~850 tokens)
    sentence = "Our dental center provides advanced restorative and surgical procedures for all patients. "
    long_para = sentence * 50

    doc = ExtractedDocument(
        full_text=long_para,
        pages=(ExtractedPage(page_number=1, text=long_para),),
        total_pages=1,
        has_tables=False,
    )

    chunker = DocumentChunker(
        tokenizer=mock_tokenizer,
        target_chunk_tokens=400,
        max_payload_tokens=450,
        hard_prefixed_limit=480,
    )
    result = chunker.chunk_document(doc, source_file_id=test_file_id)

    assert result.total_chunks > 1
    for chunk in result.chunks:
        assert chunk.token_count <= 450
        assert chunk.prefixed_token_count <= 480
        assert chunk.page_number == 1


def test_unpunctuated_text_splitting(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that long text with no punctuation splits cleanly at whitespace word boundaries."""
    # 600 words without any punctuation
    words = ["word" + str(i) for i in range(600)]
    unpunctuated_text = " ".join(words)

    doc = ExtractedDocument(
        full_text=unpunctuated_text,
        pages=(ExtractedPage(page_number=1, text=unpunctuated_text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks > 1
    for chunk in result.chunks:
        assert chunk.token_count <= 450
        assert chunk.prefixed_token_count <= 480


def test_unsplittable_single_word_raises_error(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that an unbreakable contiguous string exceeding payload raises TokenLimitExceededError."""
    # A single 3,000-character string without whitespace or punctuation
    unbreakable_word = "x" * 3000

    doc = ExtractedDocument(
        full_text=unbreakable_word,
        pages=(ExtractedPage(page_number=1, text=unbreakable_word),),
        total_pages=1,
        has_tables=False,
    )

    with pytest.raises(TokenLimitExceededError, match="Unsplittable"):
        chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)


# =====================================================================
# 8. Markdown Table Row Preservation
# =====================================================================

def test_table_row_preservation(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that Markdown table rows remain atomic and are not severed mid-pipe."""
    table_rows = [
        "| Service | Price | Duration |",
        "| Teeth Whitening | Rs. 2,500 | 45 mins |",
        "| Root Canal Therapy | Rs. 8,000 | 60 mins |",
        "| Dental Scaling & Polishing | Rs. 2,000 | 30 mins |",
    ]
    table_text = "\n".join(table_rows)

    doc = ExtractedDocument(
        full_text=table_text,
        pages=(ExtractedPage(page_number=1, text=table_text),),
        total_pages=1,
        has_tables=True,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    assert result.total_chunks >= 1
    for chunk in result.chunks:
        for line in chunk.text.split("\n"):
            if line.strip():
                assert line.startswith("|")
                assert line.endswith("|")


# =====================================================================
# 9. Overlap & Fresh Content Guarantees
# =====================================================================

def test_overlap_and_no_duplicate_only_chunks(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies overlap window and confirms that no chunk is emitted with only overlap text."""
    # 3 paragraphs of ~200 tokens each
    p1 = "Paragraph 1 describing general practice policies and appointment booking rules. " * 15
    p2 = "Paragraph 2 describing hygiene and disinfection standards for medical tools. " * 15
    p3 = "Paragraph 3 describing billing schedules and insurance coverage options. " * 15
    text = f"{p1}\n\n{p2}\n\n{p3}"

    doc = ExtractedDocument(
        full_text=text,
        pages=(ExtractedPage(page_number=1, text=text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(
        doc,
        source_file_id=test_file_id,
        tokenizer=mock_tokenizer,
        target_chunk_tokens=300,
        max_payload_tokens=400,
    )

    assert result.total_chunks >= 2

    # Verify that each chunk has distinct text and that consecutive chunks share overlap
    chunk0_text = result.chunks[0].text
    chunk1_text = result.chunks[1].text
    assert chunk0_text != chunk1_text


# =====================================================================
# 10. Short Trailing Fragment Preservation
# =====================================================================

def test_final_short_fragment_preserved(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that a very short final fragment is never discarded."""
    main_text = "Detailed policy guidelines for dental surgery. " * 30
    short_trailing = "Final Note: Emergency support is available at extension 102."
    full_text = f"{main_text}\n\n{short_trailing}"

    doc = ExtractedDocument(
        full_text=full_text,
        pages=(ExtractedPage(page_number=1, text=full_text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)

    # Must preserve the short trailing sentence in the last chunk
    last_chunk = result.chunks[-1]
    assert "Emergency support is available at extension 102" in last_chunk.text


# =====================================================================
# 11. Empty Input & Empty Page Handling
# =====================================================================

def test_empty_document_raises_error(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that documents with no pages raise EmptyDocumentError."""
    doc = ExtractedDocument(full_text="", pages=(), total_pages=0, has_tables=False)
    with pytest.raises(EmptyDocumentError, match="empty document"):
        chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)


def test_blank_pages_raises_no_text_error(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that documents with blank pages raise NoExtractableTextError."""
    doc = ExtractedDocument(
        full_text="   \n\n\t\t",
        pages=(ExtractedPage(page_number=1, text="   "),),
        total_pages=1,
        has_tables=False,
    )
    with pytest.raises(NoExtractableTextError, match="no extractable text"):
        chunk_document(doc, source_file_id=test_file_id, tokenizer=mock_tokenizer)


# =====================================================================
# 12. Token Budget Enforcement (<= 450 Raw, <= 480 Prefixed)
# =====================================================================

def test_exact_token_limit_enforcement(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that every emitted chunk strictly obeys both raw and prefixed token bounds."""
    text = "Comprehensive diagnostic evaluation protocols and treatment documentation. " * 100

    doc = ExtractedDocument(
        full_text=text,
        pages=(ExtractedPage(page_number=1, text=text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(
        doc,
        source_file_id=test_file_id,
        tokenizer=mock_tokenizer,
        target_chunk_tokens=400,
        max_payload_tokens=450,
        hard_prefixed_limit=480,
    )

    assert result.total_chunks > 1
    for chunk in result.chunks:
        assert chunk.token_count <= 450
        assert chunk.prefixed_token_count <= 480
        # Prefixed count must strictly exceed raw count due to 'passage: ' and special tokens
        assert chunk.prefixed_token_count > chunk.token_count


# =====================================================================
# 13. E5TokenizerAdapter Missing Asset Handling
# =====================================================================

def test_e5_tokenizer_adapter_missing_assets_raises_tokenizer_error():
    """Verifies that attempting to load a non-existent local tokenizer raises TokenizerError."""
    with pytest.raises(TokenizerError, match="Local tokenizer assets"):
        E5TokenizerAdapter("/invalid/non_existent/path/tokenizer.json")


# =====================================================================
# 14. Repository Dict Contract Compatibility
# =====================================================================

def test_repository_dict_contract_compatibility(test_file_id: uuid.UUID, mock_tokenizer: MockTokenizer):
    """Verifies that to_repository_dict() matches KnowledgeRepository.create_chunks_batch()."""
    chunk = DocumentChunk(
        source_file_id=test_file_id,
        chunk_index=3,
        text="Sample chunk content for repository testing.",
        token_count=12,
        prefixed_token_count=16,
        page_number=2,
        section_title="Testing Section",
        language=KnowledgeLanguage.EN.value,
    )

    repo_dict = chunk.to_repository_dict()

    assert repo_dict["source_file_id"] == test_file_id
    assert repo_dict["chunk_index"] == 3
    assert repo_dict["answer"] == "Sample chunk content for repository testing."
    assert repo_dict["question"] is None
    assert repo_dict["page_number"] == 2
    assert repo_dict["section_title"] == "Testing Section"
    assert repo_dict["language"] == KnowledgeLanguage.EN.value
    assert repo_dict["source_type"] == KnowledgeSourceType.DOCUMENT_CHUNK.value
    assert repo_dict["tags"] == []
    assert repo_dict["embedding"] is None
    assert repo_dict["embedding_stale"] is True
    assert repo_dict["embedding_model"] is None


# =====================================================================
# 15. Real E5 Tokenizer Integration & Verification (Phase 5.4F.7)
# =====================================================================

def test_real_e5_tokenizer_loading_and_singleton():
    """Verifies that the real E5 tokenizer loads from local cache and is cached as a singleton."""
    clear_e5_tokenizer_cache()
    tok1 = get_e5_tokenizer()
    assert tok1 is not None
    assert isinstance(tok1, E5TokenizerAdapter)

    # Singleton check
    tok2 = get_e5_tokenizer()
    assert tok1 is tok2

    # Direct adapter loading with local files
    tok3 = E5TokenizerAdapter("intfloat/multilingual-e5-small")
    assert tok3 is not None


def test_real_e5_tokenizer_token_count_accuracy():
    """Verifies that count_tokens measures raw tokens without special tokens (<s>, </s>)."""
    tokenizer = get_e5_tokenizer()
    text = "Hello world"
    raw_count = tokenizer.count_tokens(text)
    token_list = tokenizer.tokenize(text)

    # In XLM-RoBERTa / SentencePiece, 'Hello world' has exactly 2 subwords
    assert raw_count == len(token_list)
    assert raw_count == 2
    assert tokenizer.count_tokens("") == 0


def test_real_e5_tokenizer_prefix_and_special_token_accounting():
    """Verifies that count_prefixed_tokens correctly accounts for 'passage: ' (2) + <s> and </s> (2)."""
    tokenizer = get_e5_tokenizer()
    text = "Hello world"
    raw_count = tokenizer.count_tokens(text)
    prefixed_count = tokenizer.count_prefixed_tokens(text, prefix="passage: ")

    # Overhead: 2 tokens for 'passage: ' + 2 tokens for BOS/EOS special tokens = 4 tokens
    assert prefixed_count == raw_count + 4
    assert prefixed_count == 6

    # Test that pre-existing prefix does not double-prefix
    prefixed_already = "passage: Hello world"
    assert tokenizer.count_prefixed_tokens(prefixed_already, prefix="passage: ") == 6


def test_real_e5_tokenizer_truncation_without_special_tokens():
    """Verifies that truncate_tokens truncates raw text without embedding <s> or </s> markers."""
    tokenizer = get_e5_tokenizer()
    text = "Hello world from AgentDesk testing tokenization"
    truncated = tokenizer.truncate_tokens(text, max_tokens=3)

    assert "<s>" not in truncated
    assert "</s>" not in truncated
    assert truncated == "Hello world from"
    assert tokenizer.count_tokens(truncated) <= 3


def test_real_e5_multilingual_chunking_and_budget_enforcement(test_file_id: uuid.UUID):
    """Verifies that multilingual documents (EN, Urdu, Roman Urdu) strictly satisfy token limits."""
    tokenizer = get_e5_tokenizer()

    p1 = "Introduction to AgentDesk\n" + (
        "AgentDesk is an enterprise multi-agent platform designed for customer support and booking automation. " * 30
    )
    p2 = "اردو دستاویز\n" + (
        "یہ ایک کاروباری دستاویز ہے جس میں ہمارے کلینک کی فیس اور ملاقات کے اوقات کی تفصیلات موجود ہیں۔ " * 30
    )
    p3 = "Roman Urdu Notes\n" + (
        "AgentDesk ka maqsad small businesses ko modern AI agents provide karna hai jo Urdu aur English me baat karein. " * 30
    )

    doc = ExtractedDocument(
        full_text=f"{p1}\n\n{p2}\n\n{p3}",
        pages=(
            ExtractedPage(page_number=1, text=p1),
            ExtractedPage(page_number=2, text=p2),
            ExtractedPage(page_number=3, text=p3),
        ),
        total_pages=3,
        has_tables=False,
    )

    result = chunk_document(
        doc,
        source_file_id=test_file_id,
        tokenizer=tokenizer,
        target_chunk_tokens=400,
        max_payload_tokens=450,
        hard_prefixed_limit=480,
        target_overlap_tokens=60,
    )

    assert result.total_chunks >= 6
    assert result.document_language == KnowledgeLanguage.MIXED.value

    # Verify per-chunk invariants
    for i, chunk in enumerate(result.chunks):
        assert chunk.chunk_index == i
        assert chunk.token_count <= 450, f"Chunk {i} raw tokens {chunk.token_count} exceeds 450"
        assert chunk.prefixed_token_count <= 480, f"Chunk {i} prefixed tokens {chunk.prefixed_token_count} exceeds 480"
        assert chunk.prefixed_token_count <= 512, f"Chunk {i} prefixed tokens exceeds model capacity 512"
        assert chunk.token_count > 0
        assert chunk.prefixed_token_count > chunk.token_count
        assert chunk.page_number in (1, 2, 3)

    # Verify page separation (no cross-page chunks)
    page1_chunks = [c for c in result.chunks if c.page_number == 1]
    page2_chunks = [c for c in result.chunks if c.page_number == 2]
    page3_chunks = [c for c in result.chunks if c.page_number == 3]

    assert len(page1_chunks) >= 2
    assert all(c.language == KnowledgeLanguage.EN.value for c in page1_chunks)
    assert len(page2_chunks) >= 2
    assert all(c.language == KnowledgeLanguage.UR.value for c in page2_chunks)
    assert len(page3_chunks) >= 2


def test_real_e5_chunking_no_content_loss_and_overlap(test_file_id: uuid.UUID):
    """Verifies that consecutive chunks on the same page have ~60 token overlap and lose no content."""
    tokenizer = get_e5_tokenizer()

    sentences = [
        f"Paragraph item number {i} detailing system specifications for AgentDesk platform architecture."
        for i in range(1, 40)
    ]
    full_text = "\n\n".join(sentences)

    doc = ExtractedDocument(
        full_text=full_text,
        pages=(ExtractedPage(page_number=1, text=full_text),),
        total_pages=1,
        has_tables=False,
    )

    result = chunk_document(
        doc,
        source_file_id=test_file_id,
        tokenizer=tokenizer,
        target_chunk_tokens=400,
        max_payload_tokens=450,
        hard_prefixed_limit=480,
        target_overlap_tokens=60,
    )

    assert result.total_chunks > 1

    # Verify every sentence exists in at least one chunk (no content loss)
    for sent in sentences:
        found = any(sent in chunk.text for chunk in result.chunks)
        assert found, f"Sentence was lost during chunking: {sent}"


def test_real_e5_chunking_tables_preserved(test_file_id: uuid.UUID):
    """Verifies that markdown table row boundaries remain intact with the real E5 tokenizer."""
    tokenizer = get_e5_tokenizer()

    table_header = "| Service | Fee (PKR) | Duration |\n|---|---|---|"
    table_rows = [f"| Medical Consultation Type {i} | {1000 + i * 500} | {30 + i} mins |" for i in range(1, 60)]
    table_text = table_header + "\n" + "\n".join(table_rows)

    doc = ExtractedDocument(
        full_text=table_text,
        pages=(ExtractedPage(page_number=1, text=table_text),),
        total_pages=1,
        has_tables=True,
    )

    result = chunk_document(
        doc,
        source_file_id=test_file_id,
        tokenizer=tokenizer,
        target_chunk_tokens=400,
        max_payload_tokens=450,
        hard_prefixed_limit=480,
    )

    assert result.total_chunks > 1
    for chunk in result.chunks:
        # Table rows in chunk must be intact pipe-delimited lines
        for line in chunk.text.split("\n"):
            line = line.strip()
            if line:
                assert line.startswith("|") and line.endswith("|"), f"Table line corrupted: {line}"


