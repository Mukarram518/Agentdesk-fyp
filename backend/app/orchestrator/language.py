"""Deterministic language detection for AgentDesk customer messages."""

import re
from typing import List, Optional

from app.orchestrator.schemas import LanguageCode


# Arabic/Urdu Unicode ranges:
# U+0600..U+06FF : Arabic (standard Urdu letters)
# U+0750..U+077F : Arabic Supplement (extended Urdu letters)
# U+FB50..U+FDFF : Arabic Presentation Forms-A
# U+FE70..U+FEFF : Arabic Presentation Forms-B
URDU_SCRIPT_REGEX = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]"
)

# Standard Latin alphabetic characters
LATIN_REGEX = re.compile(r"[a-zA-Z]")

# Roman Urdu grammatical particles, question words, auxiliaries, and common vocabulary
# Distinct from standard English words to avoid false positives.
ROMAN_URDU_WORDS_REGEX = re.compile(
    r"\b(?:"
    r"kya|kyun|kyu|kyoon|kab|kahan|kaha|kidhar|kaise|kese|kesay|kaun|kon|kitna|kitne|kitni|"
    r"hai|hain|hoon|hoga|hogi|hoge|honge|hota|hoti|hote|hona|hone|"
    r"aap|aapka|aapki|aapke|apka|apki|apke|humara|hamara|humari|hamari|mera|meri|mere|mujhe|tujhe|"
    r"nahi|nahin|theek|thik|accha|acha|shukriya|shukria|mehrbani|chahiye|chaheye|"
    r"sakta|sakti|sakte|karwa|karna|karo|karein|karen|karta|karti|karte|kiya|"
    r"batayein|bataen|batao|batana|dijiye|bhejo|bhejein|bhejen|"
    r"khulta|khulti|khulte|khulega|khulna|chahta|chahti|chahte|"
    r"milna|milta|milti|milte|milega|milegi|"
    r"baje|kal|aaj|parso|subah|shaam|dopahar|auqat|rabta|pasandeeda|madad|zariye|shamil|khidmaat|"
    r"assalam|walaikum|salam|aur|bhi"
    r")\b",
    re.IGNORECASE,
)

# Roman Urdu common collocations and phrases
ROMAN_URDU_PHRASES_REGEX = re.compile(
    r"(?:"
    r"\bap\s+(?:ka|ki|ke|ko|se|ne)\b|"
    r"\bmil\s+(?:sakta|sakti|sakte|gaya|raha|rahi|jae|jayega|jayegi)\b|"
    r"\bbarah[- ]?e[- ]?karam\b|"
    r"\bkar\s+(?:dein|den|do)\b|"
    r"\bke\s+(?:sath|baad|liye)\b|"
    r"\bki\s+(?:waja|taraf)\b"
    r")",
    re.IGNORECASE,
)


def _resolve_priority_fallback(
    language_priority: Optional[List[str]] = None,
) -> LanguageCode:
    """Resolves language code from the configured priority list or defaults to EN."""
    if language_priority:
        for item in language_priority:
            normalized = str(item).lower().strip()
            if normalized in (LanguageCode.EN.value, "english"):
                return LanguageCode.EN
            if normalized in (LanguageCode.UR.value, "urdu"):
                return LanguageCode.UR
            if normalized in (
                LanguageCode.MIXED.value,
                "roman_ur",
                "roman_urdu",
                "roman-urdu",
            ):
                return LanguageCode.MIXED
    return LanguageCode.EN


def detect_language(
    text: str,
    language_priority: Optional[List[str]] = None,
) -> LanguageCode:
    """Deterministically detects customer interaction language.

    Detection strategy:
    1. If the text contains native Urdu/Arabic script:
       - If predominantly Urdu script (isolated Latin terms/acronyms like 'AgentDesk' or 'RAG'), returns `LanguageCode.UR`.
       - If both scripts are substantially present (multi-word code-switching), returns `LanguageCode.MIXED`.
    2. If the text contains Latin characters:
       - Checks for distinct Roman Urdu tokens and collocations.
       - If matched, returns `LanguageCode.MIXED`.
       - Otherwise, returns `LanguageCode.EN`.
    3. If the text contains no recognizable linguistic script (e.g. whitespace, numbers, symbols):
       - Falls back to the first supported language in `language_priority`.
       - Defaults to `LanguageCode.EN` if no priority matches.

    Args:
        text: Customer message string.
        language_priority: Optional ordered list of preferred language codes (e.g. ["ur", "en"]).

    Returns:
        LanguageCode (EN, UR, or MIXED).
    """
    if not text:
        return _resolve_priority_fallback(language_priority)

    urdu_chars = len(URDU_SCRIPT_REGEX.findall(text))
    latin_chars = len(LATIN_REGEX.findall(text))
    total_linguistic = urdu_chars + latin_chars

    # Case 1: No linguistic characters (only numbers, whitespace, or punctuation)
    if total_linguistic == 0:
        return _resolve_priority_fallback(language_priority)

    # Case 2: Urdu script characters detected
    if urdu_chars > 0:
        if latin_chars == 0:
            return LanguageCode.UR
        # Both scripts present: check if Latin is just isolated terms/brand names vs multi-word code-switching
        latin_words = re.findall(r"[a-zA-Z]+", text)
        if len(latin_words) > 2 or (len(latin_words) >= 2 and latin_chars >= 10):
            return LanguageCode.MIXED
        if urdu_chars >= latin_chars:
            return LanguageCode.UR
        return LanguageCode.MIXED

    # Case 3: Pure Latin script — distinguish Roman Urdu / Mixed from English
    if ROMAN_URDU_WORDS_REGEX.search(text) or ROMAN_URDU_PHRASES_REGEX.search(text):
        return LanguageCode.MIXED

    return LanguageCode.EN
