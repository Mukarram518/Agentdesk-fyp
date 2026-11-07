"""Deterministic Mock LLM Provider for automated testing and CI (Phase 6.1B)."""

import json
from typing import Any, Dict, List, Optional, Union
import uuid

from app.providers.llm.base import LLMProvider
from app.providers.llm.schemas import (
    ChatMessage,
    LLMResponse,
    MessageRole,
    TokenUsage,
    ToolCall,
    ToolCallFunction,
    ToolDefinition,
)

DEFAULT_MOCK_PROVIDER_NAME = "mock"
DEFAULT_MOCK_MODEL_NAME = "mock-llm-model"
DEFAULT_MOCK_RESPONSE_TEXT = "Deterministic mock response from AgentDesk MockLLMProvider."


class MockLLMProvider(LLMProvider):
    """Deterministic Mock LLM Provider for unit and integration testing.

    Guarantees:
    - Never makes external network requests or calls third-party APIs.
    - Requires zero API keys, secrets, or environment credentials.
    - Deterministic: returns reproducible predefined responses or queued responses.
    - Supports configurable tool-call generations for testing tool routing and execution.
    - Tracks generation calls (messages, tools, kwargs) for test assertions.
    """

    def __init__(
        self,
        *,
        default_response: Optional[str] = None,
        responses: Optional[List[Union[str, LLMResponse]]] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        provider_name: str = DEFAULT_MOCK_PROVIDER_NAME,
        model_name: str = DEFAULT_MOCK_MODEL_NAME,
    ) -> None:
        self._provider_name = provider_name
        self._model_name = model_name
        self._default_response = default_response or DEFAULT_MOCK_RESPONSE_TEXT
        self._queued_responses: List[Union[str, LLMResponse]] = list(responses) if responses else []
        self._default_tool_calls: List[ToolCall] = list(tool_calls) if tool_calls else []
        self.call_count: int = 0
        self.calls: List[Dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        """Identifier of the mock provider."""
        return self._provider_name

    @property
    def model_name(self) -> str:
        """Identifier of the active mock model."""
        return self._model_name

    def set_default_response(self, text: str) -> None:
        """Updates the default text response when no queued responses remain."""
        if not text or not text.strip():
            raise ValueError("Default response text cannot be empty or whitespace-only.")
        self._default_response = text.strip()

    def add_response(self, response: Union[str, LLMResponse]) -> None:
        """Queues a predefined response for subsequent generate() invocations."""
        if isinstance(response, str):
            if not response.strip():
                raise ValueError("Response text cannot be empty or whitespace-only.")
            self._queued_responses.append(response.strip())
        elif isinstance(response, LLMResponse):
            self._queued_responses.append(response)
        else:
            raise ValueError(
                f"Response must be a str or LLMResponse instance, got {type(response).__name__}."
            )

    def add_tool_call_response(
        self,
        name: str,
        arguments: Union[Dict[str, Any], str],
        *,
        call_id: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        """Queues an LLMResponse that triggers a specific tool call."""
        if isinstance(arguments, dict):
            args_str = json.dumps(arguments)
        elif isinstance(arguments, str):
            args_str = arguments
        else:
            raise ValueError("Arguments must be a dict or a valid JSON string.")

        tool_call = ToolCall(
            id=call_id or f"mock_call_{uuid.uuid4().hex[:8]}",
            type="function",
            function=ToolCallFunction(name=name, arguments=args_str),
        )

        response = LLMResponse(
            content=content,
            tool_calls=[tool_call],
            finish_reason="tool_calls",
            model=self.model_name,
            provider=self.provider_name,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )
        self.add_response(response)

    def reset(self) -> None:
        """Resets call counters, tracked call history, and queued responses."""
        self.call_count = 0
        self.calls.clear()
        self._queued_responses.clear()

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Asynchronously returns a deterministic mock response."""
        # 1. Validate inputs using LLMProvider base methods
        validated_messages = self.validate_messages(messages)
        validated_tools = self.validate_tools(tools)

        # 2. Record invocation details
        self.call_count += 1
        call_info = {
            "messages": validated_messages,
            "tools": validated_tools,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": kwargs,
        }
        self.calls.append(call_info)

        # 3. Check if there are queued responses
        if self._queued_responses:
            next_resp = self._queued_responses.pop(0)
            if isinstance(next_resp, LLMResponse):
                return next_resp
            return LLMResponse(
                content=next_resp,
                finish_reason="stop",
                model=self.model_name,
                provider=self.provider_name,
                usage=TokenUsage(
                    prompt_tokens=len(validated_messages) * 10,
                    completion_tokens=max(1, len(next_resp.split())),
                ),
            )

        # 4. Check if default tool calls were configured
        if self._default_tool_calls:
            return LLMResponse(
                content=None,
                tool_calls=self._default_tool_calls,
                finish_reason="tool_calls",
                model=self.model_name,
                provider=self.provider_name,
                usage=TokenUsage(
                    prompt_tokens=len(validated_messages) * 10,
                    completion_tokens=15,
                ),
            )

        # 5. Default deterministic text response
        last_user_msg = next(
            (m for m in reversed(validated_messages) if m.role == MessageRole.USER),
            None,
        )
        if last_user_msg and last_user_msg.content:
            reply_text = f"{self._default_response} [Echo: {last_user_msg.content.strip()}]"
        else:
            reply_text = self._default_response

        return LLMResponse(
            content=reply_text,
            finish_reason="stop",
            model=self.model_name,
            provider=self.provider_name,
            usage=TokenUsage(
                prompt_tokens=len(validated_messages) * 8,
                completion_tokens=max(1, len(reply_text.split())),
            ),
        )

