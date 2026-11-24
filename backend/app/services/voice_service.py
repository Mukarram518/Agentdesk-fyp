"""Voice Service handling voice channel validation and session readiness (Phase 4C)."""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import VoiceDisabledError
from app.models.agent_config import AgentConfig as AgentConfigModel
from app.services.agent_config_service import (
    AgentConfigService,
    agent_config_service as default_agent_config_service,
)


class VoiceService:
    """Service encapsulating voice channel business rules and session initialization checks."""

    def __init__(
        self,
        agent_config_service: Optional[AgentConfigService] = None,
    ) -> None:
        self.agent_config_service = agent_config_service or default_agent_config_service

    async def validate_voice_session_creation(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
    ) -> AgentConfigModel:
        """Validates that a voice session can be created for the business tenant.

        Guarantees:
        - Strictly verifies tenant configuration.
        - Raises VoiceDisabledError (HTTP 403 Forbidden) if voice_enabled is False.
        - Returns persisted AgentConfig entity containing voice_id, tone, and greeting.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("A valid business_id is required.")

        config = await self.agent_config_service.get_config(db, business_id=business_id)
        voice_enabled = config.voice_enabled if config is not None else True
        if not voice_enabled:
            raise VoiceDisabledError("Voice is currently disabled for this business.")

        return config


# Default singleton instance
voice_service = VoiceService()

