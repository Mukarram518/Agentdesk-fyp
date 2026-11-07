"""Pydantic schemas and enums for the AgentDesk AI Orchestrator."""

from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator

from app.providers.llm.schemas import ChatMessage, ToolCall, TokenUsage


class ChannelType(str, Enum):
    """Supported customer communication channels."""

    WEB = "web"
    WHATSAPP = "whatsapp"
    VOICE = "voice"


class LanguageCode(str, Enum):
    """Supported conversation and content languages."""

    EN = "en"
    UR = "ur"
    MIXED = "mixed"


class IntentType(str, Enum):
    """Classified customer interaction intents."""

    FAQ = "faq"
    LEAD = "lead"
    APPOINTMENT = "appointment"
    GENERAL = "general"
    UNKNOWN = "unknown"


class AgentType(str, Enum):
    """Specialized agent types handling customer interactions."""

    CHAT = "chat"
    LEAD = "lead"
    BOOKING = "booking"
    VOICE = "voice"


class AgentConfig(BaseModel):
    """In-memory configuration representation for business agents."""

    business_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Associated business/tenant UUID",
    )
    voice_enabled: bool = Field(
        default=True,
        description="Whether the voice agent channel is enabled",
    )
    chat_enabled: bool = Field(
        default=True,
        description="Whether the web/chat agent is enabled",
    )
    lead_enabled: bool = Field(
        default=True,
        description="Whether the lead capture agent is enabled",
    )
    voice_id: Optional[str] = Field(
        default=None,
        description="Configured voice synthesis identifier (e.g. ElevenLabs voice ID)",
    )
    tone: str = Field(
        default="helpful",
        description="Tone of voice for agent responses (e.g. helpful, professional, friendly)",
    )
    greeting: Optional[str] = Field(
        default=None,
        description="Custom business greeting message",
    )
    language_priority: List[str] = Field(
        default_factory=lambda: ["en", "ur"],
        description="Ordered list of preferred language codes",
    )


class AgentTurnInput(BaseModel):
    """Normalized input payload for an AI orchestrator turn."""

    business_id: uuid.UUID = Field(
        ...,
        description="Target business/tenant UUID",
    )
    channel: ChannelType = Field(
        ...,
        description="Originating communication channel (web, whatsapp, voice)",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Customer message text",
    )
    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional conversation UUID if part of an existing thread",
    )
    customer_id: Optional[str] = Field(
        default=None,
        description="Optional customer phone or identifier",
    )
    language: Optional[LanguageCode] = Field(
        default=None,
        description="Explicit or pre-detected language code",
    )
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversation message history",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific or turn metadata",
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        """Ensures the customer message contains non-whitespace text."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Customer message cannot be empty or whitespace only.")
        return cleaned


class AgentTurnOutput(BaseModel):
    """Structured response produced by the AI orchestrator."""

    response: str = Field(
        ...,
        min_length=1,
        description="Generated response text for the customer",
    )
    language: LanguageCode = Field(
        ...,
        description="Language code of the response",
    )
    intent: IntentType = Field(
        ...,
        description="Classified customer intent for this turn",
    )
    agent: AgentType = Field(
        ...,
        description="Agent that resolved or generated the turn",
    )
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description="Tools invoked or requested during turn processing",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for intent routing or retrieval (0.0 to 1.0)",
    )
    sources: List[uuid.UUID] = Field(
        default_factory=list,
        description="Knowledge base entry or chunk UUIDs used to inform the response",
    )
    usage: Optional[TokenUsage] = Field(
        default=None,
        description="Token consumption statistics for this turn",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional turn metadata or diagnostics",
    )

    @field_validator("response")
    @classmethod
    def validate_response_not_empty(cls, v: str) -> str:
        """Ensures the output response contains non-whitespace text."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Agent response cannot be empty or whitespace only.")
        return cleaned

