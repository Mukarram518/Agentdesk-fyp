"""Pydantic schemas for AgentDesk Web Chat API (Phase 7).

Defines request and response schemas for the public web chat widget and dashboard:
- ChatMessageRequest: Input payload with mandatory client-generated request_id and 2000-char message limit.
- ChatMessageItem: Detailed representation of the generated assistant message turn.
- ChatMessageResponse: Documented chat turn response structure.
"""

from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessageRequest(BaseModel):
    """Payload for submitting a chat message turn via public widget or dashboard."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional conversation UUID. Omit or pass null for turn 1 of a new thread.",
        examples=["9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message text (1-2000 characters, non-empty).",
        examples=["What services do you provide?"],
    )
    request_id: uuid.UUID = Field(
        ...,
        description="Client-generated UUIDv4 for turnkey idempotency and replay safety.",
        examples=["4a1e9442-88ec-4b72-9b24-74a984a92c42"],
    )

    @field_validator("message", mode="before")
    @classmethod
    def validate_message_content(cls, v: str) -> str:
        """Validates that message is non-empty, non-whitespace, and does not exceed 2000 characters."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Message content cannot be empty or whitespace-only.")
        cleaned = v.strip()
        if len(cleaned) > 2000:
            raise ValueError("Message content cannot exceed 2000 characters.")
        return cleaned


class ChatMessageItem(BaseModel):
    """Assistant message turn details returned within the chat response."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: uuid.UUID = Field(
        ...,
        description="Unique message UUID.",
        examples=["c3d82a17-3bf9-4b6e-b6a3-2f0802c61d54"],
    )
    role: str = Field(
        default="assistant",
        description="Message role ('assistant' or 'user').",
        examples=["assistant"],
    )
    content: str = Field(
        ...,
        description="Message textual content.",
        examples=["We provide appointment booking and customer support."],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the message was recorded.",
    )


class ChatMessageResponse(BaseModel):
    """Documented response structure returned to chat clients."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    conversation_id: uuid.UUID = Field(
        ...,
        description="UUID of the active conversation thread.",
        examples=["9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"],
    )
    message: ChatMessageItem = Field(
        ...,
        description="Assistant reply message details.",
    )


class ChatPreviewTokenRequest(BaseModel):
    """Optional request payload for requesting a dashboard chat preview token."""

    model_config = ConfigDict(
        extra="forbid",
    )

    business_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional business UUID. Defaults to the user's active/primary business.",
        examples=["9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"],
    )


class ChatPreviewTokenResponse(BaseModel):
    """Response returned when an authorized business owner/admin obtains a dashboard preview token."""

    model_config = ConfigDict(
        extra="forbid",
    )

    token: str = Field(
        ...,
        description="Compact signed HMAC-SHA256 JWT widget preview token.",
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when the preview token expires.",
    )
