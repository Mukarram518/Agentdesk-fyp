"""Unit tests for AgentDesk LLM Provider Factory (Phase 6.1D).

Verifies:
1. Default provider selection (defaults to MockLLMProvider).
2. Explicit mock provider selection (case-insensitive).
3. Explicit Groq provider selection (case-insensitive).
4. Correct model/configuration propagation to GroqProvider.
5. Missing Groq API key handling (raises LLMAuthenticationError).
6. Unsupported provider handling (raises LLMConfigurationError / ConfigurationError / ValueError).
7. Settings-driven provider selection via LLM_PROVIDER.
8. Singleton caching, cache clearing, and force_reload.
9. Confirms every returned instance implements LLMProvider.
10. Zero external API requests and zero real credentials required.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.providers.llm import (
    GroqProvider,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProvider,
    LLMProviderError,
    MockLLMProvider,
    SUPPORTED_LLM_PROVIDERS,
    clear_llm_provider_cache,
    get_llm_provider,
)


# Override session DB isolation fixture so pure unit tests can run standalone
@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No database connection needed for pure factory unit tests."""
    yield


@pytest.fixture(autouse=True)
def clean_factory_cache():
    """Ensures each test starts and ends with a clean provider cache."""
    clear_llm_provider_cache()
    yield
    clear_llm_provider_cache()


def _make_mock_settings(
    llm_provider="mock",
    groq_api_key=None,
    groq_model="llama-3.3-70b-versatile",
    groq_timeout=30.0,
    groq_retries=2,
) -> Settings:
    """Helper creating a mock application Settings object."""
    settings = MagicMock(spec=Settings)
    settings.LLM_PROVIDER = llm_provider
    settings.GROQ_API_KEY = groq_api_key
    settings.GROQ_MODEL = groq_model
    settings.GROQ_TIMEOUT_SECONDS = groq_timeout
    settings.GROQ_MAX_RETRIES = groq_retries
    return settings


# =====================================================================
# 1. Default & Mock Provider Tests
# =====================================================================

def test_default_provider_selection_returns_mock():
    """Verifies that calling get_llm_provider() with default settings returns MockLLMProvider."""
    with patch("app.providers.llm.factory.get_settings") as mock_get_settings:
        mock_get_settings.return_value = _make_mock_settings(llm_provider="mock")

        provider = get_llm_provider()

        assert isinstance(provider, LLMProvider)
        assert isinstance(provider, MockLLMProvider)
        assert provider.provider_name == "mock"


def test_explicit_mock_provider_selection_case_insensitive():
    """Verifies explicit mock provider selection with case-insensitivity."""
    for variant in ("mock", "MOCK", " Mock ", "MoCk"):
        provider = get_llm_provider(variant, force_reload=True)
        assert isinstance(provider, MockLLMProvider)
        assert provider.provider_name == "mock"


def test_mock_provider_with_custom_kwargs():
    """Verifies custom parameters passed through factory to MockLLMProvider."""
    provider = get_llm_provider(
        "mock",
        default_response="Custom mock reply",
        model_name="custom-mock-model",
        force_reload=True,
    )
    assert isinstance(provider, MockLLMProvider)
    assert provider.model_name == "custom-mock-model"
    assert provider._default_response == "Custom mock reply"


# =====================================================================
# 2. Groq Provider Selection Tests
# =====================================================================

def test_explicit_groq_provider_selection_case_insensitive():
    """Verifies explicit Groq provider selection with case-insensitivity."""
    mock_client = AsyncMock()

    for variant in ("groq", "GROQ", " Groq ", "GrOq"):
        provider = get_llm_provider(
            variant,
            api_key="gsk_test_key",
            client=mock_client,
            force_reload=True,
        )
        assert isinstance(provider, LLMProvider)
        assert isinstance(provider, GroqProvider)
        assert provider.provider_name == "groq"


def test_groq_configuration_propagated_from_settings():
    """Verifies that settings attributes are correctly propagated to GroqProvider."""
    mock_client = AsyncMock()
    custom_settings = _make_mock_settings(
        llm_provider="groq",
        groq_api_key="gsk_settings_key",
        groq_model="llama-3.1-70b-versatile",
        groq_timeout=45.0,
        groq_retries=3,
    )

    provider = get_llm_provider(
        settings=custom_settings,
        client=mock_client,
    )

    assert isinstance(provider, GroqProvider)
    assert provider.model_name == "llama-3.1-70b-versatile"
    assert provider._timeout_seconds == 45.0
    assert provider._max_retries == 3


def test_groq_missing_api_key_raises_auth_error():
    """Verifies that selecting Groq with no API key raises LLMAuthenticationError."""
    settings_without_key = _make_mock_settings(
        llm_provider="groq",
        groq_api_key=None,
    )

    with pytest.raises(LLMAuthenticationError, match="GROQ_API_KEY is not configured"):
        get_llm_provider("groq", settings=settings_without_key, client=None)


# =====================================================================
# 3. Settings-Driven Selection Tests
# =====================================================================

def test_settings_driven_groq_selection():
    """Verifies that get_llm_provider() reads LLM_PROVIDER='groq' from settings."""
    mock_client = AsyncMock()
    settings_with_groq = _make_mock_settings(
        llm_provider="groq",
        groq_api_key="gsk_test",
    )

    provider = get_llm_provider(
        settings=settings_with_groq,
        client=mock_client,
    )
    assert isinstance(provider, GroqProvider)


# =====================================================================
# 4. Error Handling & Validation Tests
# =====================================================================

def test_unsupported_provider_raises_configuration_error():
    """Verifies unsupported provider names raise LLMConfigurationError."""
    for invalid in ("openai", "anthropic", "gemini", "unknown", "invalid"):
        with pytest.raises(LLMConfigurationError) as exc_info:
            get_llm_provider(invalid)

        assert "Unsupported LLM provider" in str(exc_info.value)
        assert isinstance(exc_info.value, ConfigurationError)
        assert isinstance(exc_info.value, LLMProviderError)
        assert isinstance(exc_info.value, ValueError)


def test_empty_or_whitespace_provider_name_raises():
    """Verifies empty or whitespace-only provider names raise LLMConfigurationError."""
    with pytest.raises(LLMConfigurationError, match="Invalid LLM provider"):
        get_llm_provider("")

    with pytest.raises(LLMConfigurationError, match="Invalid LLM provider"):
        get_llm_provider("   ")


def test_supported_providers_constant():
    """Verifies the tuple of supported providers."""
    assert "mock" in SUPPORTED_LLM_PROVIDERS
    assert "groq" in SUPPORTED_LLM_PROVIDERS


# =====================================================================
# 5. Singleton Caching & Force Reload Tests
# =====================================================================

def test_provider_singleton_caching_and_force_reload():
    """Verifies process-level caching for default factory invocations."""
    with patch("app.providers.llm.factory.get_settings") as mock_settings:
        mock_settings.return_value = _make_mock_settings(llm_provider="mock")

        p1 = get_llm_provider("mock")
        p2 = get_llm_provider("mock")
        assert p1 is p2  # Same cached instance

        # force_reload returns a new instance
        p3 = get_llm_provider("mock", force_reload=True)
        assert p3 is not p1
        assert isinstance(p3, MockLLMProvider)

        # clear cache
        clear_llm_provider_cache()
        p4 = get_llm_provider("mock")
        assert p4 is not p1

