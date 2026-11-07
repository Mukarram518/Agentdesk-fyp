"""Document chunking orchestrator coordinating page metadata, overlap, and indexing."""

from typing import List, Optional, Tuple
import uuid

from app.services.document_extractor.base import (
    EmptyDocumentError,
    ExtractedDocument,
    NoExtractableTextError,
)
from app.services.document_chunker.base import (
    ChunkingResult,
    DocumentChunk,
    TokenLimitExceededError,
)
from app.services.document_chunker.language import detect_content_language
from app.services.document_chunker.splitter import split_text_into_atomic_units
from app.services.document_chunker.tokenizer import Tokenizer


def _join_units(units: List[str]) -> str:
    """Joins text units cleanly, using single newlines for table rows and double newlines for prose."""
    if not units:
        return ""
    if len(units) == 1:
        return units[0]

    result = units[0]
    for nxt in units[1:]:
        # If both current end and next start look like table rows, join with newline
        prev_is_table = result.endswith("|")
        next_is_table = nxt.startswith("|") and nxt.endswith("|")
        if prev_is_table and next_is_table:
            result = f"{result}\n{nxt}"
        elif result.endswith((".", "!", "?", "۔", "؟")):
            result = f"{result} {nxt}"
        else:
            result = f"{result}\n\n{nxt}"
    return result.strip()


def _extract_section_title(text: str) -> Optional[str]:
    """Detects Markdown-style heading (# Heading) without inventing false titles."""
    first_line = text.strip().split("\n", 1)[0].strip()
    if first_line.startswith("#"):
        # Strip leading '#' markers
        title = first_line.lstrip("#").strip()
        if title:
            return title
    return None


class DocumentChunker:
    """Coordinates structure-aware, page-preserving chunking for extracted documents."""

    def __init__(
        self,
        tokenizer: Tokenizer,
        target_chunk_tokens: int = 400,
        max_payload_tokens: int = 450,
        hard_prefixed_limit: int = 480,
        target_overlap_tokens: int = 60,
        min_overlap_tokens: int = 50,
        max_overlap_tokens: int = 80,
        passage_prefix: str = "passage: ",
    ) -> None:
        if max_payload_tokens > hard_prefixed_limit:
            raise ValueError("max_payload_tokens cannot exceed hard_prefixed_limit.")
        if target_chunk_tokens > max_payload_tokens:
            raise ValueError("target_chunk_tokens cannot exceed max_payload_tokens.")
        if target_overlap_tokens >= target_chunk_tokens:
            raise ValueError("target_overlap_tokens must be strictly less than target_chunk_tokens.")

        self.tokenizer = tokenizer
        self.target_chunk_tokens = target_chunk_tokens
        self.max_payload_tokens = max_payload_tokens
        self.hard_prefixed_limit = hard_prefixed_limit
        self.target_overlap_tokens = target_overlap_tokens
        self.min_overlap_tokens = min_overlap_tokens
        self.max_overlap_tokens = max_overlap_tokens
        self.passage_prefix = passage_prefix

    def _chunk_page_units(
        self,
        units: List[str],
        source_file_id: uuid.UUID,
        page_number: Optional[int],
        start_chunk_index: int,
    ) -> Tuple[List[DocumentChunk], int]:
        """Chunks atomic units for a single page with overlap and token limits."""
        if not units:
            return [], start_chunk_index

        page_chunks: List[DocumentChunk] = []
        current_chunk_idx = start_chunk_index
        unit_idx = 0
        total_units = len(units)
        overlap_units: List[str] = []

        while unit_idx < total_units:
            chunk_units: List[str] = list(overlap_units)
            # Must consume at least units[unit_idx] (the fresh unit)
            fresh_unit = units[unit_idx]

            # If overlap + fresh_unit exceeds max_payload_tokens, prune overlap from the left
            while chunk_units:
                candidate_text = _join_units(chunk_units + [fresh_unit])
                raw_toks = self.tokenizer.count_tokens(candidate_text)
                pref_toks = self.tokenizer.count_prefixed_tokens(candidate_text, prefix=self.passage_prefix)
                if raw_toks <= self.max_payload_tokens and pref_toks <= self.hard_prefixed_limit:
                    break
                chunk_units.pop(0)

            chunk_units.append(fresh_unit)
            unit_idx += 1

            # Accumulate more fresh units while within target_chunk_tokens
            while unit_idx < total_units:
                next_unit = units[unit_idx]
                candidate_text = _join_units(chunk_units + [next_unit])
                raw_toks = self.tokenizer.count_tokens(candidate_text)
                pref_toks = self.tokenizer.count_prefixed_tokens(candidate_text, prefix=self.passage_prefix)

                # Check if next_unit fits within target limit
                if raw_toks <= self.target_chunk_tokens and pref_toks <= self.hard_prefixed_limit:
                    chunk_units.append(next_unit)
                    unit_idx += 1
                elif unit_idx == total_units - 1 and raw_toks <= self.max_payload_tokens and pref_toks <= self.hard_prefixed_limit:
                    # Absorb the final fragment if it comfortably fits under max_payload
                    chunk_units.append(next_unit)
                    unit_idx += 1
                    break
                else:
                    break

            # Validate final candidate chunk text
            final_text = _join_units(chunk_units)
            raw_tokens = self.tokenizer.count_tokens(final_text)
            prefixed_tokens = self.tokenizer.count_prefixed_tokens(final_text, prefix=self.passage_prefix)

            # If candidate exceeds limits due to overlap, prune overlap units from start
            while chunk_units and (raw_tokens > self.max_payload_tokens or prefixed_tokens > self.hard_prefixed_limit):
                if len(chunk_units) > 1:
                    chunk_units.pop(0)
                    final_text = _join_units(chunk_units)
                    raw_tokens = self.tokenizer.count_tokens(final_text)
                    prefixed_tokens = self.tokenizer.count_prefixed_tokens(final_text, prefix=self.passage_prefix)
                else:
                    break

            if raw_tokens > self.max_payload_tokens or prefixed_tokens > self.hard_prefixed_limit:
                raise TokenLimitExceededError(
                    f"Chunk exceeded limits: raw={raw_tokens} (max {self.max_payload_tokens}), "
                    f"prefixed={prefixed_tokens} (max {self.hard_prefixed_limit})."
                )

            # Detect title and language for this specific chunk
            title = _extract_section_title(final_text)
            chunk_lang = detect_content_language(final_text)

            chunk = DocumentChunk(
                source_file_id=source_file_id,
                chunk_index=current_chunk_idx,
                text=final_text,
                token_count=raw_tokens,
                prefixed_token_count=prefixed_tokens,
                page_number=page_number,
                section_title=title,
                language=chunk_lang,
            )
            page_chunks.append(chunk)
            current_chunk_idx += 1

            # Compute overlap units for the next chunk on the same page
            if unit_idx < total_units:
                overlap_candidates: List[str] = []
                # Traverse current chunk units in reverse to find ~60 tokens
                for u in reversed(chunk_units):
                    test_overlap = [u] + overlap_candidates
                    test_text = _join_units(test_overlap)
                    toks = self.tokenizer.count_tokens(test_text)
                    if toks <= self.max_overlap_tokens:
                        overlap_candidates.insert(0, u)
                    else:
                        break
                overlap_units = overlap_candidates
            else:
                overlap_units = []

        return page_chunks, current_chunk_idx

    def chunk_document(
        self,
        document: ExtractedDocument,
        source_file_id: uuid.UUID,
    ) -> ChunkingResult:
        """Chunks an ExtractedDocument while preserving page numbers and contiguous indexing.

        Guarantees:
        - Rejects empty documents with EmptyDocumentError or NoExtractableTextError.
        - PDF pages are chunked strictly independently (page_number = 1, 2, ...).
        - DOCX pages retain page_number = None.
        - Chunk indexes are globally contiguous and 0-based.
        - Every chunk satisfies raw <= 450 and prefixed <= 480 tokens.
        - Preserves Urdu Unicode and punctuation.
        """
        if not document or not document.pages:
            raise EmptyDocumentError("Cannot chunk empty document (no pages present).")

        if not document.full_text or not document.full_text.strip():
            raise NoExtractableTextError("Cannot chunk document containing no extractable text.")

        all_chunks: List[DocumentChunk] = []
        global_chunk_index = 0

        for page in document.pages:
            page_text = page.text.strip() if page.text else ""
            if not page_text:
                continue

            atomic_units = split_text_into_atomic_units(
                text=page_text,
                tokenizer=self.tokenizer,
                max_payload_tokens=self.max_payload_tokens,
            )

            if not atomic_units:
                continue

            page_chunks, global_chunk_index = self._chunk_page_units(
                units=atomic_units,
                source_file_id=source_file_id,
                page_number=page.page_number,
                start_chunk_index=global_chunk_index,
            )
            all_chunks.extend(page_chunks)

        if not all_chunks:
            raise NoExtractableTextError("Document produced zero extractable chunks.")

        total_tokens = sum(c.token_count for c in all_chunks)
        doc_language = detect_content_language(document.full_text)

        return ChunkingResult(
            source_file_id=source_file_id,
            chunks=tuple(all_chunks),
            total_chunks=len(all_chunks),
            total_tokens=total_tokens,
            document_language=doc_language,
        )

