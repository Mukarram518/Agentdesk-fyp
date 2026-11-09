"""Conversation database repository for managing conversation threads and lifecycle."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import (
    Conversation,
    ConversationChannel,
    ConversationStatus,
)
from app.models.message import Message


class ConversationRepository:
    """Repository handling persistence operations for Conversation entities."""

    async def create_conversation(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        channel: str = ConversationChannel.WEB.value,
        language: str = "en",
        status: str = ConversationStatus.ACTIVE.value,
        started_at: Optional[datetime] = None,
    ) -> Conversation:
        """Creates and flushes a new conversation record for a business without committing."""
        conversation = Conversation(
            business_id=business_id,
            channel=channel.strip() if channel else ConversationChannel.WEB.value,
            language=language.strip().lower() if language else "en",
            status=status.strip() if status else ConversationStatus.ACTIVE.value,
            started_at=started_at or datetime.now(timezone.utc),
        )
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)
        return conversation

    async def get_by_id(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        include_messages: bool = False,
    ) -> Optional[Conversation]:
        """Fetches a conversation by primary key strictly scoped to the tenant business."""
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.business_id == business_id,
        )
        if include_messages:
            stmt = stmt.options(selectinload(Conversation.messages))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_language(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        language: str,
    ) -> Optional[Conversation]:
        """Updates the conversation language while enforcing tenant isolation."""
        conversation = await self.get_by_id(db, business_id, conversation_id)
        if conversation is None:
            return None

        conversation.language = language.strip().lower()
        await db.flush()
        return conversation

    async def update_status(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        status: str,
    ) -> Optional[Conversation]:
        """Updates the conversation status while enforcing tenant isolation."""
        conversation = await self.get_by_id(db, business_id, conversation_id)
        if conversation is None:
            return None

        conversation.status = status.strip()
        await db.flush()
        return conversation

    async def close_conversation(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        status: str = ConversationStatus.COMPLETED.value,
        outcome: Optional[str] = None,
        summary: Optional[str] = None,
        ended_at: Optional[datetime] = None,
    ) -> Optional[Conversation]:
        """Marks a conversation as ended/closed with outcome and summary, enforcing tenant isolation."""
        conversation = await self.get_by_id(db, business_id, conversation_id)
        if conversation is None:
            return None

        conversation.status = status.strip() if status else ConversationStatus.COMPLETED.value
        conversation.outcome = outcome.strip() if outcome else None
        conversation.summary = summary.strip() if summary else None
        conversation.ended_at = ended_at or datetime.now(timezone.utc)
        await db.flush()
        return conversation

    async def update_conversation(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        language: Optional[str] = None,
        status: Optional[str] = None,
        ended_at: Optional[datetime] = None,
        outcome: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> Optional[Conversation]:
        """Updates arbitrary mutable fields of a conversation while enforcing tenant isolation."""
        conversation = await self.get_by_id(db, business_id, conversation_id)
        if conversation is None:
            return None

        if language is not None:
            conversation.language = language.strip().lower()
        if status is not None:
            conversation.status = status.strip()
        if ended_at is not None:
            conversation.ended_at = ended_at
        if outcome is not None:
            conversation.outcome = outcome.strip() if outcome else None
        if summary is not None:
            conversation.summary = summary.strip() if summary else None

        await db.flush()
        return conversation

    async def get_recent_messages(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        limit: int = 50,
    ) -> List[Message]:
        """Retrieves bounded recent message history for a conversation in chronological order.

        Tenant Isolation Guarantee:
        Joins with Conversation on Conversation.business_id to ensure that only messages
        belonging to the verified business tenant are ever returned.
        """
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.business_id == business_id,
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
        if limit > 0:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()  # Chronological order of the most recent N messages
        return messages

    async def list_by_business(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Conversation]:
        """Lists conversations belonging to a business with optional filtering and pagination."""
        stmt = (
            select(Conversation)
            .where(Conversation.business_id == business_id)
            .order_by(Conversation.created_at.desc())
        )
        if channel:
            stmt = stmt.where(Conversation.channel == channel)
        if status:
            stmt = stmt.where(Conversation.status == status)
        if limit > 0:
            stmt = stmt.limit(limit)
        if offset > 0:
            stmt = stmt.offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())


conversation_repository = ConversationRepository()
