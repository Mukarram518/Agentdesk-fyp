"""Text normalization utility for AgentDesk document extraction.

Preserves:
- Full Urdu character set and diacritics (Aeraab: Zabar, Zair, Pesh, Tashdeed, Tanween, etc.).
- Urdu punctuation (full stop '۔', question mark '؟', comma '،').
- Zero-Width Non-Joiner (ZWNJ '\\u200c') used in Urdu/Persian word boundaries.
- English punctuation, numbers, currency symbols, and mixed-language content.
- Meaningful paragraph boundaries.
"""

import re
import unicodedata


def normalize_extracted_text(text: str) -> str:
    """Normalizes extracted text while strictly preserving language characters and diacritics.

    Processing pipeline:
    1. Unicode NFC canonical decomposition followed by canonical composition.
    2. Convert carriage-return variations (\\r\\n and \\r) to standard line breaks (\\n).
    3. Replace non-breaking spaces (\\u00a0, \\u202f) with regular ASCII spaces (\\x20).
    4. Collapse runs of horizontal whitespace (spaces, tabs) into single spaces.
    5. Strip leading and trailing whitespace on individual lines.
    6. Collapse 3 or more consecutive line breaks into 2 line breaks (\\n\\n) to preserve
       paragraph boundaries without excessive vertical whitespace.
    7. Retain all Urdu characters, diacritics, punctuation, and ZWNJ without modification.
    8. Retain all English punctuation, digits, symbols, and formatting tokens.

    Args:
        text: Raw extracted text string.

    Returns:
        Cleaned, normalized text string.
    """
    if not text:
        return ""

    # 1. Unicode NFC normalization (composes base characters + diacritics into canonical forms)
    normalized = unicodedata.normalize("NFC", text)

    # 2. Line ending normalization
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Replace non-breaking and typographical spaces with standard space
    # Note: \u200c (ZWNJ) is intentionally NOT replaced
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")

    # 4 & 5. Line-by-line horizontal whitespace collapse and edge trimming
    lines = normalized.split("\n")
    processed_lines = []
    for line in lines:
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip(" \t")
        processed_lines.append(cleaned_line)

    normalized = "\n".join(processed_lines)

    # 6. Collapse three or more newlines into two (\n\n) to preserve paragraph breaks
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    # 7. Strip leading and trailing whitespace from the document
    return normalized.strip()

