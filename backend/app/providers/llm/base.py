"""Abstract interface for LLM providers in AgentDesk.

Defines the asynchronous interface and contract for large language model inference,
guaranteeing full provider independence across Groq, OpenAI, Anthropic, and test mocks.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from app.providers.llm.schemas import ChatMessage, ToolDefinition, LLMResponse


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM provider implementations in AgentDesk must inherit from this class
    and implement the asynchronous `generate()` method.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier of the provider (e.g. 'groq', 'openai', 'mock')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model identifier (e.g. 'llama-3.1-70b-versatile', 'gpt-4o-mini')."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Asynchronously generates a response from the LLM given conversation messages and optional tools.

        Args:
            messages: Ordered sequence of conversation messages. Must contain at least one message.
            tools: Optional list of available tool definitions the model may invoke.
            temperature: Optional sampling temperature between 0.0 and 2.0.
            max_tokens: Optional upper bound on generated completion tokens.
            **kwargs: Additional provider-specific options passed to underlying client.

        Returns:
            A structured `LLMResponse` containing text content, requested tool calls, and metadata.

        Raises:
            LLMProviderError: If the provider encounters an unrecoverable failure.
            LLMAuthenticationError: If API credentials fail authentication.
            LLMRateLimitError: If provider rate limits or quotas are exceeded.
            LLMTimeoutError: If the inference request times out.
            LLMResponseError: If the response is malformed, empty, or fails schema validation.
            ValueError: If input messages or tools fail validation.
        """
        pass

    def validate_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Validates and ensures the messages list is valid for inference.

        Args:
            messages: List of ChatMessage objects to validate.

        Returns:
            The validated list of messages.

        Raises:
            ValueError: If messages is not a non-empty list of ChatMessage instances.
        """
        if not messages or not isinstance(messages, list):
            raise ValueError("Messages input must be a non-empty list of ChatMessage instances.")
        for idx, msg in enumerate(messages):
            if not isinstance(msg, ChatMessage):
                raise ValueError(
                    f"Message at index {idx} must be an instance of ChatMessage, got {type(msg).__name__}."
                )
        return messages

    def validate_tools(
        self,
        tools: Optional[List[ToolDefinition]],
    ) -> Optional[List[ToolDefinition]]:
        """Validates tool definitions ensuring proper structure and name uniqueness.

        Args:
            tools: Optional list of ToolDefinition objects.

        Returns:
            The validated list of tools, or None if tools was None or empty.

        Raises:
            ValueError: If tools is not a list of ToolDefinition instances or contains duplicate tool names.
        """
        if tools is None:
            return None
        if not isinstance(tools, list):
            raise ValueError("Tools input must be a list of ToolDefinition instances.")
        if not tools:
            return None

        seen_names = set()
        for idx, tool in enumerate(tools):
            if not isinstance(tool, ToolDefinition):
                raise ValueError(
                    f"Tool at index {idx} must be an instance of ToolDefinition, got {type(tool).__name__}."
                )
            name = tool.function.name
            if name in seen_names:
                raise ValueError(f"Duplicate tool definition name '{name}' at index {idx}.")
            seen_names.add(name)
        return tools

