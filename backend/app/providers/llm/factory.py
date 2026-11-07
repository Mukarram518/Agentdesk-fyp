"""Provider factory for AgentDesk LLM integration (Phase 6.1D)."""

from typing import Any, Dict, Optional

from app.core.config import Settings, get_settings
from app.core.exceptions import ConfigurationError
from app.providers.llm.base import LLMProvider
from app.providers.llm.exceptions import LLMProviderError
from app.providers.llm.groq_provider import GroqProvider
from app.providers.llm.mock_provider import MockLLMProvider

SUPPORTED_LLM_PROVIDERS = ("mock", "groq")

_PROVIDER_CACHE: Dict[str, LLMProvider] = {}


class LLMConfigurationError(ConfigurationError, LLMProviderError, ValueError):
    """Raised when an invalid or unsupported LLM provider is requested or configuration is invalid."""

    def __init__(self, message: str, *, provider_name: Optional[str] = None):
        super().__init__(message)
        self.provider_name = provider_name


def get_llm_provider(
    provider_type: Optional[str] = None,
    *,
    settings: Optional[Settings] = None,
    force_reload: bool = False,
    **kwargs: Any,
) -> LLMProvider:
    """Factory selecting and initializing the configured LLM provider.

    Args:
        provider_type: Optional explicit provider name ('mock' or 'groq').
                       If None, resolves from application settings (LLM_PROVIDER, defaulting to 'mock').
        settings: Optional custom Settings instance. If None, uses get_settings().
        force_reload: If True, bypasses process-level singleton caching and returns a fresh instance.
        **kwargs: Optional configuration overrides passed to provider constructor.

    Returns:
        An instance conforming to LLMProvider.

    Raises:
        LLMConfigurationError: If an unsupported provider name is specified.
        LLMAuthenticationError: If Groq is selected but no API key is available.
    """
    app_settings = settings or get_settings()

    if provider_type is not None:
        raw_type = provider_type
    else:
        raw_type = getattr(app_settings, "LLM_PROVIDER", "mock")

    if not isinstance(raw_type, str) or not raw_type.strip():
        raise LLMConfigurationError(
            f"Invalid LLM provider '{raw_type}'. Supported providers are: {', '.join(repr(p) for p in SUPPORTED_LLM_PROVIDERS)}.",
            provider_name=str(raw_type),
        )

    selected_type = raw_type.strip().lower()

    if selected_type not in SUPPORTED_LLM_PROVIDERS:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{raw_type}'. Supported providers are: {', '.join(repr(p) for p in SUPPORTED_LLM_PROVIDERS)}.",
            provider_name=selected_type,
        )

    # Use cached instance if no kwargs, no custom settings, and not force_reload
    if not force_reload and not kwargs and settings is None and selected_type in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[selected_type]

    provider: LLMProvider

    if selected_type == "mock":
        mock_kwargs: Dict[str, Any] = {}
        for key in ("default_response", "responses", "tool_calls", "provider_name", "model_name"):
            if key in kwargs:
                mock_kwargs[key] = kwargs[key]
        provider = MockLLMProvider(**mock_kwargs)

    elif selected_type == "groq":
        groq_kwargs: Dict[str, Any] = {
            "api_key": kwargs.get("api_key") or app_settings.GROQ_API_KEY,
            "model_name": kwargs.get("model_name") or app_settings.GROQ_MODEL,
            "timeout_seconds": (
                kwargs.get("timeout_seconds")
                if "timeout_seconds" in kwargs
                else app_settings.GROQ_TIMEOUT_SECONDS
            ),
            "max_retries": (
                kwargs.get("max_retries")
                if "max_retries" in kwargs
                else app_settings.GROQ_MAX_RETRIES
            ),
        }
        if "client" in kwargs:
            groq_kwargs["client"] = kwargs["client"]
        provider = GroqProvider(**groq_kwargs)

    if not kwargs and settings is None:
        _PROVIDER_CACHE[selected_type] = provider

    return provider


def clear_llm_provider_cache() -> None:
    """Clears the provider cache (useful for test isolation)."""
    _PROVIDER_CACHE.clear()

