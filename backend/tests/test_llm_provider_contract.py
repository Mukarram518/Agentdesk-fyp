"""Unit tests for AgentDesk foundational LLM provider contract (Phase 6.1A).

Verifies:
1. Abstract Interface Behavior (LLMProvider):
   - Instantiation prevention on abstract class.
   - Property enforcement (provider_name, model_name).
   - Method enforcement (generate).
   - Concrete provider implementation behavior.
   - Message validation helper (validate_messages).
   - Tool definition validation helper (validate_tools).
2. Message Schemas:
   - MessageRole enumeration.
   - System, user, assistant, and tool ChatMessage creation.
   - Role-specific content and tool call validations.
   - Convenience factory constructors.
3. Tool Definition & Call Schemas:
   - ToolFunction and ToolDefinition creation and validation.
   - Function name validation constraints (alphanumeric, underscores, hyphens).
   - ToolCall and ToolCallFunction schemas.
   - Safe argument deserialization (parse_arguments) and error handling.
4. Token Usage & Request Schemas:
   - TokenUsage computation and validation.
   - LLMRequest options, temperature bounds, and constraints.
5. Response Schema:
   - LLMResponse with content and/or tool_calls.
   - Rejection of completely empty responses.
   - Metadata preservation (finish_reason, usage, model, provider).
6. Exception Hierarchy & Security Redaction:
   - Inheritance from LLMProviderError and AgentDeskException.
   - Appropriate HTTP status codes.
   - Sensitive credential redaction (Bearer tokens, Groq keys, OpenAI keys).
"""

from typing import Any, Dict, List, Optional
import pytest
from pydantic import ValidationError

from app.core.exceptions import AgentDeskException
from app.providers.llm import (
    ChatMessage,
    LLMAuthenticationError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMResponseError,
    LLMTimeoutError,
    MessageRole,
    TokenUsage,
    ToolCall,
    ToolCallFunction,
    ToolDefinition,
    ToolFunction,
)


# Override session DB isolation fixture so pure unit tests can run standalone
@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No database connection needed for pure LLM contract unit tests."""
    yield


# =====================================================================
# Dummy Concrete Provider for Testing Interface Conformance
# =====================================================================

class ConcreteTestProvider(LLMProvider):
    """Concrete implementation for verifying LLMProvider contract."""

    def __init__(self, provider: str = "mock-llm", model: str = "mock-model"):
        self._provider = provider
        self._model = model

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.validate_messages(messages)
        self.validate_tools(tools)
        return LLMResponse(
            content="Mock reply",
            provider=self.provider_name,
            model=self.model_name,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        )


# =====================================================================
# 1. Abstract Interface Behavior Tests
# =====================================================================

def test_cannot_instantiate_abstract_provider():
    """Verifies that LLMProvider cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        LLMProvider()  # type: ignore


def test_subclass_missing_properties_raises():
    """Verifies that a subclass missing required abstract properties cannot be instantiated."""
    class IncompleteProvider(LLMProvider):
        async def generate(self, messages, tools=None, **kwargs):
            return LLMResponse(content="ok")

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteProvider()  # type: ignore


@pytest.mark.asyncio
async def test_concrete_provider_contract_execution():
    """Verifies that a fully conformant subclass operates correctly."""
    provider = ConcreteTestProvider()
    assert provider.provider_name == "mock-llm"
    assert provider.model_name == "mock-model"

    messages = [ChatMessage.user("Hello, AgentDesk!")]
    response = await provider.generate(messages)

    assert isinstance(response, LLMResponse)
    assert response.content == "Mock reply"
    assert response.provider == "mock-llm"
    assert response.finish_reason == "stop"
    assert response.usage is not None
    assert response.usage.total_tokens == 15


def test_validate_messages_success():
    """Verifies message list validation succeeds with valid ChatMessage instances."""
    provider = ConcreteTestProvider()
    valid_msgs = [
        ChatMessage.system("System prompt"),
        ChatMessage.user("User question"),
    ]
    validated = provider.validate_messages(valid_msgs)
    assert validated == valid_msgs


def test_validate_messages_rejections():
    """Verifies message list validation rejects invalid inputs."""
    provider = ConcreteTestProvider()

    with pytest.raises(ValueError, match="non-empty list"):
        provider.validate_messages([])

    with pytest.raises(ValueError, match="non-empty list"):
        provider.validate_messages(None)  # type: ignore

    with pytest.raises(ValueError, match="non-empty list"):
        provider.validate_messages("not a list")  # type: ignore

    with pytest.raises(ValueError, match="must be an instance of ChatMessage"):
        provider.validate_messages([{"role": "user", "content": "hi"}])  # type: ignore


def test_validate_tools_success():
    """Verifies tool validation succeeds with valid tools or None/empty."""
    provider = ConcreteTestProvider()
    assert provider.validate_tools(None) is None
    assert provider.validate_tools([]) is None

    tools = [
        ToolDefinition.from_function("search_knowledge", "Searches business FAQ"),
        ToolDefinition.from_function("check_hours", "Checks store opening hours"),
    ]
    assert provider.validate_tools(tools) == tools


def test_validate_tools_rejections():
    """Verifies tool validation rejects non-list, invalid items, or duplicates."""
    provider = ConcreteTestProvider()

    with pytest.raises(ValueError, match="must be a list"):
        provider.validate_tools("invalid")  # type: ignore

    with pytest.raises(ValueError, match="must be an instance of ToolDefinition"):
        provider.validate_tools([{"name": "test"}])  # type: ignore

    duplicate_tools = [
        ToolDefinition.from_function("same_tool", "Tool description 1"),
        ToolDefinition.from_function("same_tool", "Tool description 2"),
    ]
    with pytest.raises(ValueError, match="Duplicate tool definition name 'same_tool'"):
        provider.validate_tools(duplicate_tools)


# =====================================================================
# 2. ChatMessage Schema & MessageRole Tests
# =====================================================================

def test_message_roles_enum():
    """Verifies that MessageRole values conform to expected strings."""
    assert MessageRole.SYSTEM.value == "system"
    assert MessageRole.USER.value == "user"
    assert MessageRole.ASSISTANT.value == "assistant"
    assert MessageRole.TOOL.value == "tool"


def test_chat_message_constructors_and_factories():
    """Verifies standard ChatMessage construction and classmethod factories."""
    sys_msg = ChatMessage.system("System instructions")
    assert sys_msg.role == MessageRole.SYSTEM
    assert sys_msg.content == "System instructions"

    user_msg = ChatMessage.user("Hello")
    assert user_msg.role == MessageRole.USER
    assert user_msg.content == "Hello"

    asst_msg = ChatMessage.assistant("Assistant reply")
    assert asst_msg.role == MessageRole.ASSISTANT
    assert asst_msg.content == "Assistant reply"

    tool_call = ToolCall(
        id="call_123",
        type="function",
        function=ToolCallFunction(name="test_tool", arguments='{"q": "hours"}'),
    )
    asst_tool_msg = ChatMessage.assistant(tool_calls=[tool_call])
    assert asst_tool_msg.role == MessageRole.ASSISTANT
    assert asst_tool_msg.content is None
    assert asst_tool_msg.tool_calls == [tool_call]

    tool_res_msg = ChatMessage.tool_result(
        tool_call_id="call_123", content='{"hours": "9am-5pm"}', name="test_tool"
    )
    assert tool_res_msg.role == MessageRole.TOOL
    assert tool_res_msg.tool_call_id == "call_123"
    assert tool_res_msg.content == '{"hours": "9am-5pm"}'
    assert tool_res_msg.name == "test_tool"


def test_chat_message_validation_rejections():
    """Verifies ChatMessage rejects empty contents or missing IDs."""
    # System message cannot be empty or whitespace
    with pytest.raises(ValidationError, match="System messages must contain non-empty 'content'"):
        ChatMessage.system("")
    with pytest.raises(ValidationError, match="System messages must contain non-empty 'content'"):
        ChatMessage.system("   ")

    # User message cannot be empty or whitespace
    with pytest.raises(ValidationError, match="User messages must contain non-empty 'content'"):
        ChatMessage.user("")
    with pytest.raises(ValidationError, match="User messages must contain non-empty 'content'"):
        ChatMessage.user("   ")

    # Assistant message cannot be completely empty without tools
    with pytest.raises(
        ValidationError,
        match="Assistant message must contain either non-empty 'content' or at least one 'tool_call'",
    ):
        ChatMessage.assistant(content=None, tool_calls=None)

    with pytest.raises(
        ValidationError,
        match="Assistant message must contain either non-empty 'content' or at least one 'tool_call'",
    ):
        ChatMessage.assistant(content="   ", tool_calls=[])

    # Tool message requires tool_call_id
    with pytest.raises(ValidationError, match="Tool messages must specify a non-empty 'tool_call_id'"):
        ChatMessage(role=MessageRole.TOOL, content="result", tool_call_id="")


# =====================================================================
# 3. ToolDefinition, ToolFunction & ToolCall Tests
# =====================================================================

def test_tool_definition_and_function_creation():
    """Verifies ToolDefinition and ToolFunction schema validation and factory method."""
    tool = ToolDefinition.from_function(
        name="search_faqs",
        description="Searches store FAQs",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    assert tool.type == "function"
    assert tool.function.name == "search_faqs"
    assert tool.function.description == "Searches store FAQs"
    assert tool.function.parameters["required"] == ["query"]


def test_tool_function_name_validation():
    """Verifies tool function names allow valid identifiers and reject illegal characters."""
    valid_names = ["search_faqs", "check-hours", "tool123", "GET_INFO"]
    for name in valid_names:
        func = ToolFunction(name=name, description="Test description")
        assert func.name == name

    invalid_names = ["search faqs", "tool@name", "tool!#", "", "bad/name"]
    for name in invalid_names:
        with pytest.raises(ValidationError):
            ToolFunction(name=name, description="Test description")


def test_tool_call_parse_arguments_success():
    """Verifies ToolCall correctly parses valid JSON arguments."""
    tool_call = ToolCall(
        id="call_abc",
        type="function",
        function=ToolCallFunction(
            name="search_knowledge",
            arguments='{"query": "timing", "limit": 3}',
        ),
    )
    args = tool_call.parse_arguments()
    assert args == {"query": "timing", "limit": 3}

    # Empty string parses to empty dict
    tool_call_empty = ToolCall(
        id="call_empty",
        type="function",
        function=ToolCallFunction(name="get_all", arguments="   "),
    )
    assert tool_call_empty.parse_arguments() == {}


def test_tool_call_parse_arguments_malformed():
    """Verifies ToolCall raises LLMResponseError on malformed arguments JSON."""
    tool_call = ToolCall(
        id="call_bad",
        type="function",
        function=ToolCallFunction(name="test", arguments="{not-json"),
    )
    with pytest.raises(LLMResponseError, match="Malformed JSON arguments in tool call 'test'"):
        tool_call.parse_arguments()


def test_tool_call_parse_arguments_non_dict():
    """Verifies ToolCall raises LLMResponseError if arguments JSON is not an object."""
    tool_call = ToolCall(
        id="call_scalar",
        type="function",
        function=ToolCallFunction(name="test", arguments="42"),
    )
    with pytest.raises(LLMResponseError, match="Arguments must deserialize to a JSON object"):
        tool_call.parse_arguments()


# =====================================================================
# 4. TokenUsage & LLMRequest Tests
# =====================================================================

def test_token_usage_auto_compute_total():
    """Verifies TokenUsage automatically computes total_tokens when not given."""
    usage = TokenUsage(prompt_tokens=40, completion_tokens=15)
    assert usage.prompt_tokens == 40
    assert usage.completion_tokens == 15
    assert usage.total_tokens == 55

    # If explicitly given, preserves value
    usage_explicit = TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=25)
    assert usage_explicit.total_tokens == 25


def test_token_usage_negative_rejected():
    """Verifies negative token values are rejected."""
    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=-1)


def test_llm_request_validation():
    """Verifies LLMRequest schema and temperature/token boundaries."""
    req = LLMRequest(
        messages=[ChatMessage.user("Hi")],
        temperature=0.7,
        max_tokens=256,
        model="llama-3.1-70b-versatile",
    )
    assert len(req.messages) == 1
    assert req.temperature == 0.7
    assert req.max_tokens == 256
    assert req.model == "llama-3.1-70b-versatile"

    # Temperature cannot be < 0 or > 2.0
    with pytest.raises(ValidationError):
        LLMRequest(messages=[ChatMessage.user("Hi")], temperature=-0.1)
    with pytest.raises(ValidationError):
        LLMRequest(messages=[ChatMessage.user("Hi")], temperature=2.5)

    # Max tokens cannot be <= 0
    with pytest.raises(ValidationError):
        LLMRequest(messages=[ChatMessage.user("Hi")], max_tokens=0)

    # Messages list cannot be empty
    with pytest.raises(ValidationError):
        LLMRequest(messages=[])


# =====================================================================
# 5. LLMResponse Schema Tests
# =====================================================================

def test_llm_response_content_only():
    """Verifies LLMResponse validation with text content."""
    resp = LLMResponse(
        content="Response text",
        finish_reason="stop",
        model="test-model",
        provider="mock",
    )
    assert resp.content == "Response text"
    assert resp.has_tool_calls is False
    assert resp.finish_reason == "stop"


def test_llm_response_tool_calls_only():
    """Verifies LLMResponse validation with tool calls and no text content."""
    tool_call = ToolCall(
        id="call_1",
        type="function",
        function=ToolCallFunction(name="test", arguments="{}"),
    )
    resp = LLMResponse(
        content=None,
        tool_calls=[tool_call],
        finish_reason="tool_calls",
    )
    assert resp.content is None
    assert resp.has_tool_calls is True
    assert len(resp.tool_calls) == 1


def test_llm_response_empty_rejection():
    """Verifies LLMResponse rejects having neither text content nor tool calls."""
    with pytest.raises(ValidationError, match="cannot have both empty content and empty tool_calls"):
        LLMResponse(content=None, tool_calls=[])

    with pytest.raises(ValidationError, match="cannot have both empty content and empty tool_calls"):
        LLMResponse(content="   ", tool_calls=[])


# =====================================================================
# 6. Exception Hierarchy & Security Redaction Tests
# =====================================================================

def test_exception_inheritance():
    """Verifies all LLM exceptions inherit from LLMProviderError and AgentDeskException."""
    err = LLMProviderError("general error")
    assert isinstance(err, AgentDeskException)
    assert err.status_code == 502

    auth_err = LLMAuthenticationError()
    assert isinstance(auth_err, LLMProviderError)
    assert auth_err.status_code == 502

    rate_err = LLMRateLimitError(retry_after=5.0)
    assert isinstance(rate_err, LLMProviderError)
    assert rate_err.status_code == 429
    assert rate_err.retry_after == 5.0

    timeout_err = LLMTimeoutError(timeout_seconds=30.0)
    assert isinstance(timeout_err, LLMProviderError)
    assert timeout_err.status_code == 504
    assert timeout_err.timeout_seconds == 30.0

    resp_err = LLMResponseError()
    assert isinstance(resp_err, LLMProviderError)
    assert resp_err.status_code == 502


def test_exception_message_security_redaction():
    """Verifies sensitive provider credentials and tokens are redacted from exception messages."""
    # Bearer token redaction
    err = LLMProviderError("Request failed with header Bearer abcdef1234567890xyz")
    assert "abcdef1234567890xyz" not in str(err)
    assert "Bearer [REDACTED]" in str(err)

    # Groq API key redaction (gsk_...)
    err_groq = LLMAuthenticationError("Invalid API key gsk_1234567890abcdef1234567890")
    assert "gsk_1234567890abcdef1234567890" not in str(err_groq)
    assert "[REDACTED_API_KEY]" in str(err_groq)

    # OpenAI API key redaction (sk-... or sk-proj-...)
    err_openai = LLMAuthenticationError("Failed key sk-proj-1234567890abcdef1234567890")
    assert "sk-proj-1234567890abcdef1234567890" not in str(err_openai)
    assert "[REDACTED_API_KEY]" in str(err_openai)

    # Generic api_key= pattern redaction
    err_generic = LLMProviderError("Failed query: api_key=secret_value_12345")
    assert "secret_value_12345" not in str(err_generic)
    assert "api_key=[REDACTED]" in str(err_generic)

