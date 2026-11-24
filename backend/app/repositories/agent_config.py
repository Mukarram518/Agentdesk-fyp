"""AgentConfig database repository handling tenant-scoped agent configurations."""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_config import (
    AgentConfig,
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_TONE,
)


class AgentConfigRepository:
    """Repository handling persistence operations for AgentConfig entities."""

    async def get_by_business_id(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
    ) -> Optional[AgentConfig]:
        """Fetches the agent configuration for a specific business.

        Strictly tenant-scoped by business_id.
        """
        stmt = select(AgentConfig).where(AgentConfig.business_id == business_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_default(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        voice_enabled: bool = True,
        chat_enabled: bool = True,
        lead_enabled: bool = True,
        voice_id: Optional[str] = None,
        tone: str = DEFAULT_TONE,
        greeting: Optional[str] = None,
        language_priority: Optional[List[str]] = None,
    ) -> AgentConfig:
        """Creates and flushes a default agent configuration for a business.

        Does not commit independently; caller coordinates transaction.
        """
        config = AgentConfig(
            business_id=business_id,
            voice_enabled=voice_enabled,
            chat_enabled=chat_enabled,
            lead_enabled=lead_enabled,
            voice_id=voice_id,
            tone=tone.strip() if tone else DEFAULT_TONE,
            greeting=greeting.strip() if greeting and greeting.strip() else None,
            language_priority=(
                list(language_priority)
                if language_priority is not None
                else list(DEFAULT_LANGUAGE_PRIORITY)
            ),
        )
        db.add(config)
        await db.flush()
        return config

    async def get_or_create_default(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
    ) -> AgentConfig:
        """Retrieves existing configuration or creates a default one if absent.

        Guarantees:
        - Strictly scoped to business_id.
        - Does not commit independently.
        """
        existing = await self.get_by_business_id(db, business_id)
        if existing is not None:
            return existing
        return await self.create_default(db, business_id)

    async def update(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        **updates: Any,
    ) -> Optional[AgentConfig]:
        """Updates agent configuration fields for a specific business.

        Guarantees:
        - Strictly scoped to the specified business_id.
        - Flushes changes without committing independently.
        - Returns updated AgentConfig or None if not found.
        """
        config = await self.get_by_business_id(db, business_id)
        if config is None:
            return None

        allowed_fields = {
            "voice_enabled",
            "chat_enabled",
            "lead_enabled",
            "voice_id",
            "tone",
            "greeting",
            "language_priority",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                if field == "tone" and isinstance(value, str):
                    setattr(config, field, value.strip() if value.strip() else DEFAULT_TONE)
                elif field == "greeting" and isinstance(value, str):
                    setattr(config, field, value.strip() if value.strip() else None)
                elif field == "language_priority" and isinstance(value, (list, tuple)):
                    setattr(config, field, list(value))
                else:
                    setattr(config, field, value)

        await db.flush()
        return config


# Default singleton instance
agent_config_repository = AgentConfigRepository()

