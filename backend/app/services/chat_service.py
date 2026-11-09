"""AgentDesk Web Chat Service.

Coordinates the end-to-end multi-agent chat turn:
1. Distributed lock acquisition per (business_id, request_id) preventing concurrent duplicate turns.
2. Tenant-scoped conversation retrieval or creation.
3. Database-enforced request idempotency and first-turn recovery.
4. Two-transaction database safety (commits user message before non-transactional AI inference).
5. AI Orchestrator turn execution with safe customer-facing fallbacks.
6. Lease-loss verification before assistant response persistence.
7. Idempotent assistant reply recording linked via reply_to_id.
8. Sanitized customer response generation matching ChatMessageResponse.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.distributed_lock import (
    DistributedLock,
    LeaseLostError,
    LockAcquisitionError,
    LockConnectionError,
)
from app.core.exceptions import AgentDeskException, ServiceUnavailableError
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.orchestrator.schemas import (
    AgentTurnInput,
    AgentTurnOutput,
    ChannelType,
)
from app.orchestrator.service import AIOrchestrator
from app.providers.llm.schemas import ChatMessage, MessageRole as LLMMessageRole
from app.repositories.conversation_repository import (
    ConversationRepository,
    conversation_repository,
)
from app.repositories.message_repository import (
    MessageRepository,
    message_repository,
)
from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageRequest,
    ChatMessageResponse,
)

logger = logging.getLogger(__name__)


# =====================================================================
# Domain Exceptions
# =====================================================================

class ChatServiceError(AgentDeskException):
    """Base exception for chat service failures."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message=message, status_code=status_code)


class ChatLockTimeoutError(ChatServiceError):
    """Raised when chat turn coordination lock cannot be acquired within the timeout."""

    def __init__(self, message: str = "Chat coordination timeout. Please retry shortly."):
        super().__init__(message=message, status_code=503)


class ChatLeaseLostError(ChatServiceError):
    """Raised when the worker's lock lease was lost or expired during inference."""

    def __init__(self, message: str = "Distributed lock lease expired during processing. Persistence aborted."):
        super().__init__(message=message, status_code=503)


class ConversationNotFoundError(ChatServiceError):
    """Raised when a specified conversation does not exist or does not belong to the authorized business."""

    def __init__(self, message: str = "Conversation not found or access denied."):
        super().__init__(message=message, status_code=404)


# =====================================================================
# ChatService Implementation
# =====================================================================

class ChatService:
    """Service encapsulating end-to-end chat turn coordination and persistence."""

    def __init__(
        self,
        conversation_repo: ConversationRepository = conversation_repository,
        message_repo: MessageRepository = message_repository,
        orchestrator: Optional[AIOrchestrator] = None,
        lock_acquire_timeout: float = 10.0,
        lock_ttl_seconds: int = 30,
        lock_heartbeat_interval: float = 10.0,
    ) -> None:
        """Initializes the ChatService with repository, orchestrator, and lock parameters."""
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self._orchestrator = orchestrator
        self.lock_acquire_timeout = lock_acquire_timeout
        self.lock_ttl_seconds = lock_ttl_seconds
        self.lock_heartbeat_interval = lock_heartbeat_interval

    @property
    def orchestrator(self) -> AIOrchestrator:
        """Lazy-instantiates the AIOrchestrator if not injected."""
        if self._orchestrator is None:
            self._orchestrator = AIOrchestrator()
        return self._orchestrator

    async def handle_chat_turn(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        request: ChatMessageRequest,
        business: Optional[Business] = None,
    ) -> ChatMessageResponse:
        """Processes a chat turn with distributed locking, idempotency, and transactional safety.

        Execution Flow:
        1. Tenant Validation: business_id is passed from verified token, never trusted from client.
        2. Distributed Lock: Acquires lock on lock:chat:{business_id}:{request_id}.
        3. Idempotency Check: Checks for existing user message for (business_id, request_id).
           - If found: returns existing completed reply or recovers conversation identity.
        4. Thread Resolution: Creates new conversation (turn 1) or verifies ownership (follow-up).
        5. Transaction 1: Commits user message before inference so client input is never lost.
        6. AI Orchestration: Invokes AIOrchestrator.handle_turn() with zero open DB write transactions.
        7. Lock Lease Check: Verifies lock ownership before persistence via lock.assert_held().
        8. Transaction 2: Persists and commits assistant reply with reply_to_id.
        9. Response Assembly: Returns sanitized ChatMessageResponse matching public contract.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("A valid business_id is required.")

        request_id = request.request_id

        # 1. Distributed Lock Acquisition
        lock = DistributedLock.for_chat_turn(
            business_id=business_id,
            request_id=request_id,
            ttl_seconds=self.lock_ttl_seconds,
            heartbeat_interval=self.lock_heartbeat_interval,
            acquire_timeout=self.lock_acquire_timeout,
        )

        try:
            await lock.acquire(raise_on_failure=True)
        except LockConnectionError as exc:
            logger.error(f"Redis connection failure acquiring lock for {request_id}: {exc}")
            raise ServiceUnavailableError("Redis", "Chat coordination service temporarily unavailable.") from exc
        except LockAcquisitionError as exc:
            logger.warning(f"Lock acquisition timed out for chat request_id={request_id}: {exc}")
            raise ChatLockTimeoutError("Chat coordination timeout. Please retry shortly.") from exc

        try:
            # 2. Idempotency & Retry Check
            existing_user_msg = await self.message_repo.get_by_business_request_id(
                db=db,
                business_id=business_id,
                request_id=request_id,
            )

            if existing_user_msg is not None:
                # This request_id was already received by the business
                conversation_id = existing_user_msg.conversation_id
                logger.info(
                    f"Duplicate chat request detected for business={business_id} "
                    f"request_id={request_id} conv_id={conversation_id}"
                )

                # Check if assistant reply was already committed
                existing_reply = await self.message_repo.get_reply_by_user_message_id(
                    db=db,
                    user_message_id=existing_user_msg.id,
                )
                if existing_reply is not None:
                    # Request was already fully completed; return the existing reply
                    return ChatMessageResponse(
                        conversation_id=conversation_id,
                        message=ChatMessageItem(
                            id=existing_reply.id,
                            role="assistant",
                            content=existing_reply.content,
                            created_at=existing_reply.created_at,
                        ),
                    )

                # Assistant reply was not committed (e.g. inference failed or worker crashed).
                # Resume execution with the existing user message without creating a duplicate.
                user_msg = existing_user_msg
            else:
                # 3. Conversation Thread Resolution
                if request.conversation_id is None:
                    # First turn of a new conversation
                    conversation = await self.conversation_repo.create_conversation(
                        db=db,
                        business_id=business_id,
                        channel=ChannelType.WEB.value,
                    )
                    conversation_id = conversation.id
                else:
                    # Subsequent turn: verify conversation exists and belongs to authorized business
                    conversation = await self.conversation_repo.get_by_id(
                        db=db,
                        business_id=business_id,
                        conversation_id=request.conversation_id,
                    )
                    if conversation is None:
                        raise ConversationNotFoundError(
                            f"Conversation '{request.conversation_id}' not found for business '{business_id}'."
                        )
                    conversation_id = conversation.id

                # 4. DB Transaction 1: Record and commit user message
                try:
                    user_msg, _ = await self.message_repo.create_message_idempotent(
                        db=db,
                        conversation_id=conversation_id,
                        business_id=business_id,
                        role=MessageRole.USER.value,
                        content=request.message,
                        request_id=request_id,
                    )
                    # Commit Transaction 1: user input is durably persisted
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

            # 5. Non-Transactional AI Orchestration
            # Retrieve prior conversation history (excluding the current turn)
            recent_db_messages = await self.conversation_repo.get_recent_messages(
                db=db,
                business_id=business_id,
                conversation_id=conversation_id,
                limit=20,
            )
            history = [
                ChatMessage(
                    role=LLMMessageRole.USER if m.role == MessageRole.USER.value else LLMMessageRole.ASSISTANT,
                    content=m.content,
                )
                for m in recent_db_messages
                if m.id != user_msg.id
            ]

            turn_input = AgentTurnInput(
                business_id=business_id,
                channel=ChannelType.WEB,
                message=user_msg.content,
                conversation_id=conversation_id,
                history=history,
            )

            # Ensure zero open database transactions during external AI inference
            if db.in_transaction():
                await db.commit()

            # Call AI Orchestrator (zero open DB write transactions during external LLM call)
            turn_output: AgentTurnOutput = await self.orchestrator.handle_turn(
                db=db,
                turn_input=turn_input,
                business=business,
            )

            # 6. Verify Distributed Lock Lease Before Persistence
            try:
                await lock.assert_held_async()
            except (LeaseLostError, LockConnectionError) as exc:
                logger.error(
                    f"Lock lease verification failed before persistence for request_id={request_id}: {exc}. "
                    "Aborting assistant message persistence."
                )
                raise ChatLeaseLostError() from exc

            # 7. DB Transaction 2: Persist and commit assistant reply
            try:
                assistant_msg, _ = await self.message_repo.create_assistant_reply_idempotent(
                    db=db,
                    conversation_id=conversation_id,
                    business_id=business_id,
                    content=turn_output.response,
                    reply_to_id=user_msg.id,
                )

                # Update conversation language if resolved by orchestrator
                if turn_output.language:
                    await self.conversation_repo.update_language(
                        db=db,
                        business_id=business_id,
                        conversation_id=conversation_id,
                        language=turn_output.language.value,
                    )

                # Commit Transaction 2: assistant response is durably persisted
                await db.commit()
            except Exception:
                await db.rollback()
                raise

            # 8. Assemble Documented Response Structure
            return ChatMessageResponse(
                conversation_id=conversation_id,
                message=ChatMessageItem(
                    id=assistant_msg.id,
                    role="assistant",
                    content=assistant_msg.content,
                    created_at=assistant_msg.created_at,
                ),
            )
        finally:
            # 9. Clean Lock Release (shielded against caller cancellation)
            try:
                await asyncio.shield(lock.release())
            except Exception as exc:
                logger.warning(f"Error releasing lock for request_id={request_id}: {exc}")


chat_service = ChatService()
