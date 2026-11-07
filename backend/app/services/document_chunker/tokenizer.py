"""Tokenizer abstraction and implementations for AgentDesk document chunking."""

from abc import ABC, abstractmethod
import os
import re
from typing import Any, List, Optional

from app.services.document_chunker.base import TokenizerError

DEFAULT_E5_MODEL_NAME = "intfloat/multilingual-e5-small"
_e5_tokenizer_instance: Optional["E5TokenizerAdapter"] = None


class Tokenizer(ABC):
    """Abstract interface for tokenization in AgentDesk chunking."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Counts raw tokens for text without prefixes or special tokens."""
        pass

    @abstractmethod
    def count_prefixed_tokens(self, text: str, prefix: str = "passage: ") -> int:
        """Counts total encoded tokens for text prefixed with `prefix` including special tokens (<s>, </s>)."""
        pass

    @abstractmethod
    def truncate_tokens(self, text: str, max_tokens: int) -> str:
        """Safely truncates text to fit within max_tokens without breaking Unicode characters."""
        pass

    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        """Returns token string representations for inspection or splitting."""
        pass


class MockTokenizer(Tokenizer):
    """Deterministic, rule-based tokenizer for offline unit tests.

    Guarantees:
    - Zero external network calls or downloaded model assets.
    - Accurately segments English, Urdu, punctuation, and Unicode text.
    - Incorporates exact boundary special tokens: <s> (BOS = 1) and </s> (EOS = 1).
    - Preserves deterministic token-to-word relationships across test runs.
    """

    def __init__(self, special_token_count: int = 2) -> None:
        self.special_token_count = special_token_count
        # Matches word sequences or individual punctuation/symbol characters
        self._token_pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def tokenize(self, text: str) -> List[str]:
        """Extracts token tokens from text using Unicode word and symbol boundaries.

        Splits words longer than 4 characters into subwords of up to 4 characters
        to accurately reflect subword-based BPE / SentencePiece tokenization.
        """
        if not text:
            return []
        matches = self._token_pattern.findall(text)
        tokens: List[str] = []
        for m in matches:
            if len(m) > 4:
                tokens.extend([m[i : i + 4] for i in range(0, len(m), 4)])
            else:
                tokens.append(m)
        return tokens

    def count_tokens(self, text: str) -> int:
        """Counts raw tokens in text."""
        return len(self.tokenize(text))

    def count_prefixed_tokens(self, text: str, prefix: str = "passage: ") -> int:
        """Counts tokens for f'{prefix}{text}' plus BOS (<s>) and EOS (</s>) special tokens."""
        full_text = f"{prefix}{text}" if prefix else text
        raw_count = len(self.tokenize(full_text))
        return raw_count + self.special_token_count

    def truncate_tokens(self, text: str, max_tokens: int) -> str:
        """Truncates text to fit within max_tokens."""
        if max_tokens <= 0:
            return ""
        tokens = self.tokenize(text)
        if len(tokens) <= max_tokens:
            return text

        count = 0
        end_pos = 0
        for match in self._token_pattern.finditer(text):
            word = match.group(0)
            sub_count = (len(word) + 3) // 4 if len(word) > 4 else 1
            if count + sub_count >= max_tokens:
                remaining = max_tokens - count
                end_pos = match.start() + (remaining * 4)
                break
            count += sub_count
            end_pos = match.end()

        return text[:end_pos].strip()


class E5TokenizerAdapter(Tokenizer):
    """Adapter wrapping Hugging Face tokenizers for intfloat/multilingual-e5-small.

    Loads locally via tokenizers.Tokenizer.from_file() or AutoTokenizer with local_files_only=True.
    Raises TokenizerError if local assets are missing or cannot be parsed.
    """

    def __init__(
        self,
        model_path_or_name: str = DEFAULT_E5_MODEL_NAME,
        tokenizer_instance: Optional[Any] = None,
    ) -> None:
        self.model_path_or_name = model_path_or_name
        self._tokenizer = tokenizer_instance or self._load_tokenizer(model_path_or_name)

    def _load_tokenizer(self, target: str):
        """Loads tokenizer strictly from local files without attempting network downloads."""
        # 1. Direct file path check (e.g. path to tokenizer.json)
        if os.path.isfile(target):
            try:
                from tokenizers import Tokenizer as HFTokenizer
                return HFTokenizer.from_file(target)
            except Exception as exc:
                raise TokenizerError(f"Failed to load tokenizer from file '{target}': {exc}") from exc

        # 2. Directory or model identifier check
        try:
            from transformers import AutoTokenizer
            return AutoTokenizer.from_pretrained(target, local_files_only=True)
        except Exception as exc:
            raise TokenizerError(
                f"Local tokenizer assets for '{target}' could not be loaded: {exc}. "
                "Ensure local model directory exists or provide path to local tokenizer.json."
            ) from exc

    def count_tokens(self, text: str) -> int:
        """Counts raw tokens for text without prefixes or special tokens."""
        if not text:
            return 0
        try:
            # Handles both tokenizers.Tokenizer and transformers.PreTrainedTokenizerBase
            if hasattr(self._tokenizer, "encode"):
                try:
                    res = self._tokenizer.encode(text, add_special_tokens=False, verbose=False)
                except TypeError:
                    res = self._tokenizer.encode(text, add_special_tokens=False)
                if hasattr(res, "ids"):
                    # Hugging Face tokenizers.Tokenizer
                    return len(res.ids)
                elif isinstance(res, list):
                    # transformers AutoTokenizer with add_special_tokens=False
                    return len(res)
            return len(self._tokenizer(text, add_special_tokens=False)["input_ids"])
        except Exception as exc:
            raise TokenizerError(f"Token counting failed: {exc}") from exc

    def count_prefixed_tokens(self, text: str, prefix: str = "passage: ") -> int:
        """Counts total encoded tokens for text prefixed with `prefix` including special tokens (<s>, </s>)."""
        if not text:
            return 0
        full_text = text if prefix and text.startswith(prefix) else f"{prefix}{text}"
        try:
            if hasattr(self._tokenizer, "encode"):
                try:
                    res = self._tokenizer.encode(full_text, add_special_tokens=True, verbose=False)
                except TypeError:
                    res = self._tokenizer.encode(full_text, add_special_tokens=True)
                if hasattr(res, "ids"):
                    # Note: fast tokenizer encodes without special tokens unless post-processor configured
                    # If special tokens not automatically added, account for BOS (<s>) and EOS (</s>)
                    count = len(res.ids)
                    if hasattr(self._tokenizer, "num_special_tokens_to_add"):
                        count += self._tokenizer.num_special_tokens_to_add(False)
                    return count
                elif isinstance(res, list):
                    return len(res)
            # transformers AutoTokenizer
            encoded = self._tokenizer(full_text, add_special_tokens=True)
            return len(encoded["input_ids"])
        except Exception as exc:
            raise TokenizerError(f"Prefixed token counting failed: {exc}") from exc

    def truncate_tokens(self, text: str, max_tokens: int) -> str:
        """Safely truncates text to fit within max_tokens without breaking characters or injecting special tokens."""
        if not text or max_tokens <= 0:
            return ""
        try:
            if hasattr(self._tokenizer, "encode") and hasattr(self._tokenizer, "decode"):
                try:
                    res = self._tokenizer.encode(text, add_special_tokens=False, verbose=False)
                except TypeError:
                    res = self._tokenizer.encode(text, add_special_tokens=False)
                ids = res.ids if hasattr(res, "ids") else res
                truncated_ids = ids[:max_tokens]
                try:
                    return self._tokenizer.decode(truncated_ids, skip_special_tokens=True).strip()
                except TypeError:
                    return self._tokenizer.decode(truncated_ids).strip()
            # transformers AutoTokenizer
            ids = self._tokenizer.encode(text, add_special_tokens=False)[:max_tokens]
            return self._tokenizer.decode(ids, skip_special_tokens=True).strip()
        except Exception as exc:
            raise TokenizerError(f"Token truncation failed: {exc}") from exc

    def tokenize(self, text: str) -> List[str]:
        """Returns token string representations."""
        if not text:
            return []
        try:
            if hasattr(self._tokenizer, "tokenize"):
                return self._tokenizer.tokenize(text)
            if hasattr(self._tokenizer, "encode"):
                res = self._tokenizer.encode(text, add_special_tokens=False)
                if hasattr(res, "tokens"):
                    return list(res.tokens)
                elif isinstance(res, list):
                    return [str(i) for i in res]
            return [str(i) for i in self._tokenizer.encode(text)]
        except Exception as exc:
            raise TokenizerError(f"Tokenization failed: {exc}") from exc


def get_e5_tokenizer(
    model_path_or_name: str = DEFAULT_E5_MODEL_NAME,
    force_reload: bool = False,
) -> E5TokenizerAdapter:
    """Returns a process-level cached E5TokenizerAdapter instance.

    Lazily loaded on first use; reused across files and worker tasks.
    """
    global _e5_tokenizer_instance
    if (
        _e5_tokenizer_instance is None
        or force_reload
        or _e5_tokenizer_instance.model_path_or_name != model_path_or_name
    ):
        _e5_tokenizer_instance = E5TokenizerAdapter(model_path_or_name)
    return _e5_tokenizer_instance


def clear_e5_tokenizer_cache() -> None:
    """Clears cached tokenizer instance (for test isolation)."""
    global _e5_tokenizer_instance
    _e5_tokenizer_instance = None

