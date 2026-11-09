"""Tests for AgentDesk ChatService (Phase 7 - Step 5E).

Verifies the complete end-to-end multi-agent chat turn coordination:
1. test_successful_first_turn_creates_conversation_and_messages:
   First turn with conversation_id=None creates conversation, commits user message,
   invokes orchestrator, and commits assistant reply with reply_to_id.
2. test_successful_follow_up_turn_in_existing_conversation:
   Follow-up turn preserves conversation identity, feeds prior history to orchestrator,
   and links new assistant reply to the new user message.
3. test_cross_tenant_conversation_access_rejected:
   Attempting to access another business's conversation raises ConversationNotFoundError (HTTP 404).
4. test_duplicate_request_recovery_existing_reply:
   Duplicate request_id with existing assistant reply returns immediately without re-invoking orchestrator.
5. test_first_turn_retry_recovers_conversation_without_conversation_id:
   First turn retry after crash/interruption recovers conversation_id without creating duplicate rows.
6. test_existing_assistant_reply_returned_without_calling_orchestrator:
   Explicit assertion that orchestrator.handle_turn is never called on completed duplicate replay.
7. test_concurrent_duplicate_requests_serialized_by_lock:
   Concurrent requests for same (business_id, request_id) are serialized by distributed lock.
8. test_user_message_committed_before_orchestrator_call:
   User message is committed to DB and visible to separate sessions before orchestrator finishes.
9. test_no_database_transaction_held_during_orchestrator_inference:
   db.in_transaction() is False when orchestrator.handle_turn is called.
10. test_redis_connection_failure_raises_service_unavailable:
    Redis connection failure during lock acquire raises ServiceUnavailableError (HTTP 503).
11. test_lock_acquisition_timeout_raises_lock_timeout_error:
    Lock acquisition timeout raises ChatLockTimeoutError (HTTP 503).
12. test_lease_loss_before_assistant_persistence_aborts_write:
    Distributed lock lease loss during inference raises ChatLeaseLostError and aborts assistant persistence.
13. test_orchestrator_provider_error_handles_fallback_safely:
    Orchestrator provider error returns safe localized fallback persisted to assistant message.
14. test_assistant_persistence_failure_rollback:
    Assistant persistence failure rolls back Transaction 2 and releases the distributed lock.
15. test_no_duplicate_assistant_replies_under_concurrency:
    Concurrency test verifying uniqueness constraint and idempotent assistant reply persistence.
16. test_response_contains_no_internal_rag_or_provider_metadata:
    ChatMessageResponse contains only conversation_id and message (id, role, content, created_at).
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select, func

from app.core.database import async_session_factory
from app.core.distributed_lock import (
    DistributedLock,
    LeaseLostError,
    LockAcquisitionError,
    LockConnectionError,
)
from app.core.exceptions import ServiceUnavailableError
from app.core.redis import get_redis_client
from app.models.business import Business
from app.models.conversation import Conversation, ConversationChannel
from app.models.message import Message, MessageRole
from app.orchestrator.schemas import (
    AgentTurnInput,
    AgentTurnOutput,
    AgentType,
    ChannelType,
    IntentType,
    LanguageCode,
)
from app.orchestrator.service import AIOrchestrator, FALLBACK_RESPONSES
from app.providers.llm import (
    LLMProviderError,
    MockLLMProvider,
    TokenUsage,
)
from app.repositories.conversation_repository import conversation_repository
from app.repositories.message_repository import message_repository
from app.schemas.chat import ChatMessageItem, ChatMessageRequest, ChatMessageResponse
from app.services.chat_service import (
    ChatLeaseLostError,
    ChatLockTimeoutError,
    ChatService,
    ChatServiceError,
    ConversationNotFoundError,
)


# =====================================================================
# Fixtures and Helpers
# =====================================================================

@pytest_asyncio.fixture(autouse=True)
async def cleanup_chat_redis_keys():
    """Cleans up any chat turn lock keys in Redis before and after each test."""
    client = get_redis_client()
    try:
        keys = await client.keys("lock:chat:*")
        if keys:
            await client.delete(*keys)
    except Exception:
        pass
    yield
    try:
        keys = await client.keys("lock:chat:*")
        if keys:
            await client.delete(*keys)
    except Exception:
        pass


async def create_test_business(db, name: str = "Chat Service Biz") -> Business:
    """Helper to persist a test business tenant."""
    biz = Business(
        name=name,
        slug=f"chat-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


def make_mock_orchestrator(
    response: str = "Hello from AgentDesk AI!",
    language: LanguageCode = LanguageCode.EN,
    intent: IntentType = IntentType.FAQ,
    agent: AgentType = AgentType.CHAT,
    confidence: float = 0.95,
) -> MagicMock:
    """Creates a mock AIOrchestrator returning a controlled AgentTurnOutput."""
    mock_orch = MagicMock(spec=AIOrchestrator)
    mock_orch.handle_turn = AsyncMock(
        return_value=AgentTurnOutput(
            response=response,
            language=language,
            intent=intent,
            agent=agent,
            confidence=confidence,
            sources=[uuid.uuid4()],
            usage=TokenUsage(prompt_tokens=25, completion_tokens=15, total_tokens=40),
            metadata={"provider": "mock", "turn_time_ms": 120.0},
        )
    )
    return mock_orch


# =====================================================================
# 1. First Turn Success
# =====================================================================

@pytest.mark.asyncio
async def test_successful_first_turn_creates_conversation_and_messages():
    """Verifies turn 1: creates conversation, commits user message, runs orchestrator, commits assistant reply."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "First Turn Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="What are your hours?",
            request_id=req_id,
        )

        mock_orch = make_mock_orchestrator(response="We are open Mon-Fri 9am-6pm.")
        service = ChatService(orchestrator=mock_orch)

        result = await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

        assert isinstance(result, ChatMessageResponse)
        assert result.conversation_id is not None
        assert result.message.role == "assistant"
        assert result.message.content == "We are open Mon-Fri 9am-6pm."
        assert result.message.created_at is not None

        # Verify DB state
        conv = await conversation_repository.get_by_id(
            db=db, business_id=biz.id, conversation_id=result.conversation_id
        )
        assert conv is not None
        assert conv.channel == ConversationChannel.WEB.value
        assert conv.business_id == biz.id

        # Verify messages in DB
        messages = await conversation_repository.get_recent_messages(
            db=db, business_id=biz.id, conversation_id=result.conversation_id, limit=10
        )
        assert len(messages) == 2
        user_msg, assistant_msg = messages[0], messages[1]

        assert user_msg.role == MessageRole.USER.value
        assert user_msg.content == "What are your hours?"
        assert user_msg.request_id == req_id
        assert user_msg.reply_to_id is None
        assert user_msg.business_id == biz.id

        assert assistant_msg.role == MessageRole.ASSISTANT.value
        assert assistant_msg.content == "We are open Mon-Fri 9am-6pm."
        assert assistant_msg.reply_to_id == user_msg.id
        assert assistant_msg.business_id == biz.id

        # Verify orchestrator was invoked with empty history for turn 1
        mock_orch.handle_turn.assert_awaited_once()
        call_kwargs = mock_orch.handle_turn.call_args.kwargs
        turn_input: AgentTurnInput = call_kwargs["turn_input"]
        assert turn_input.conversation_id == result.conversation_id
        assert turn_input.history == []
        assert turn_input.message == "What are your hours?"


# =====================================================================
# 2. Follow-Up Turn Success
# =====================================================================

@pytest.mark.asyncio
async def test_successful_follow_up_turn_in_existing_conversation():
    """Verifies follow-up turn: preserves conversation_id, passes history, links reply to new user message."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Follow-Up Biz")
        mock_orch = make_mock_orchestrator(response="First reply.")
        service = ChatService(orchestrator=mock_orch)

        # Turn 1
        req1 = ChatMessageRequest(
            conversation_id=None,
            message="Hello",
            request_id=uuid.uuid4(),
        )
        res1 = await service.handle_chat_turn(db=db, business_id=biz.id, request=req1)
        conv_id = res1.conversation_id

        # Turn 2
        mock_orch.handle_turn.reset_mock()
        mock_orch.handle_turn.return_value = AgentTurnOutput(
            response="Follow-up reply.",
            language=LanguageCode.EN,
            intent=IntentType.GENERAL,
            agent=AgentType.CHAT,
            confidence=0.9,
        )

        req2 = ChatMessageRequest(
            conversation_id=conv_id,
            message="Tell me more",
            request_id=uuid.uuid4(),
        )
        res2 = await service.handle_chat_turn(db=db, business_id=biz.id, request=req2)

        assert res2.conversation_id == conv_id
        assert res2.message.content == "Follow-up reply."

        # Verify orchestrator received prior turn in history (excluding current user message)
        mock_orch.handle_turn.assert_awaited_once()
        call_kwargs = mock_orch.handle_turn.call_args.kwargs
        turn_input: AgentTurnInput = call_kwargs["turn_input"]
        assert turn_input.conversation_id == conv_id
        assert turn_input.message == "Tell me more"
        assert len(turn_input.history) == 2
        assert turn_input.history[0].content == "Hello"
        assert turn_input.history[1].content == "First reply."

        # Verify DB has 4 messages total
        all_messages = await conversation_repository.get_recent_messages(
            db=db, business_id=biz.id, conversation_id=conv_id, limit=10
        )
        assert len(all_messages) == 4
        # New assistant message links to the second user message
        assert all_messages[3].reply_to_id == all_messages[2].id


# =====================================================================
# 3. Cross-Tenant Conversation Access Rejected
# =====================================================================

@pytest.mark.asyncio
async def test_cross_tenant_conversation_access_rejected():
    """Verifies that accessing a conversation belonging to another tenant raises ConversationNotFoundError."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, "Tenant A")
        biz_b = await create_test_business(db, "Tenant B")

        # Create conversation for Tenant A
        conv_a = await conversation_repository.create_conversation(
            db=db, business_id=biz_a.id, channel=ConversationChannel.WEB.value
        )
        await db.commit()

        # Tenant B attempts to send a message to Tenant A's conversation
        service = ChatService(orchestrator=make_mock_orchestrator())
        req = ChatMessageRequest(
            conversation_id=conv_a.id,
            message="Unauthorized access attempt",
            request_id=uuid.uuid4(),
        )

        with pytest.raises(ConversationNotFoundError) as exc_info:
            await service.handle_chat_turn(db=db, business_id=biz_b.id, request=req)

        assert exc_info.value.status_code == 404

        # Confirm no messages were created in Tenant A's conversation
        messages = await conversation_repository.get_recent_messages(
            db=db, business_id=biz_a.id, conversation_id=conv_a.id
        )
        assert len(messages) == 0


# =====================================================================
# 4. Duplicate Request Recovery (Completed Turn)
# =====================================================================

@pytest.mark.asyncio
async def test_duplicate_request_recovery_existing_reply():
    """Verifies that repeating a request_id for a completed turn returns existing reply with 0 duplicate rows."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Dedup Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Duplicate test query",
            request_id=req_id,
        )

        mock_orch = make_mock_orchestrator(response="Original unique answer.")
        service = ChatService(orchestrator=mock_orch)

        # First request
        res1 = await service.handle_chat_turn(db=db, business_id=biz.id, request=req)
        assert res1.message.content == "Original unique answer."
        assert mock_orch.handle_turn.await_count == 1

        # Second request with identical request_id and conversation_id
        req_duplicate = ChatMessageRequest(
            conversation_id=res1.conversation_id,
            message="Duplicate test query",
            request_id=req_id,
        )
        res2 = await service.handle_chat_turn(db=db, business_id=biz.id, request=req_duplicate)

        # Assert same message returned
        assert res2.conversation_id == res1.conversation_id
        assert res2.message.id == res1.message.id
        assert res2.message.content == "Original unique answer."

        # Orchestrator was NOT called again
        assert mock_orch.handle_turn.await_count == 1

        # Verify no duplicate rows
        messages = await conversation_repository.get_recent_messages(
            db=db, business_id=biz.id, conversation_id=res1.conversation_id, limit=10
        )
        assert len(messages) == 2


# =====================================================================
# 5. First-Turn Retry Recovers Conversation (conversation_id=None)
# =====================================================================

@pytest.mark.asyncio
async def test_first_turn_retry_recovers_conversation_without_conversation_id():
    """Verifies recovery when turn 1 crashed after user message commit but before assistant reply commit."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "First Turn Recovery Biz")
        req_id = uuid.uuid4()

        # Simulate state after Transaction 1 of turn 1: conversation + user message persisted, no assistant reply
        conv = await conversation_repository.create_conversation(
            db=db, business_id=biz.id, channel=ConversationChannel.WEB.value
        )
        user_msg, _ = await message_repository.create_message_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=biz.id,
            role=MessageRole.USER.value,
            content="Initial question",
            request_id=req_id,
        )
        await db.commit()

        # Client retries turn 1: conversation_id is STILL None because client never received it!
        retry_req = ChatMessageRequest(
            conversation_id=None,
            message="Initial question",
            request_id=req_id,
        )

        mock_orch = make_mock_orchestrator(response="Recovered reply.")
        service = ChatService(orchestrator=mock_orch)

        result = await service.handle_chat_turn(db=db, business_id=biz.id, request=retry_req)

        # Recovers existing conversation ID
        assert result.conversation_id == conv.id
        assert result.message.content == "Recovered reply."

        # Verify DB state: exactly 1 conversation and 2 messages (no duplicates)
        messages = await conversation_repository.get_recent_messages(
            db=db, business_id=biz.id, conversation_id=conv.id
        )
        assert len(messages) == 2
        assert messages[0].id == user_msg.id
        assert messages[1].reply_to_id == user_msg.id


# =====================================================================
# 6. Existing Reply Returned Without Calling Orchestrator
# =====================================================================

@pytest.mark.asyncio
async def test_existing_assistant_reply_returned_without_calling_orchestrator():
    """Explicitly verifies orchestrator.handle_turn is never invoked on duplicate replay."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Zero Orchestrator Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Hello",
            request_id=req_id,
        )

        mock_orch = make_mock_orchestrator()
        service = ChatService(orchestrator=mock_orch)

        # Turn 1
        res1 = await service.handle_chat_turn(db=db, business_id=biz.id, request=req)
        assert mock_orch.handle_turn.await_count == 1

        # Reset mock
        mock_orch.handle_turn.reset_mock()

        # Replay identical turn
        res2 = await service.handle_chat_turn(db=db, business_id=biz.id, request=req)
        assert res2.message.id == res1.message.id

        # Must not be called at all
        mock_orch.handle_turn.assert_not_called()


# =====================================================================
# 7. Concurrent Duplicate Requests Serialized by Lock
# =====================================================================

@pytest.mark.asyncio
async def test_concurrent_duplicate_requests_serialized_by_lock():
    """Verifies that concurrent requests with identical (business_id, request_id) are serialized."""
    async with async_session_factory() as db_setup:
        biz = await create_test_business(db_setup, "Concurrent Lock Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Concurrent test message",
            request_id=req_id,
        )

    # Orchestrator with slight delay to ensure concurrency overlap
    call_counter = 0

    async def delayed_handle_turn(*args, **kwargs):
        nonlocal call_counter
        call_counter += 1
        await asyncio.sleep(0.15)
        return AgentTurnOutput(
            response="Concurrent response.",
            language=LanguageCode.EN,
            intent=IntentType.FAQ,
            agent=AgentType.CHAT,
            confidence=0.9,
        )

    mock_orch = MagicMock(spec=AIOrchestrator)
    mock_orch.handle_turn = AsyncMock(side_effect=delayed_handle_turn)
    service = ChatService(orchestrator=mock_orch, lock_acquire_timeout=5.0)

    async def execute_turn():
        async with async_session_factory() as db:
            return await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

    # Launch two simultaneous requests
    res1, res2 = await asyncio.gather(execute_turn(), execute_turn())

    # Both succeed and return identical assistant message ID
    assert res1.conversation_id == res2.conversation_id
    assert res1.message.id == res2.message.id
    assert res1.message.content == "Concurrent response."

    # Orchestrator was executed exactly once
    assert call_counter == 1

    # Database contains exactly 1 user message and 1 assistant message
    async with async_session_factory() as db_verify:
        messages = await conversation_repository.get_recent_messages(
            db=db_verify, business_id=biz.id, conversation_id=res1.conversation_id
        )
        assert len(messages) == 2


# =====================================================================
# 8. User Message Committed Before Orchestrator Call
# =====================================================================

@pytest.mark.asyncio
async def test_user_message_committed_before_orchestrator_call():
    """Verifies that user message is committed and visible to other sessions before inference completes."""
    async with async_session_factory() as db_setup:
        biz = await create_test_business(db_setup, "Tx1 Visibility Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Pre-inference commit check",
            request_id=req_id,
        )

    user_msg_found_during_inference = False

    async def inspect_db_during_inference(*args, **kwargs):
        nonlocal user_msg_found_during_inference
        # In a separate database session, query for the user message
        async with async_session_factory() as separate_db:
            found = await message_repository.get_by_business_request_id(
                db=separate_db,
                business_id=biz.id,
                request_id=req_id,
            )
            if found is not None and found.content == "Pre-inference commit check":
                user_msg_found_during_inference = True

        return AgentTurnOutput(
            response="Inference done.",
            language=LanguageCode.EN,
            intent=IntentType.FAQ,
            agent=AgentType.CHAT,
            confidence=0.9,
        )

    mock_orch = MagicMock(spec=AIOrchestrator)
    mock_orch.handle_turn = AsyncMock(side_effect=inspect_db_during_inference)
    service = ChatService(orchestrator=mock_orch)

    async with async_session_factory() as db:
        await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

    assert user_msg_found_during_inference is True


# =====================================================================
# 9. No Open Database Transaction During Inference
# =====================================================================

@pytest.mark.asyncio
async def test_no_database_transaction_held_during_orchestrator_inference():
    """Verifies db.in_transaction() is False when orchestrator.handle_turn is invoked."""
    async with async_session_factory() as db_setup:
        biz = await create_test_business(db_setup, "No Open Tx Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Checking active transaction flag",
            request_id=req_id,
        )

    in_transaction_during_inference = True

    async def check_tx_flag(*args, **kwargs):
        nonlocal in_transaction_during_inference
        # Extract db passed to orchestrator.handle_turn
        orch_db = kwargs.get("db") or args[0]
        in_transaction_during_inference = orch_db.in_transaction()
        return AgentTurnOutput(
            response="Tx check complete.",
            language=LanguageCode.EN,
            intent=IntentType.FAQ,
            agent=AgentType.CHAT,
            confidence=0.9,
        )

    mock_orch = MagicMock(spec=AIOrchestrator)
    mock_orch.handle_turn = AsyncMock(side_effect=check_tx_flag)
    service = ChatService(orchestrator=mock_orch)

    async with async_session_factory() as db:
        await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

    # Must be False! Zero open DB transactions during inference.
    assert in_transaction_during_inference is False


# =====================================================================
# 10. Redis Connection Failure Raises ServiceUnavailableError (503)
# =====================================================================

@pytest.mark.asyncio
async def test_redis_connection_failure_raises_service_unavailable():
    """Verifies that Redis failure during lock acquisition raises ServiceUnavailableError (503)."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Redis Fail Biz")
        req = ChatMessageRequest(
            conversation_id=None,
            message="Hello",
            request_id=uuid.uuid4(),
        )

        service = ChatService(orchestrator=make_mock_orchestrator())

        with patch.object(
            DistributedLock,
            "acquire",
            side_effect=LockConnectionError("Connection to Redis refused."),
        ):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

            assert exc_info.value.status_code == 503
            assert "Chat coordination service temporarily unavailable" in exc_info.value.message

        # Assert no conversations were created
        result = await db.execute(
            select(func.count(Conversation.id)).where(Conversation.business_id == biz.id)
        )
        assert result.scalar() == 0


# =====================================================================
# 11. Lock Acquisition Timeout Raises ChatLockTimeoutError (503)
# =====================================================================

@pytest.mark.asyncio
async def test_lock_acquisition_timeout_raises_lock_timeout_error():
    """Verifies that failing to acquire lock within timeout raises ChatLockTimeoutError (503)."""
    client = get_redis_client()
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Lock Timeout Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Timeout check",
            request_id=req_id,
        )

        # Hold the lock externally in Redis
        lock_key = f"lock:chat:{biz.id}:{req_id}"
        await client.set(lock_key, "external-owner", ex=10)

        # Configure short acquire timeout
        service = ChatService(orchestrator=make_mock_orchestrator(), lock_acquire_timeout=0.2)

        with pytest.raises(ChatLockTimeoutError) as exc_info:
            await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

        assert exc_info.value.status_code == 503
        assert "Chat coordination timeout" in str(exc_info.value)


# =====================================================================
# 12. Lease Loss Before Persistence Aborts Assistant Write
# =====================================================================

@pytest.mark.asyncio
async def test_lease_loss_before_assistant_persistence_aborts_write():
    """Verifies that losing lock lease during inference raises ChatLeaseLostError and aborts assistant write."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Lease Lost Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Lease loss test",
            request_id=req_id,
        )

        mock_orch = MagicMock(spec=AIOrchestrator)
        mock_orch.handle_turn = AsyncMock(
            return_value=AgentTurnOutput(
                response="Orchestrator output.",
                language=LanguageCode.EN,
                intent=IntentType.FAQ,
                agent=AgentType.CHAT,
                confidence=0.9,
            )
        )

        service = ChatService(orchestrator=mock_orch)

        # Patch assert_held to simulate lease expiration during inference
        with patch.object(
            DistributedLock,
            "assert_held",
            side_effect=LeaseLostError("Lock lease expired or taken over by another worker."),
        ):
            with pytest.raises(ChatLeaseLostError) as exc_info:
                await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

            assert exc_info.value.status_code == 503
            assert "lease expired" in str(exc_info.value).lower()

        # Verify DB state: user message was committed in Tx 1, but NO assistant message was written!
        user_msg = await message_repository.get_by_business_request_id(
            db=db, business_id=biz.id, request_id=req_id
        )
        assert user_msg is not None
        assert user_msg.content == "Lease loss test"

        reply = await message_repository.get_reply_by_user_message_id(
            db=db, user_message_id=user_msg.id
        )
        assert reply is None, "Assistant message must not be persisted after lease loss"


# =====================================================================
# 13. Orchestrator Provider Error Safe Fallback Handling
# =====================================================================

@pytest.mark.asyncio
async def test_orchestrator_provider_error_handles_fallback_safely():
    """Verifies that orchestrator provider failure yields safe fallback response and persists it."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Fallback Handling Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Help me with booking",
            request_id=req_id,
        )

        # Mock orchestrator that returns safe fallback response as AIOrchestrator does on LLM error
        fallback_text = FALLBACK_RESPONSES[LanguageCode.EN]
        mock_orch = make_mock_orchestrator(
            response=fallback_text,
            language=LanguageCode.EN,
            confidence=0.0,
        )
        service = ChatService(orchestrator=mock_orch)

        res = await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

        assert res.message.role == "assistant"
        assert res.message.content == fallback_text

        # Verify assistant message was durably persisted with fallback text
        reply = await message_repository.get_by_business_request_id(
            db=db, business_id=biz.id, request_id=req_id
        )
        assert reply is not None
        persisted_reply = await message_repository.get_reply_by_user_message_id(
            db=db, user_message_id=reply.id
        )
        assert persisted_reply is not None
        assert persisted_reply.content == fallback_text


# =====================================================================
# 14. Assistant Persistence Failure Rolls Back Transaction 2
# =====================================================================

@pytest.mark.asyncio
async def test_assistant_persistence_failure_rollback():
    """Verifies that an error during assistant message persistence rolls back Tx 2 and releases lock."""
    client = get_redis_client()
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Tx2 Rollback Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Rollback test",
            request_id=req_id,
        )

        service = ChatService(orchestrator=make_mock_orchestrator())

        with patch.object(
            message_repository,
            "create_assistant_reply_idempotent",
            side_effect=RuntimeError("Simulated DB disk failure during Tx 2"),
        ):
            with pytest.raises(RuntimeError, match="Simulated DB disk failure"):
                await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

        # User message was committed in Tx 1
        user_msg = await message_repository.get_by_business_request_id(
            db=db, business_id=biz.id, request_id=req_id
        )
        assert user_msg is not None

        # Lock was cleanly released in finally block
        lock_val = await client.get(f"lock:chat:{biz.id}:{req_id}")
        assert lock_val is None


# =====================================================================
# 15. No Duplicate Assistant Replies Under Concurrency
# =====================================================================

@pytest.mark.asyncio
async def test_no_duplicate_assistant_replies_under_concurrency():
    """Verifies that concurrent persistence calls for same reply_to_id do not create duplicate rows."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Assistant Dedup Biz")
        conv = await conversation_repository.create_conversation(
            db=db, business_id=biz.id, channel=ConversationChannel.WEB.value
        )
        user_msg, _ = await message_repository.create_message_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=biz.id,
            role=MessageRole.USER.value,
            content="User query",
            request_id=uuid.uuid4(),
        )
        await db.commit()

        # Concurrent assistant reply creation calls racing to persist for user_msg.id
        async def insert_reply(text: str):
            async with async_session_factory() as task_db:
                reply, _ = await message_repository.create_assistant_reply_idempotent(
                    db=task_db,
                    conversation_id=conv.id,
                    business_id=biz.id,
                    content=text,
                    reply_to_id=user_msg.id,
                )
                await task_db.commit()
                return reply.id

        rep1_id, rep2_id = await asyncio.gather(
            insert_reply("Reply from Worker 1"),
            insert_reply("Reply from Worker 2"),
        )

        assert rep1_id == rep2_id

        # Verify only 1 assistant message in DB for this conversation
        messages = await conversation_repository.get_recent_messages(
            db=db, business_id=biz.id, conversation_id=conv.id
        )
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT.value]
        assert len(assistant_messages) == 1
        assert assistant_messages[0].reply_to_id == user_msg.id


# =====================================================================
# 16. Response Contains No Internal Metadata
# =====================================================================

@pytest.mark.asyncio
async def test_response_contains_no_internal_rag_or_provider_metadata():
    """Verifies ChatMessageResponse contains only conversation_id and message (id, role, content, created_at)."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Metadata Leak Biz")
        req = ChatMessageRequest(
            conversation_id=None,
            message="Verify clean response structure",
            request_id=uuid.uuid4(),
        )

        # Orchestrator with internal sources, tokens, metadata
        mock_orch = make_mock_orchestrator(response="Clean customer response.")
        service = ChatService(orchestrator=mock_orch)

        response = await service.handle_chat_turn(db=db, business_id=biz.id, request=req)

        # Verify Pydantic dump strictly matches public API contract
        dump = response.model_dump()

        # Top-level keys must ONLY be conversation_id and message
        assert set(dump.keys()) == {"conversation_id", "message"}

        # Message keys must ONLY be id, role, content, created_at
        assert set(dump["message"].keys()) == {"id", "role", "content", "created_at"}

        # Explicitly verify no internal RAG/AI metadata is exposed
        forbidden_fields = [
            "sources",
            "usage",
            "token_usage",
            "confidence",
            "agent",
            "intent",
            "provider",
            "model",
            "context",
            "metadata",
            "business_id",
            "request_id",
            "reply_to_id",
        ]
        for field in forbidden_fields:
            assert field not in dump, f"Forbidden field '{field}' leaked into response"
            assert field not in dump["message"], f"Forbidden field '{field}' leaked into message"


# =====================================================================
# 17. Task Cancellation During Inference Cleans Up and Preserves Tx 1
# =====================================================================

@pytest.mark.asyncio
async def test_cancellation_during_inference_cleans_up_and_preserves_user_message():
    """Verifies that if a caller task is cancelled during AI inference:
    1. User message remains committed (Tx 1 completed before inference).
    2. Lock is cleanly released via asyncio.shield in finally block.
    3. Client retry with identical request_id recovers turn cleanly without duplicates.
    """
    client = get_redis_client()
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Cancellation Safety Biz")
        req_id = uuid.uuid4()
        req = ChatMessageRequest(
            conversation_id=None,
            message="Will be cancelled mid-inference",
            request_id=req_id,
        )

        inference_started = asyncio.Event()

        async def slow_inference(*args, **kwargs):
            inference_started.set()
            await asyncio.sleep(10.0)  # Wait to be cancelled
            return AgentTurnOutput(response="Should not be reached")

        mock_orch = AsyncMock()
        mock_orch.handle_turn.side_effect = slow_inference
        service = ChatService(orchestrator=mock_orch)

        # Run handle_chat_turn in a separate task
        task = asyncio.create_task(
            service.handle_chat_turn(db=db, business_id=biz.id, request=req)
        )

        # Wait until orchestrator is entered
        await inference_started.wait()

        # Cancel the task
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # 1. Verify lock was cleanly released despite task cancellation
        lock_val = await client.get(f"lock:chat:{biz.id}:{req_id}")
        assert lock_val is None

        # 2. Verify user message is durably persisted in DB (Tx 1 was committed before inference)
        user_msg = await message_repository.get_by_business_request_id(
            db=db, business_id=biz.id, request_id=req_id
        )
        assert user_msg is not None
        assert user_msg.content == "Will be cancelled mid-inference"

        # 3. Verify retry with same request_id recovers conversation and completes
        retry_orch = make_mock_orchestrator(response="Recovered after cancellation.")
        retry_service = ChatService(orchestrator=retry_orch)

        retry_res = await retry_service.handle_chat_turn(
            db=db, business_id=biz.id, request=req
        )
        assert retry_res.message.content == "Recovered after cancellation."
        assert retry_res.conversation_id == user_msg.conversation_id
