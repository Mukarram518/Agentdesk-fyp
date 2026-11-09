"""Message database repository for managing individual conversation turns."""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message, MessageRole


class MessageRepository:
    """Repository handling persistence operations for Message entities."""

    async def create_message(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        request_id: Optional[uuid.UUID] = None,
        business_id: Optional[uuid.UUID] = None,
        reply_to_id: Optional[uuid.UUID] = None,
    ) -> Message:
        """Creates and flushes a new message record without committing.

        Multi-Tenancy & Integrity Rules:
        - Resolves business_id from conversation if not explicitly provided.
        - Role must be 'user' or 'assistant'.
        - Content must be non-empty text.
        - reply_to_id can only be set on assistant messages.
        - Flushes to session to generate ID and trigger DB checks, but never commits.
        """
        normalized_role = role.strip().lower() if role else ""
        if normalized_role not in (MessageRole.USER.value, MessageRole.ASSISTANT.value):
            raise ValueError(f"Invalid message role '{role}'. Must be 'user' or 'assistant'.")

        normalized_content = content.strip() if content else ""
        if not normalized_content:
            raise ValueError("Message content cannot be empty or whitespace-only.")

        if reply_to_id is not None and normalized_role != MessageRole.ASSISTANT.value:
            raise ValueError("Only assistant messages can have a reply_to_id set.")

        # Resolve business_id from parent conversation if not explicitly supplied
        effective_business_id = business_id
        if effective_business_id is None:
            stmt = select(Conversation.business_id).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            resolved = result.scalar_one_or_none()
            if resolved is None:
                raise ValueError(f"Conversation with id '{conversation_id}' does not exist.")
            effective_business_id = resolved

        message = Message(
            conversation_id=conversation_id,
            business_id=effective_business_id,
            role=normalized_role,
            content=normalized_content,
            request_id=request_id,
            reply_to_id=reply_to_id,
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)
        return message

    async def get_by_id(
        self,
        db: AsyncSession,
        message_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        business_id: Optional[uuid.UUID] = None,
    ) -> Optional[Message]:
        """Fetches a message by primary key, optionally scoped to a conversation and business."""
        stmt = select(Message).where(Message.id == message_id)
        if conversation_id is not None:
            stmt = stmt.where(Message.conversation_id == conversation_id)
        if business_id is not None:
            stmt = stmt.where(Message.business_id == business_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_business_request_id(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> Optional[Message]:
        """Retrieves a message strictly scoped to tenant ID and request ID.

        Enforces tenant isolation by never performing an unscoped request-ID lookup.
        """
        stmt = select(Message).where(
            Message.business_id == business_id,
            Message.request_id == request_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_request_id(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        request_id: uuid.UUID,
        business_id: Optional[uuid.UUID] = None,
    ) -> Optional[Message]:
        """Fetches a message by conversation_id and request_id, with optional business scoping."""
        stmt = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.request_id == request_id,
        )
        if business_id is not None:
            stmt = stmt.where(Message.business_id == business_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def has_request_id(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        request_id: uuid.UUID,
        business_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Checks whether a request_id already exists for a conversation."""
        return (await self.get_by_request_id(db, conversation_id, request_id, business_id=business_id)) is not None

    async def get_reply_by_user_message_id(
        self,
        db: AsyncSession,
        user_message_id: uuid.UUID,
    ) -> Optional[Message]:
        """Retrieves the assistant reply linked to a specific user message via reply_to_id."""
        stmt = select(Message).where(
            Message.reply_to_id == user_message_id,
            Message.role == MessageRole.ASSISTANT.value,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_messages_for_conversation(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        business_id: Optional[uuid.UUID] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Message]:
        """Retrieves messages for a conversation in chronological order.

        Enforces tenant isolation by verifying ownership against business_id.
        """
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if business_id is not None:
            stmt = stmt.where(Message.business_id == business_id)
        stmt = stmt.order_by(Message.created_at.asc(), Message.id.asc())

        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)
        if offset > 0:
            stmt = stmt.offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_message_idempotent(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        request_id: Optional[uuid.UUID] = None,
        business_id: Optional[uuid.UUID] = None,
        reply_to_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Message, bool]:
        """Creates a message with safe idempotency semantics using database constraints.

        Returns:
            Tuple[Message, bool]: (message, created)
            - If request_id is None: creates the message and returns (message, True).
            - If request_id already exists: returns the existing message and False.
            - If request_id does not exist: creates the message. In the event of a concurrent race
              condition triggering a unique constraint violation on (business_id, request_id),
              the nested transaction (savepoint) cleanly rolls back and retrieves the existing record,
              returning (existing_message, False).
        """
        if request_id is None:
            msg = await self.create_message(
                db=db,
                conversation_id=conversation_id,
                business_id=business_id,
                role=role,
                content=content,
                request_id=None,
                reply_to_id=reply_to_id,
            )
            return msg, True

        # Resolve business_id if not passed
        effective_business_id = business_id
        if effective_business_id is None:
            stmt = select(Conversation.business_id).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            effective_business_id = result.scalar_one_or_none()
            if effective_business_id is None:
                raise ValueError(f"Conversation with id '{conversation_id}' does not exist.")

        # 1. Pre-check if record already exists for this tenant
        existing = await self.get_by_business_request_id(db, effective_business_id, request_id)
        if existing is not None:
            return existing, False

        # 2. Attempt creation in nested transaction (savepoint) to safely handle concurrent races
        try:
            async with db.begin_nested():
                msg = await self.create_message(
                    db=db,
                    conversation_id=conversation_id,
                    business_id=effective_business_id,
                    role=role,
                    content=content,
                    request_id=request_id,
                    reply_to_id=reply_to_id,
                )
                return msg, True
        except IntegrityError:
            # Concurrently created by another request with the same request_id
            existing = await self.get_by_business_request_id(db, effective_business_id, request_id)
            if existing is not None:
                return existing, False
            raise

    async def create_assistant_reply_idempotent(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        content: str,
        reply_to_id: uuid.UUID,
    ) -> Tuple[Message, bool]:
        """Creates an assistant reply linked to its user message with strict 1-to-1 idempotency.

        Guarantees:
        - Scoped to conversation_id and business_id via composite FK.
        - reply_to_id links directly to the parent user message.
        - Uses a nested transaction (savepoint) to safely catch unique constraint conflicts
          on uq_messages_reply_to_id.
        - If another concurrent transaction already committed or created the reply,
          safely rolls back to savepoint and returns (existing_assistant_message, False).
        - Repository flushes but never commits.

        Returns:
            Tuple[Message, bool]: (assistant_message, created)
        """
        # 1. Pre-check if reply already exists
        existing = await self.get_reply_by_user_message_id(db, reply_to_id)
        if existing is not None:
            return existing, False

        # 2. Attempt creation in nested transaction (savepoint)
        try:
            async with db.begin_nested():
                msg = await self.create_message(
                    db=db,
                    conversation_id=conversation_id,
                    business_id=business_id,
                    role=MessageRole.ASSISTANT.value,
                    content=content,
                    request_id=None,
                    reply_to_id=reply_to_id,
                )
                return msg, True
        except IntegrityError:
            # Concurrently created by another worker
            existing = await self.get_reply_by_user_message_id(db, reply_to_id)
            if existing is not None:
                return existing, False
            raise


message_repository = MessageRepository()
