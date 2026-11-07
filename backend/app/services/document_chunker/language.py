"""Strict script-based language classifier for AgentDesk document chunks.

Guarantees:
- Returns strictly 'en', 'ur', or 'mixed' (satisfying database check constraints).
- Ignores whitespace, digits, punctuation, and typographical formatting.
- Properly accounts for Urdu letters, diacritics (Aeraab), and Unicode blocks.
"""

from app.models.knowledge import KnowledgeLanguage

# Unicode code point ranges for Urdu / Arabic script (letters and diacritics)
_URDU_EXCLUDED_PUNCTUATION_AND_DIGITS = {
    0x060C,  # Urdu comma '،'
    0x061B,  # Urdu semicolon '؛'
    0x061F,  # Urdu question mark '؟'
    0x06D4,  # Urdu full stop '۔'
    # Eastern Arabic-Indic digits 0-9
    0x0660, 0x0661, 0x0662, 0x0663, 0x0664, 0x0665, 0x0666, 0x0667, 0x0668, 0x0669,
    # Extended Arabic-Indic digits 0-9 (Urdu digits)
    0x06F0, 0x06F1, 0x06F2, 0x06F3, 0x06F4, 0x06F5, 0x06F6, 0x06F7, 0x06F8, 0x06F9,
}


def _is_urdu_script_char(char: str) -> bool:
    """Checks if character belongs to Urdu/Arabic letters or diacritics."""
    code = ord(char)
    if code in _URDU_EXCLUDED_PUNCTUATION_AND_DIGITS:
        return False
    return (
        (0x0600 <= code <= 0x06FF)      # Arabic/Urdu basic + diacritics
        or (0x0750 <= code <= 0x077F)  # Arabic Supplement
        or (0xFB50 <= code <= 0xFDFF)  # Arabic Presentation Forms-A
        or (0xFE70 <= code <= 0xFEFF)  # Arabic Presentation Forms-B
    )


def _is_english_script_char(char: str) -> bool:
    """Checks if character belongs to Latin alphabet (A-Z, a-z)."""
    return ("a" <= char <= "z") or ("A" <= char <= "Z")


def detect_content_language(text: str) -> str:
    """Classifies text into 'en', 'ur', or 'mixed'.

    Processing:
    1. Strips out whitespace, digits, punctuation, and non-letter symbols.
    2. Counts Urdu script characters (including Aeraab diacritics).
    3. Counts Latin/English script characters.
    4. Computes relative density.

    Returns:
        KnowledgeLanguage.UR.value ('ur') if Urdu is predominant (>= 85%).
        KnowledgeLanguage.EN.value ('en') if English is predominant (>= 85%).
        KnowledgeLanguage.MIXED.value ('mixed') if both scripts have significant presence.
    """
    if not text:
        return KnowledgeLanguage.EN.value

    urdu_count = 0
    english_count = 0

    for char in text:
        if _is_urdu_script_char(char):
            urdu_count += 1
        elif _is_english_script_char(char):
            english_count += 1

    total_script = urdu_count + english_count
    if total_script == 0:
        return KnowledgeLanguage.EN.value

    urdu_ratio = urdu_count / total_script

    if urdu_ratio >= 0.85:
        return KnowledgeLanguage.UR.value
    elif urdu_ratio <= 0.15:
        return KnowledgeLanguage.EN.value
    else:
        return KnowledgeLanguage.MIXED.value

