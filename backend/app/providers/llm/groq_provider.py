"""Production-ready Groq LLM Adapter for AgentDesk (Phase 6.1C).

Implements the LLMProvider interface using the official asynchronous Groq Python SDK.
Guarantees strict tenant-isolation compatibility, credential safety, and robust error handling.
"""

import logging
from typing import Any, Dict, List, Optional
import uuid

import groq
from groq import AsyncGroq
from groq import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    GroqError,
    RateLimitError,
)

from app.core.config import get_settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.exceptions import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.providers.llm.schemas import (
    ChatMessage,
    LLMResponse,
    MessageRole,
    TokenUsage,
    ToolCall,
    ToolCallFunction,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

DEFAULT_GROQ_PROVIDER_NAME = "groq"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_TIMEOUT_SECONDS = 30.0
DEFAULT_GROQ_MAX_RETRIES = 2


class GroqProvider(LLMProvider):
    """Asynchronous Groq LLM Provider adapter.

    Translates AgentDesk standard ChatMessages and ToolDefinitions into the Groq API format
    and maps Groq responses back to standard LLMResponse objects.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        client: Optional[AsyncGroq] = None,
    ) -> None:
        """Initializes the Groq provider adapter.

        Args:
            api_key: Optional Groq API key. If omitted, reads GROQ_API_KEY from application settings.
            model_name: Optional model identifier. Defaults to GROQ_MODEL in settings or Llama 3.3.
            timeout_seconds: Optional request timeout in seconds.
            max_retries: Optional maximum retries for transient errors.
            client: Optional pre-configured AsyncGroq instance (useful for dependency injection and tests).

        Raises:
            LLMAuthenticationError: If no API key is provided or configured in settings.
        """
        settings = get_settings()

        self._model_name = model_name or getattr(settings, "GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "GROQ_TIMEOUT_SECONDS", DEFAULT_GROQ_TIMEOUT_SECONDS)
        )
        self._max_retries = (
            max_retries
            if max_retries is not None
            else getattr(settings, "GROQ_MAX_RETRIES", DEFAULT_GROQ_MAX_RETRIES)
        )

        if client is not None:
            self._client = client
        else:
            resolved_key = api_key or getattr(settings, "GROQ_API_KEY", None)
            if not resolved_key or not resolved_key.strip():
                raise LLMAuthenticationError(
                    "GROQ_API_KEY is not configured. Please configure GROQ_API_KEY in environment or settings.",
                    provider_name=DEFAULT_GROQ_PROVIDER_NAME,
                )
            self._client = AsyncGroq(
                api_key=resolved_key.strip(),
                timeout=self._timeout_seconds,
                max_retries=self._max_retries,
            )

    @property
    def provider_name(self) -> str:
        """Identifier of the provider."""
        return DEFAULT_GROQ_PROVIDER_NAME

    @property
    def model_name(self) -> str:
        """Active model identifier."""
        return self._model_name

    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Converts AgentDesk ChatMessages into Groq chat completion messages."""
        groq_messages: List[Dict[str, Any]] = []

        for m in messages:
            if m.role == MessageRole.SYSTEM:
                msg: Dict[str, Any] = {"role": "system", "content": m.content}
                if m.name:
                    msg["name"] = m.name
                groq_messages.append(msg)

            elif m.role == MessageRole.USER:
                msg = {"role": "user", "content": m.content}
                if m.name:
                    msg["name"] = m.name
                groq_messages.append(msg)

            elif m.role == MessageRole.ASSISTANT:
                msg = {"role": "assistant"}
                if m.content is not None:
                    msg["content"] = m.content
                if m.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in m.tool_calls
                    ]
                if m.name:
                    msg["name"] = m.name
                groq_messages.append(msg)

            elif m.role == MessageRole.TOOL:
                msg = {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content or "",
                }
                if m.name:
                    msg["name"] = m.name
                groq_messages.append(msg)

        return groq_messages

    def _convert_tools(
        self, tools: Optional[List[ToolDefinition]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Converts AgentDesk ToolDefinitions into Groq tool dictionaries."""
        if not tools:
            return None

        return [
            {
                "type": "function",
                "function": {
                    "name": t.function.name,
                    "description": t.function.description,
                    "parameters": t.function.parameters,
                },
            }
            for t in tools
        ]

    def _parse_groq_response(self, response: Any) -> LLMResponse:
        """Parses a Groq ChatCompletion into a standard LLMResponse."""
        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMResponseError(
                "Groq completion response contains no choices.",
                provider_name=self.provider_name,
            )

        choice = choices[0]
        message = getattr(choice, "message", None)
        if not message:
            raise LLMResponseError(
                "Groq choice contains no message payload.",
                provider_name=self.provider_name,
            )

        content = getattr(message, "content", None)
        finish_reason = getattr(choice, "finish_reason", "stop")

        # Map tool calls if present
        mapped_tool_calls: List[ToolCall] = []
        raw_tool_calls = getattr(message, "tool_calls", None)
        if raw_tool_calls:
            for tc in raw_tool_calls:
                fn = getattr(tc, "function", None)
                if not fn:
                    raise LLMResponseError(
                        "Malformed tool call in Groq response: missing function object.",
                        provider_name=self.provider_name,
                    )
                fn_name = getattr(fn, "name", None)
                if not fn_name:
                    raise LLMResponseError(
                        "Malformed tool call in Groq response: missing function name.",
                        provider_name=self.provider_name,
                    )
                fn_args = getattr(fn, "arguments", "") or "{}"
                mapped_tool_calls.append(
                    ToolCall(
                        id=getattr(tc, "id", None) or f"call_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=ToolCallFunction(
                            name=fn_name,
                            arguments=fn_args,
                        ),
                    )
                )

        # Map token usage if present
        usage_obj = getattr(response, "usage", None)
        token_usage: Optional[TokenUsage] = None
        if usage_obj:
            token_usage = TokenUsage(
                prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage_obj, "completion_tokens", 0) or 0,
                total_tokens=getattr(usage_obj, "total_tokens", 0) or 0,
            )

        try:
            return LLMResponse(
                content=content,
                tool_calls=mapped_tool_calls,
                finish_reason=finish_reason,
                usage=token_usage,
                model=getattr(response, "model", None) or self.model_name,
                provider=self.provider_name,
            )
        except Exception as exc:
            raise LLMResponseError(
                f"Groq response failed standard schema validation: {exc}",
                provider_name=self.provider_name,
            ) from exc

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Asynchronously executes inference via the Groq Chat Completions API.

        Args:
            messages: Ordered sequence of conversation messages.
            tools: Optional tool definitions available for the model to invoke.
            temperature: Sampling temperature between 0.0 and 2.0.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional options forwarded to Groq SDK.

        Returns:
            A structured LLMResponse instance.

        Raises:
            LLMAuthenticationError: On credential or unauthorized failures.
            LLMRateLimitError: On rate-limit or quota limits.
            LLMTimeoutError: On inference request timeouts.
            LLMProviderError: On network or server connection failures.
            LLMResponseError: On malformed or empty completions.
            ValueError: On invalid input messages or tools.
        """
        validated_messages = self.validate_messages(messages)
        validated_tools = self.validate_tools(tools)

        groq_messages = self._convert_messages(validated_messages)
        groq_tools = self._convert_tools(validated_tools)

        request_kwargs: Dict[str, Any] = {
            "model": kwargs.pop("model", self.model_name),
            "messages": groq_messages,
        }

        if groq_tools is not None:
            request_kwargs["tools"] = groq_tools

        if temperature is not None:
            request_kwargs["temperature"] = temperature

        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens

        # Merge any additional legitimate parameters
        request_kwargs.update(kwargs)

        try:
            response = await self._client.chat.completions.create(**request_kwargs)
            return self._parse_groq_response(response)

        except AuthenticationError as exc:
            raise LLMAuthenticationError(
                f"Groq authentication error: {exc}",
                provider_name=self.provider_name,
            ) from exc

        except RateLimitError as exc:
            retry_after = getattr(exc, "retry_after", None)
            raise LLMRateLimitError(
                f"Groq rate limit exceeded: {exc}",
                provider_name=self.provider_name,
                retry_after=retry_after,
            ) from exc

        except APITimeoutError as exc:
            raise LLMTimeoutError(
                f"Groq request timed out: {exc}",
                provider_name=self.provider_name,
                timeout_seconds=self._timeout_seconds,
            ) from exc

        except APIConnectionError as exc:
            raise LLMProviderError(
                f"Groq connection failure: {exc}",
                provider_name=self.provider_name,
                status_code=503,
            ) from exc

        except APIResponseValidationError as exc:
            raise LLMResponseError(
                f"Groq response validation error: {exc}",
                provider_name=self.provider_name,
            ) from exc

        except (BadRequestError, APIStatusError) as exc:
            status_code = getattr(exc, "status_code", 502)
            raise LLMProviderError(
                f"Groq API error ({status_code}): {exc}",
                provider_name=self.provider_name,
                status_code=status_code,
            ) from exc

        except GroqError as exc:
            raise LLMProviderError(
                f"Groq SDK failure: {exc}",
                provider_name=self.provider_name,
                status_code=502,
            ) from exc

        except (LLMProviderError, ValueError):
            raise

        except Exception as exc:
            raise LLMProviderError(
                f"Unexpected failure communicating with Groq: {exc}",
                provider_name=self.provider_name,
                status_code=502,
            ) from exc

