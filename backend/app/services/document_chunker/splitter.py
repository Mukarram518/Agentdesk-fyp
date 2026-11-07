"""Structure-aware hierarchical text splitter for AgentDesk document chunking.

Splitting Hierarchy:
1. Double newlines (paragraphs and tables)
2. Markdown table rows (line-by-line, preserving atomic '| ... |' rows)
3. Sentence boundaries (English: . ! ?, Urdu: ۔ ؟ \n)
4. Clause boundaries (English: , ; :, Urdu: ، ؛)
5. Whitespace word boundaries
"""

import re
from typing import List

from app.services.document_chunker.base import TokenLimitExceededError
from app.services.document_chunker.tokenizer import Tokenizer

# Regex matching sentence boundaries preserving the delimiter with preceding text
# Supports English (. ! ?), Urdu (۔ \u06D4, ؟ \u061F), and newline breaks
_SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?۔؟\n])\s+", re.UNICODE)

# Regex matching sub-sentence clause boundaries
# Supports English (, ; :) and Urdu (، \u060C, ؛ \u061B, —)
_CLAUSE_SPLIT_REGEX = re.compile(r"(?<=[,;:،؛—])\s+", re.UNICODE)


def _is_table_block(block: str) -> bool:
    """Determines if a text block represents a pipe-delimited Markdown table."""
    lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
    if not lines:
        return False
    # If all non-empty lines start and end with '|'
    return all(line.startswith("|") and line.endswith("|") for line in lines)


def _split_long_sentence(
    sentence: str,
    tokenizer: Tokenizer,
    max_payload_tokens: int,
) -> List[str]:
    """Recursively splits a single sentence exceeding the token payload limit."""
    sentence = sentence.strip()
    if not sentence:
        return []

    # 1. Try splitting by clauses (, ; : ، ؛)
    clauses = [c.strip() for c in _CLAUSE_SPLIT_REGEX.split(sentence) if c.strip()]
    if len(clauses) > 1:
        units: List[str] = []
        for clause in clauses:
            if tokenizer.count_tokens(clause) <= max_payload_tokens:
                units.append(clause)
            else:
                units.extend(_split_long_sentence(clause, tokenizer, max_payload_tokens))
        return units

    # 2. Try splitting by whitespace word boundaries
    words = sentence.split()
    if len(words) > 1:
        units: List[str] = []
        current_words: List[str] = []
        for word in words:
            candidate = " ".join(current_words + [word])
            if tokenizer.count_tokens(candidate) <= max_payload_tokens:
                current_words.append(word)
            else:
                if current_words:
                    units.append(" ".join(current_words))
                    current_words = [word]
                else:
                    # Single word exceeds payload limit
                    tokens = tokenizer.count_tokens(word)
                    raise TokenLimitExceededError(
                        f"Unsplittable single word/token ({tokens} tokens) exceeds maximum limit "
                        f"of {max_payload_tokens} tokens."
                    )
        if current_words:
            units.append(" ".join(current_words))
        return units

    # 3. Unbreakable single string without whitespace exceeding payload
    tokens = tokenizer.count_tokens(sentence)
    raise TokenLimitExceededError(
        f"Unsplittable token sequence of {tokens} tokens exceeds maximum payload limit of {max_payload_tokens}."
    )


def split_text_into_atomic_units(
    text: str,
    tokenizer: Tokenizer,
    max_payload_tokens: int = 450,
) -> List[str]:
    """Splits text into atomic units that are guaranteed to each fit within max_payload_tokens.

    Preserves:
    - Paragraph breaks where possible.
    - Markdown table row boundaries (table rows remain intact unless an individual row > max_payload_tokens).
    - Urdu and English sentence punctuation and typography.
    - Word boundaries without character loss.

    Raises:
        TokenLimitExceededError: If an unbroken string cannot be split within max_payload_tokens.
    """
    if not text or not text.strip():
        return []

    cleaned_text = text.strip()
    # 1. Split into paragraphs / top-level blocks
    raw_blocks = [b.strip() for b in cleaned_text.split("\n\n") if b.strip()]
    atomic_units: List[str] = []

    for block in raw_blocks:
        block_tokens = tokenizer.count_tokens(block)
        if block_tokens <= max_payload_tokens:
            atomic_units.append(block)
            continue

        # 2. Check if block is a Markdown table
        if _is_table_block(block):
            table_rows = [r.strip() for r in block.split("\n") if r.strip()]
            for row in table_rows:
                row_tokens = tokenizer.count_tokens(row)
                if row_tokens <= max_payload_tokens:
                    atomic_units.append(row)
                else:
                    # Individual table row exceeds limit; split cells or words
                    atomic_units.extend(_split_long_sentence(row, tokenizer, max_payload_tokens))
            continue

        # 3. Prose block > max_payload_tokens: split into sentences
        sentences = [s.strip() for s in _SENTENCE_SPLIT_REGEX.split(block) if s.strip()]
        for sentence in sentences:
            sentence_tokens = tokenizer.count_tokens(sentence)
            if sentence_tokens <= max_payload_tokens:
                atomic_units.append(sentence)
            else:
                atomic_units.extend(_split_long_sentence(sentence, tokenizer, max_payload_tokens))

    return atomic_units

