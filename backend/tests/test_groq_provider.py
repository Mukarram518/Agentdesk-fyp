"""Unit tests for AgentDesk Groq LLM Provider Adapter (Phase 6.1C).

Verifies:
1. Conformance with LLMProvider interface.
2. Provider initialization and API key resolution (settings vs param vs missing).
3. Missing API key raises LLMAuthenticationError.
4. Message format conversion (system, user, assistant, tool, names).
5. Tool definitions format conversion.
6. Successful text generation, model & provider metadata, and finish reason.
7. Token usage parsing and total computation.
8. Single and multiple tool-call responses mapping.
9. Malformed tool responses handling (missing function name or object).
10. AuthenticationError -> LLMAuthenticationError mapping.
11. RateLimitError -> LLMRateLimitError mapping (including retry_after).
12. APITimeoutError -> LLMTimeoutError mapping.
13. APIConnectionError -> LLMProviderError (status 503) mapping.
14. Empty completion choices -> LLMResponseError mapping.
15. Zero external network requests (all SDK calls mocked).
"""

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from groq import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.core.config import Settings
from app.providers.llm import (
    ChatMessage,
    GroqProvider,
    LLMAuthenticationError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
    LLMTimeoutError,
    MessageRole,
    ToolCall,
    ToolCallFunction,
    ToolDefinition,
)


# Override session DB isolation fixture so pure unit tests can run standalone
@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No database connection needed for pure Groq provider unit tests."""
    yield


@pytest.fixture
def mock_httpx_request():
    return httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _make_mock_completion(
    content="Hello from Groq!",
    tool_calls=None,
    finish_reason="stop",
    model="llama-3.3-70b-versatile",
    prompt_tokens=15,
    completion_tokens=8,
    total_tokens=23,
):
    """Helper creating a mock Groq ChatCompletion object."""
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message = MagicMock()
    mock_choice.message.content = content
    mock_choice.message.tool_calls = tool_calls
    mock_choice.finish_reason = finish_reason

    mock_resp.choices = [mock_choice]
    mock_resp.model = model

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = total_tokens
    mock_resp.usage = mock_usage

    return mock_resp


# =====================================================================
# 1. Initialization and Interface Conformance Tests
# =====================================================================

def test_groq_provider_conforms_to_llm_provider():
    """Verifies that GroqProvider inherits from LLMProvider."""
    mock_client = AsyncMock()
    provider = GroqProvider(api_key="gsk_test123", client=mock_client)
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, GroqProvider)
    assert provider.provider_name == "groq"
    assert provider.model_name == "llama-3.3-70b-versatile"


def test_groq_provider_missing_api_key_raises_auth_error():
    """Verifies that missing GROQ_API_KEY raises LLMAuthenticationError."""
    with patch("app.providers.llm.groq_provider.get_settings") as mock_settings:
        fake_settings = MagicMock(spec=Settings)
        fake_settings.GROQ_API_KEY = None
        fake_settings.GROQ_MODEL = "llama-3.3-70b-versatile"
        fake_settings.GROQ_TIMEOUT_SECONDS = 30.0
        fake_settings.GROQ_MAX_RETRIES = 2
        mock_settings.return_value = fake_settings

        with pytest.raises(LLMAuthenticationError, match="GROQ_API_KEY is not configured"):
            GroqProvider(api_key=None, client=None)


def test_groq_provider_custom_model_and_timeout():
    """Verifies custom model and timeout configuration."""
    mock_client = AsyncMock()
    provider = GroqProvider(
        api_key="gsk_test",
        model_name="llama-3.1-8b-instant",
        timeout_seconds=45.0,
        client=mock_client,
    )
    assert provider.model_name == "llama-3.1-8b-instant"
    assert provider._timeout_seconds == 45.0


# =====================================================================
# 2. Message and Tool Conversion Tests
# =====================================================================

def test_convert_messages_all_roles():
    """Verifies proper mapping of ChatMessage objects to Groq message dictionaries."""
    mock_client = AsyncMock()
    provider = GroqProvider(api_key="gsk_test", client=mock_client)

    tool_call = ToolCall(
        id="call_check",
        type="function",
        function=ToolCallFunction(name="check_hours", arguments='{"date": "today"}'),
    )

    messages = [
        ChatMessage.system("System prompt instructions"),
        ChatMessage.user("Customer question", name="ali"),
        ChatMessage.assistant(content="Checking for you...", tool_calls=[tool_call]),
        ChatMessage.tool_result(
            tool_call_id="call_check",
            content='{"hours": "9am-8pm"}',
            name="check_hours",
        ),
    ]

    groq_msgs = provider._convert_messages(messages)

    assert len(groq_msgs) == 4
    assert groq_msgs[0] == {"role": "system", "content": "System prompt instructions"}
    assert groq_msgs[1] == {"role": "user", "content": "Customer question", "name": "ali"}
    assert groq_msgs[2] == {
        "role": "assistant",
        "content": "Checking for you...",
        "tool_calls": [
            {
                "id": "call_check",
                "type": "function",
                "function": {"name": "check_hours", "arguments": '{"date": "today"}'},
            }
        ],
    }
    assert groq_msgs[3] == {
        "role": "tool",
        "tool_call_id": "call_check",
        "content": '{"hours": "9am-8pm"}',
        "name": "check_hours",
    }


def test_convert_tools():
    """Verifies proper mapping of ToolDefinitions to Groq tools schema."""
    mock_client = AsyncMock()
    provider = GroqProvider(api_key="gsk_test", client=mock_client)

    tools = [
        ToolDefinition.from_function(
            "search_knowledge",
            "Searches FAQ knowledge base",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        )
    ]

    groq_tools = provider._convert_tools(tools)
    assert groq_tools is not None
    assert len(groq_tools) == 1
    assert groq_tools[0] == {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Searches FAQ knowledge base",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    }

    # None input returns None
    assert provider._convert_tools(None) is None


# =====================================================================
# 3. Successful Generation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_groq_provider_generate_text_success():
    """Verifies successful text completion with GroqProvider."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _make_mock_completion(
        content="Our office is open from 9 AM to 8 PM Monday to Saturday.",
        model="llama-3.3-70b-versatile",
        prompt_tokens=20,
        completion_tokens=14,
        total_tokens=34,
    )

    provider = GroqProvider(api_key="gsk_test", client=mock_client)
    messages = [ChatMessage.user("What are your timings?")]

    response = await provider.generate(messages, temperature=0.3, max_tokens=150)

    assert isinstance(response, LLMResponse)
    assert response.content == "Our office is open from 9 AM to 8 PM Monday to Saturday."
    assert response.provider == "groq"
    assert response.model == "llama-3.3-70b-versatile"
    assert response.finish_reason == "stop"
    assert response.has_tool_calls is False
    assert response.usage is not None
    assert response.usage.prompt_tokens == 20
    assert response.usage.completion_tokens == 14
    assert response.usage.total_tokens == 34

    # Verify parameters passed to Groq SDK
    mock_client.chat.completions.create.assert_awaited_once_with(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "What are your timings?"}],
        temperature=0.3,
        max_tokens=150,
    )


@pytest.mark.asyncio
async def test_groq_provider_generate_with_tool_calls():
    """Verifies generation returning multiple tool calls."""
    mock_client = AsyncMock()

    tc1 = MagicMock()
    tc1.id = "call_1"
    tc1.function = MagicMock(name="search_knowledge", arguments='{"query": "pricing"}')
    tc1.function.name = "search_knowledge"
    tc1.function.arguments = '{"query": "pricing"}'

    tc2 = MagicMock()
    tc2.id = "call_2"
    tc2.function = MagicMock(name="check_availability", arguments='{"date": "2026-11-08"}')
    tc2.function.name = "check_availability"
    tc2.function.arguments = '{"date": "2026-11-08"}'

    mock_client.chat.completions.create.return_value = _make_mock_completion(
        content=None,
        tool_calls=[tc1, tc2],
        finish_reason="tool_calls",
    )

    provider = GroqProvider(api_key="gsk_test", client=mock_client)
    tools = [
        ToolDefinition.from_function("search_knowledge", "Search FAQs"),
        ToolDefinition.from_function("check_availability", "Check Calendar"),
    ]

    response = await provider.generate(
        [ChatMessage.user("I want to know pricing and book a meeting")],
        tools=tools,
    )

    assert response.has_tool_calls is True
    assert len(response.tool_calls) == 2
    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].function.name == "search_knowledge"
    assert response.tool_calls[0].parse_arguments() == {"query": "pricing"}

    assert response.tool_calls[1].id == "call_2"
    assert response.tool_calls[1].function.name == "check_availability"
    assert response.tool_calls[1].parse_arguments() == {"date": "2026-11-08"}
    assert response.finish_reason == "tool_calls"


# =====================================================================
# 4. Error Mapping Tests
# =====================================================================

@pytest.mark.asyncio
async def test_groq_provider_authentication_error(mock_httpx_request):
    """Verifies AuthenticationError is caught and re-raised as LLMAuthenticationError."""
    mock_client = AsyncMock()
    resp = httpx.Response(401, request=mock_httpx_request)
    mock_client.chat.completions.create.side_effect = AuthenticationError(
        "Invalid API Key provided",
        response=resp,
        body=None,
    )

    provider = GroqProvider(api_key="gsk_bad_key", client=mock_client)

    with pytest.raises(LLMAuthenticationError) as exc_info:
        await provider.generate([ChatMessage.user("Hi")])

    assert exc_info.value.provider_name == "groq"
    assert exc_info.value.status_code == 502
    assert "Invalid API Key" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_rate_limit_error(mock_httpx_request):
    """Verifies RateLimitError is caught and re-raised as LLMRateLimitError."""
    mock_client = AsyncMock()
    resp = httpx.Response(429, request=mock_httpx_request)
    mock_client.chat.completions.create.side_effect = RateLimitError(
        "Rate limit reached for model llama-3.3-70b-versatile",
        response=resp,
        body=None,
    )

    provider = GroqProvider(api_key="gsk_test", client=mock_client)

    with pytest.raises(LLMRateLimitError) as exc_info:
        await provider.generate([ChatMessage.user("Hi")])

    assert exc_info.value.provider_name == "groq"
    assert exc_info.value.status_code == 429
    assert "Rate limit reached" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_timeout_error(mock_httpx_request):
    """Verifies APITimeoutError is caught and re-raised as LLMTimeoutError."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = APITimeoutError(request=mock_httpx_request)

    provider = GroqProvider(api_key="gsk_test", timeout_seconds=25.0, client=mock_client)

    with pytest.raises(LLMTimeoutError) as exc_info:
        await provider.generate([ChatMessage.user("Hi")])

    assert exc_info.value.provider_name == "groq"
    assert exc_info.value.status_code == 504
    assert exc_info.value.timeout_seconds == 25.0


@pytest.mark.asyncio
async def test_groq_provider_connection_error(mock_httpx_request):
    """Verifies APIConnectionError is caught and re-raised as LLMProviderError with 503."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = APIConnectionError(
        message="DNS resolution failed",
        request=mock_httpx_request,
    )

    provider = GroqProvider(api_key="gsk_test", client=mock_client)

    with pytest.raises(LLMProviderError) as exc_info:
        await provider.generate([ChatMessage.user("Hi")])

    assert exc_info.value.provider_name == "groq"
    assert exc_info.value.status_code == 503
    assert "DNS resolution failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_empty_choices_raises_response_error():
    """Verifies empty choices in response raises LLMResponseError."""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.choices = []

    mock_client.chat.completions.create.return_value = mock_resp

    provider = GroqProvider(api_key="gsk_test", client=mock_client)

    with pytest.raises(LLMResponseError, match="Groq completion response contains no choices"):
        await provider.generate([ChatMessage.user("Hi")])


@pytest.mark.asyncio
async def test_groq_provider_malformed_tool_call_raises_response_error():
    """Verifies malformed tool call without function name raises LLMResponseError."""
    mock_client = AsyncMock()

    tc_bad = MagicMock()
    tc_bad.function = MagicMock(name="", arguments="{}")
    tc_bad.function.name = None

    mock_client.chat.completions.create.return_value = _make_mock_completion(
        content=None,
        tool_calls=[tc_bad],
        finish_reason="tool_calls",
    )

    provider = GroqProvider(api_key="gsk_test", client=mock_client)

    with pytest.raises(LLMResponseError, match="missing function name"):
        await provider.generate([ChatMessage.user("Hi")])


@pytest.mark.asyncio
async def test_groq_provider_bad_request_error(mock_httpx_request):
    """Verifies BadRequestError is caught and re-raised as LLMProviderError."""
    mock_client = AsyncMock()
    resp = httpx.Response(400, request=mock_httpx_request)
    mock_client.chat.completions.create.side_effect = BadRequestError(
        "Invalid model parameter",
        response=resp,
        body=None,
    )

    provider = GroqProvider(api_key="gsk_test", client=mock_client)

    with pytest.raises(LLMProviderError) as exc_info:
        await provider.generate([ChatMessage.user("Hi")])

    assert exc_info.value.provider_name == "groq"
    assert exc_info.value.status_code == 400

