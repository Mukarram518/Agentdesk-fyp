"""Provider-independent exceptions for AgentDesk LLM integrations."""

import re
from typing import Optional
from app.core.exceptions import AgentDeskException


def _sanitize_message(message: str) -> str:
    """Sanitizes sensitive information (API keys, bearer tokens) from error messages."""
    if not message:
        return ""
    # Mask Bearer tokens: Bearer <token>
    sanitized = re.sub(
        r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}",
        r"\1[REDACTED]",
        message,
        flags=re.IGNORECASE,
    )
    # Mask Groq API keys: gsk_[A-Za-z0-9]{16,}
    sanitized = re.sub(r"gsk_[A-Za-z0-9_\-]{16,}", "[REDACTED_API_KEY]", sanitized)
    # Mask OpenAI API keys: sk-[A-Za-z0-9_\-]{16,}
    sanitized = re.sub(r"sk-(proj-)?[A-Za-z0-9_\-]{16,}", "[REDACTED_API_KEY]", sanitized)
    # Mask general key=value or token=value patterns
    sanitized = re.sub(
        r"(api[_-]?key|token|secret|password)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


class LLMProviderError(AgentDeskException):
    """Base exception for all LLM provider failures."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: Optional[str] = None,
        status_code: int = 502,
    ):
        clean_msg = _sanitize_message(message)
        super().__init__(clean_msg, status_code=status_code)
        self.provider_name = provider_name


class LLMAuthenticationError(LLMProviderError):
    """Raised when authentication with the LLM provider fails (invalid or expired credentials)."""

    def __init__(
        self,
        message: str = "LLM provider authentication failed. Please verify API credentials.",
        *,
        provider_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            provider_name=provider_name,
            status_code=502,
        )


class LLMRateLimitError(LLMProviderError):
    """Raised when the LLM provider returns a rate limit (HTTP 429) or quota exceeded error."""

    def __init__(
        self,
        message: str = "LLM provider rate limit exceeded. Please retry later.",
        *,
        provider_name: Optional[str] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            provider_name=provider_name,
            status_code=429,
        )
        self.retry_after = retry_after


class LLMTimeoutError(LLMProviderError):
    """Raised when an inference request to the LLM provider times out."""

    def __init__(
        self,
        message: str = "LLM provider request timed out.",
        *,
        provider_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            provider_name=provider_name,
            status_code=504,
        )
        self.timeout_seconds = timeout_seconds


class LLMResponseError(LLMProviderError):
    """Raised when the LLM provider returns an invalid, unparseable, or empty response."""

    def __init__(
        self,
        message: str = "Invalid response received from LLM provider.",
        *,
        provider_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            provider_name=provider_name,
            status_code=502,
        )

