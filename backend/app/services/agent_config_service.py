"""AgentConfig service coordinating agent configuration business logic and tenant validation."""

import uuid
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.agent_config import (
    AgentConfig,
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_TONE,
)
from app.repositories.agent_config import (
    AgentConfigRepository,
    agent_config_repository,
)
from app.schemas.agent_config import (
    AgentConfigUpdate,
    SUPPORTED_LANGUAGES,
    VALID_TONES,
)


class AgentConfigService:
    """Service encapsulating agent configuration operations and business validations."""

    def __init__(
        self,
        agent_config_repo: AgentConfigRepository = agent_config_repository,
    ) -> None:
        self.agent_config_repo = agent_config_repo

    async def get_or_create_config(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
    ) -> AgentConfig:
        """Retrieves or creates default agent configuration for a verified business tenant.

        Guarantees:
        - Strictly scoped to the authenticated business_id.
        - Automatically creates default configuration row if one does not exist.
        - Flushes and refreshes to ensure server-generated values (e.g. timestamps) are populated.
        - Never commits independently; caller / get_db dependency coordinates transaction.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Valid business_id is required.",
            )

        config = await self.agent_config_repo.get_by_business_id(db, business_id)
        if config is None:
            logger.info(f"Initializing default agent configuration for business {business_id}")
            config = await self.agent_config_repo.create_default(db, business_id=business_id)
            await db.flush()
            await db.refresh(config)

        return config

    async def get_config(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
    ) -> Optional[AgentConfig]:
        """Retrieves agent configuration for a business without creating a default if absent.

        Useful for read-only checks, orchestrator context loading, or existence verification.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Valid business_id is required.",
            )
        return await self.agent_config_repo.get_by_business_id(db, business_id)

    async def update_config(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        payload: AgentConfigUpdate,
    ) -> AgentConfig:
        """Updates agent configuration fields for a verified business tenant.

        Guarantees:
        - Strictly scoped to the authenticated business_id.
        - Validates allowed fields and configuration values.
        - Automatically initializes default config if none existed prior to update.
        - Updates only explicitly supplied fields (exclude_unset=True).
        - Flushes and refreshes within the current transaction without committing independently.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Valid business_id is required.",
            )

        # 1. Ensure config row exists (lazy creation on first access/update)
        config = await self.get_or_create_config(db, business_id)

        # 2. Extract explicitly set fields
        updates: Dict[str, Any] = payload.model_dump(exclude_unset=True)
        if not updates:
            return config

        # 3. Defensive validation on fields
        if "tone" in updates and updates["tone"] is not None:
            tone_val = str(updates["tone"]).strip().lower()
            if tone_val not in VALID_TONES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid tone '{updates['tone']}'. Allowed tones: {', '.join(sorted(VALID_TONES))}.",
                )
            updates["tone"] = tone_val

        if "language_priority" in updates and updates["language_priority"] is not None:
            langs = updates["language_priority"]
            if not isinstance(langs, (list, tuple)) or len(langs) == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="language_priority must be a non-empty list of supported language codes.",
                )
            cleaned_langs = []
            for lang in langs:
                cleaned_code = str(lang).strip().lower()
                if cleaned_code not in SUPPORTED_LANGUAGES:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Unsupported language code '{lang}'. Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}.",
                    )
                if cleaned_code not in cleaned_langs:
                    cleaned_langs.append(cleaned_code)
            updates["language_priority"] = cleaned_langs

        if "greeting" in updates and updates["greeting"] is not None:
            greeting_val = str(updates["greeting"]).strip()
            if len(greeting_val) > 1000:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="greeting cannot exceed 1000 characters.",
                )
            updates["greeting"] = greeting_val if greeting_val else None

        if "voice_id" in updates and updates["voice_id"] is not None:
            voice_val = str(updates["voice_id"]).strip()
            if len(voice_val) > 100:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="voice_id cannot exceed 100 characters.",
                )
            updates["voice_id"] = voice_val if voice_val else None

        # 4. Delegate to repository
        updated_config = await self.agent_config_repo.update(
            db=db,
            business_id=business_id,
            **updates,
        )
        if updated_config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent configuration could not be found.",
            )

        await db.flush()
        await db.refresh(updated_config)
        return updated_config


# Default singleton instance
agent_config_service = AgentConfigService()

