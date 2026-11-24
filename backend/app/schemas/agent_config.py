"""Pydantic schemas for AgentConfig entities and update payloads."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.agent_config import (
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_TONE,
)

VALID_TONES = frozenset({"helpful", "professional", "friendly", "direct"})
SUPPORTED_LANGUAGES = frozenset({"en", "ur"})


class AgentConfigResponse(BaseModel):
    """Public agent configuration representation returned to authenticated users."""

    business_id: uuid.UUID
    voice_enabled: bool
    chat_enabled: bool
    lead_enabled: bool
    voice_id: Optional[str] = None
    tone: str
    greeting: Optional[str] = None
    language_priority: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    @classmethod
    def from_orm_entry(cls, config) -> "AgentConfigResponse":
        """Factory method constructing AgentConfigResponse from an ORM AgentConfig model."""
        return cls(
            business_id=config.business_id,
            voice_enabled=config.voice_enabled,
            chat_enabled=config.chat_enabled,
            lead_enabled=config.lead_enabled,
            voice_id=config.voice_id,
            tone=config.tone,
            greeting=config.greeting,
            language_priority=list(config.language_priority or DEFAULT_LANGUAGE_PRIORITY),
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


class AgentConfigUpdate(BaseModel):
    """Payload for updating agent configuration settings."""

    voice_enabled: Optional[bool] = None
    chat_enabled: Optional[bool] = None
    lead_enabled: Optional[bool] = None
    voice_id: Optional[str] = Field(None, max_length=100)
    tone: Optional[str] = Field(None, max_length=50)
    greeting: Optional[str] = Field(None, max_length=1000)
    language_priority: Optional[List[str]] = None

    model_config = {
        "extra": "forbid",
    }

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Tone cannot be empty. Allowed tones: helpful, professional, friendly, direct.")
        if cleaned not in VALID_TONES:
            raise ValueError(
                f"Invalid tone '{v}'. Allowed tones are: {', '.join(sorted(VALID_TONES))}."
            )
        return cleaned

    @field_validator("greeting")
    @classmethod
    def validate_greeting(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        if len(cleaned) > 1000:
            raise ValueError("Greeting message cannot exceed 1000 characters.")
        return cleaned

    @field_validator("voice_id")
    @classmethod
    def validate_voice_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        if len(cleaned) > 100:
            raise ValueError("Voice ID cannot exceed 100 characters.")
        return cleaned

    @field_validator("language_priority")
    @classmethod
    def validate_language_priority(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        if not isinstance(v, (list, tuple)) or len(v) == 0:
            raise ValueError("Language priority must be a non-empty list of supported languages (e.g. ['en', 'ur']).")

        cleaned_list: List[str] = []
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("Language priority codes must be non-empty strings.")
            code = item.strip().lower()
            if code not in SUPPORTED_LANGUAGES:
                raise ValueError(
                    f"Unsupported language code '{item}'. Supported languages are: {', '.join(sorted(SUPPORTED_LANGUAGES))}."
                )
            if code not in cleaned_list:
                cleaned_list.append(code)

        if not cleaned_list:
            raise ValueError("Language priority must contain at least one valid language code.")
        return cleaned_list

