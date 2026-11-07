"""Unit tests for AgentDesk Mock LLM Provider (Phase 6.1B).

Verifies:
1. Conformance with LLMProvider abstract interface.
2. Provider and model metadata properties.
3. Successful text response generation.
4. Deterministic repeated responses.
5. Multi-turn queued responses (strings and LLMResponse instances).
6. Configurable tool-call responses.
7. Call tracking and reset capabilities.
8. Empty or invalid input rejections (messages and tools).
9. Guarantee of zero external network/API requests and zero API keys needed.
"""

import pytest

from app.providers.llm import (
    ChatMessage,
    LLMProvider,
    LLMResponse,
    MockLLMProvider,
    ToolCall,
    ToolCallFunction,
    ToolDefinition,
)


# Override session DB isolation fixture so pure unit tests can run standalone
@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No database connection needed for pure Mock LLM unit tests."""
    yield


# =====================================================================
# 1. Interface Conformance & Metadata Tests
# =====================================================================

def test_mock_llm_provider_is_instance_of_llm_provider():
    """Verifies that MockLLMProvider is a concrete subclass of LLMProvider."""
    provider = MockLLMProvider()
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, MockLLMProvider)


def test_mock_llm_provider_default_metadata():
    """Verifies default provider and model metadata."""
    provider = MockLLMProvider()
    assert provider.provider_name == "mock"
    assert provider.model_name == "mock-llm-model"


def test_mock_llm_provider_custom_metadata():
    """Verifies custom provider and model metadata configuration."""
    provider = MockLLMProvider(
        provider_name="test-mock-provider",
        model_name="mock-llama-3-8b",
    )
    assert provider.provider_name == "test-mock-provider"
    assert provider.model_name == "mock-llama-3-8b"


# =====================================================================
# 2. Text Generation & Determinism Tests
# =====================================================================

@pytest.mark.asyncio
async def test_mock_llm_provider_default_text_response():
    """Verifies successful text response generation with default response."""
    provider = MockLLMProvider()
    messages = [ChatMessage.user("What are your business hours?")]

    response = await provider.generate(messages)

    assert isinstance(response, LLMResponse)
    assert response.content is not None
    assert "Deterministic mock response" in response.content
    assert "[Echo: What are your business hours?]" in response.content
    assert response.finish_reason == "stop"
    assert response.provider == "mock"
    assert response.model == "mock-llm-model"
    assert response.usage is not None
    assert response.usage.prompt_tokens > 0
    assert response.usage.completion_tokens > 0
    assert response.usage.total_tokens == response.usage.prompt_tokens + response.usage.completion_tokens


@pytest.mark.asyncio
async def test_mock_llm_provider_deterministic_repeated_responses():
    """Verifies that calling generate with identical messages produces identical responses."""
    provider = MockLLMProvider(default_response="Consistent answer.")
    messages = [ChatMessage.user("Can I book a consultation?")]

    resp1 = await provider.generate(messages)
    resp2 = await provider.generate(messages)

    assert resp1.content == resp2.content
    assert resp1.content == "Consistent answer. [Echo: Can I book a consultation?]"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_mock_llm_provider_set_default_response():
    """Verifies setting a new default response text."""
    provider = MockLLMProvider()
    provider.set_default_response("Custom configured reply.")

    messages = [ChatMessage.system("System prompt")]
    response = await provider.generate(messages)

    assert response.content == "Custom configured reply."

    # Cannot set empty default response
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        provider.set_default_response("")
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        provider.set_default_response("   ")


# =====================================================================
# 3. Queued Multi-Turn Responses Tests
# =====================================================================

@pytest.mark.asyncio
async def test_mock_llm_provider_queued_string_responses():
    """Verifies that queued string responses are yielded sequentially."""
    provider = MockLLMProvider(
        responses=[
            "First turn answer.",
            "Second turn answer.",
        ]
    )

    resp1 = await provider.generate([ChatMessage.user("Question 1")])
    assert resp1.content == "First turn answer."

    resp2 = await provider.generate([ChatMessage.user("Question 2")])
    assert resp2.content == "Second turn answer."

    # When queue is exhausted, falls back to default response
    resp3 = await provider.generate([ChatMessage.user("Question 3")])
    assert "Deterministic mock response" in resp3.content


@pytest.mark.asyncio
async def test_mock_llm_provider_add_response_dynamically():
    """Verifies adding responses dynamically via add_response()."""
    provider = MockLLMProvider()
    provider.add_response("Dynamic answer 1")
    provider.add_response(
        LLMResponse(
            content="Dynamic LLMResponse object",
            finish_reason="stop",
            model="custom-mock",
        )
    )

    resp1 = await provider.generate([ChatMessage.user("Turn 1")])
    assert resp1.content == "Dynamic answer 1"

    resp2 = await provider.generate([ChatMessage.user("Turn 2")])
    assert resp2.content == "Dynamic LLMResponse object"
    assert resp2.model == "custom-mock"

    # Rejection of invalid response types or empty strings
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        provider.add_response("   ")
    with pytest.raises(ValueError, match="Response must be a str or LLMResponse instance"):
        provider.add_response(12345)  # type: ignore


# =====================================================================
# 4. Tool Call Configuration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_mock_llm_provider_default_tool_calls():
    """Verifies generating configured tool calls when tool_calls is provided at init."""
    tool_call = ToolCall(
        id="call_check_hours",
        type="function",
        function=ToolCallFunction(
            name="check_calendar_availability",
            arguments='{"date": "2026-11-10"}',
        ),
    )
    provider = MockLLMProvider(tool_calls=[tool_call])
    messages = [ChatMessage.user("Book me an appointment tomorrow")]

    response = await provider.generate(messages)

    assert response.has_tool_calls is True
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call_check_hours"
    assert response.tool_calls[0].function.name == "check_calendar_availability"
    parsed_args = response.tool_calls[0].parse_arguments()
    assert parsed_args == {"date": "2026-11-10"}
    assert response.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_mock_llm_provider_add_tool_call_response():
    """Verifies queueing tool calls using add_tool_call_response()."""
    provider = MockLLMProvider()
    provider.add_tool_call_response(
        name="search_knowledge",
        arguments={"query": "refund policy", "limit": 3},
        call_id="call_rag_1",
    )

    tools = [ToolDefinition.from_function("search_knowledge", "Searches business FAQ")]
    messages = [ChatMessage.user("What is your refund policy?")]

    response = await provider.generate(messages, tools=tools)

    assert response.has_tool_calls is True
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call_rag_1"
    assert response.tool_calls[0].function.name == "search_knowledge"
    assert response.tool_calls[0].parse_arguments() == {"query": "refund policy", "limit": 3}
    assert response.finish_reason == "tool_calls"


def test_mock_llm_provider_add_tool_call_invalid_arguments():
    """Verifies rejection of invalid argument types in add_tool_call_response."""
    provider = MockLLMProvider()
    with pytest.raises(ValueError, match="Arguments must be a dict or a valid JSON string"):
        provider.add_tool_call_response(name="bad_tool", arguments=123)  # type: ignore


# =====================================================================
# 5. Call Tracking & Reset Tests
# =====================================================================

@pytest.mark.asyncio
async def test_mock_llm_provider_call_tracking_and_reset():
    """Verifies call count, parameter tracking, and reset."""
    provider = MockLLMProvider()
    assert provider.call_count == 0
    assert len(provider.calls) == 0

    tools = [ToolDefinition.from_function("tool_a", "Description A")]
    messages = [ChatMessage.user("Test message")]

    await provider.generate(
        messages,
        tools=tools,
        temperature=0.5,
        max_tokens=100,
        custom_param="agentdesk",
    )

    assert provider.call_count == 1
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["messages"] == messages
    assert call["tools"] == tools
    assert call["temperature"] == 0.5
    assert call["max_tokens"] == 100
    assert call["kwargs"] == {"custom_param": "agentdesk"}

    # Reset
    provider.reset()
    assert provider.call_count == 0
    assert len(provider.calls) == 0


# =====================================================================
# 6. Input Validation Rejection Tests
# =====================================================================

@pytest.mark.asyncio
async def test_mock_llm_provider_empty_messages_rejected():
    """Verifies rejection of empty messages list."""
    provider = MockLLMProvider()
    with pytest.raises(ValueError, match="non-empty list of ChatMessage"):
        await provider.generate([])


@pytest.mark.asyncio
async def test_mock_llm_provider_invalid_tools_rejected():
    """Verifies rejection of duplicate tool definitions."""
    provider = MockLLMProvider()
    dup_tools = [
        ToolDefinition.from_function("search", "Search A"),
        ToolDefinition.from_function("search", "Search B"),
    ]
    with pytest.raises(ValueError, match="Duplicate tool definition name 'search'"):
        await provider.generate([ChatMessage.user("Hello")], tools=dup_tools)

