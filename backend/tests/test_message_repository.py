"""Tests for MessageRepository (Phase 7 - Step 5B).

Verifies:
1. Message creation with explicit business_id and auto-resolved business_id.
2. Message validation (role, non-empty content, reply_to_id role restrictions).
3. Retrieval by ID with conversation and business scoping.
4. Chronological message retrieval with limit and offset.
5. Correct tenant-scoped request-ID lookup (get_by_business_request_id).
6. Same request ID allowed across different businesses.
7. Duplicate request ID rejected within the same business (database constraint & idempotent helper).
8. First-turn lookup when conversation_id was initially unknown.
9. Assistant reply creation and retrieval (get_reply_by_user_message_id).
10. Duplicate assistant reply returns the existing reply safely via savepoint.
11. Two different user messages can each have their own assistant reply.
12. Cross-tenant conversation/message access is rejected.
13. Repository methods flush but never commit.
"""

from datetime import datetime, timezone, timedelta
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.repositories.conversation_repository import conversation_repository
from app.repositories.message_repository import message_repository


async def create_test_business(db, name: str = "Message Repo Biz") -> Business:
    """Helper to persist a test business."""
    biz = Business(
        name=name,
        slug=f"msg-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


async def create_test_conversation(db, business_id: uuid.UUID = None) -> Conversation:
    """Helper to persist a test conversation."""
    if business_id is None:
        biz = await create_test_business(db)
        business_id = biz.id

    conv = Conversation(
        business_id=business_id,
        channel="web",
        language="en",
        status="active",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@pytest.mark.asyncio
async def test_create_user_and_assistant_messages():
    """Verifies creating user and assistant messages with explicit and auto-resolved business_id."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)

        # 1. User message with explicit business_id
        req_id = uuid.uuid4()
        user_msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role=MessageRole.USER.value,
            content="What are your business hours?",
            request_id=req_id,
        )
        assert user_msg.id is not None
        assert user_msg.conversation_id == conv.id
        assert user_msg.business_id == conv.business_id
        assert user_msg.role == "user"
        assert user_msg.content == "What are your business hours?"
        assert user_msg.request_id == req_id
        assert user_msg.reply_to_id is None
        assert user_msg.created_at is not None

        # 2. Assistant message with auto-resolved business_id (omitted business_id parameter)
        asst_msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            role=MessageRole.ASSISTANT.value,
            content="We are open Monday to Friday from 9 AM to 6 PM.",
            request_id=None,
            reply_to_id=user_msg.id,
        )
        assert asst_msg.id is not None
        assert asst_msg.conversation_id == conv.id
        assert asst_msg.business_id == conv.business_id  # Auto-resolved from conversation
        assert asst_msg.role == "assistant"
        assert asst_msg.content == "We are open Monday to Friday from 9 AM to 6 PM."
        assert asst_msg.request_id is None
        assert asst_msg.reply_to_id == user_msg.id


@pytest.mark.asyncio
async def test_create_message_validation_errors():
    """Verifies that invalid roles, empty contents, and user messages with reply_to_id are rejected."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)

        # Invalid role
        with pytest.raises(ValueError, match="Invalid message role 'system'"):
            await message_repository.create_message(
                db=db,
                conversation_id=conv.id,
                business_id=conv.business_id,
                role="system",
                content="System prompt injection attempt",
            )

        with pytest.raises(ValueError, match="Invalid message role ''"):
            await message_repository.create_message(
                db=db,
                conversation_id=conv.id,
                role="",
                content="Hello",
            )

        # Empty or whitespace-only content
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            await message_repository.create_message(
                db=db,
                conversation_id=conv.id,
                role="user",
                content="   ",
            )

        with pytest.raises(ValueError, match="Message content cannot be empty"):
            await message_repository.create_message(
                db=db,
                conversation_id=conv.id,
                role="user",
                content="\n\t",
            )

        # User message cannot have reply_to_id
        dummy_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Only assistant messages can have a reply_to_id set"):
            await message_repository.create_message(
                db=db,
                conversation_id=conv.id,
                role="user",
                content="Replying as user",
                reply_to_id=dummy_id,
            )


@pytest.mark.asyncio
async def test_get_by_id():
    """Verifies retrieval by message ID with optional conversation and business scoping."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)
        other_conv_id = uuid.uuid4()
        other_biz_id = uuid.uuid4()

        msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Looking for assistance",
        )

        # Unscoped lookup
        found = await message_repository.get_by_id(db, msg.id)
        assert found is not None
        assert found.id == msg.id

        # Scoped to matching conversation and business
        scoped_found = await message_repository.get_by_id(
            db, msg.id, conversation_id=conv.id, business_id=conv.business_id
        )
        assert scoped_found is not None
        assert scoped_found.id == msg.id

        # Scoped to wrong conversation returns None
        assert await message_repository.get_by_id(db, msg.id, conversation_id=other_conv_id) is None

        # Scoped to wrong business returns None
        assert await message_repository.get_by_id(db, msg.id, business_id=other_biz_id) is None


@pytest.mark.asyncio
async def test_get_messages_for_conversation_chronological_order():
    """Verifies messages for a conversation are returned in chronological order."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)
        base_time = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Insert 3 messages with explicit timestamps
        for i in range(3):
            m = Message(
                conversation_id=conv.id,
                business_id=conv.business_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Turn {i + 1}",
                created_at=base_time + timedelta(seconds=i * 10),
            )
            db.add(m)
        await db.flush()

        messages = await message_repository.get_messages_for_conversation(db, conv.id)
        assert len(messages) == 3
        assert [m.content for m in messages] == ["Turn 1", "Turn 2", "Turn 3"]

        # Pagination limit and offset
        paged = await message_repository.get_messages_for_conversation(
            db, conv.id, limit=2, offset=1
        )
        assert len(paged) == 2
        assert [m.content for m in paged] == ["Turn 2", "Turn 3"]


@pytest.mark.asyncio
async def test_get_messages_for_conversation_tenant_isolation():
    """Verifies tenant isolation when business_id is passed to get_messages_for_conversation."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)
        other_biz = await create_test_business(db, "Intruder Biz")

        await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Confidential inquiry",
        )

        # 1. Matching business returns messages
        valid = await message_repository.get_messages_for_conversation(
            db, conv.id, business_id=conv.business_id
        )
        assert len(valid) == 1
        assert valid[0].content == "Confidential inquiry"

        # 2. Cross-tenant inquiry returns empty list
        isolated = await message_repository.get_messages_for_conversation(
            db, conv.id, business_id=other_biz.id
        )
        assert isolated == []


@pytest.mark.asyncio
async def test_get_by_business_request_id_tenant_scoped():
    """Verifies that get_by_business_request_id strictly isolates lookup by tenant ID."""
    async with async_session_factory() as db:
        biz_1 = await create_test_business(db, "Tenant 1 Req Biz")
        biz_2 = await create_test_business(db, "Tenant 2 Req Biz")

        conv_1 = await create_test_conversation(db, business_id=biz_1.id)
        req_id = uuid.uuid4()

        msg = await message_repository.create_message(
            db=db,
            conversation_id=conv_1.id,
            business_id=biz_1.id,
            role="user",
            content="Tenant 1 query",
            request_id=req_id,
        )

        # Tenant 1 lookup succeeds
        found = await message_repository.get_by_business_request_id(db, biz_1.id, req_id)
        assert found is not None
        assert found.id == msg.id
        assert found.content == "Tenant 1 query"

        # Tenant 2 lookup for same request_id returns None (strict tenant isolation)
        assert await message_repository.get_by_business_request_id(db, biz_2.id, req_id) is None


@pytest.mark.asyncio
async def test_same_request_id_allowed_across_different_businesses():
    """Verifies that the same request_id is allowed in two different businesses (tenant-partitioned uniqueness)."""
    async with async_session_factory() as db:
        biz_1 = await create_test_business(db, "MultiTenant Biz A")
        biz_2 = await create_test_business(db, "MultiTenant Biz B")

        conv_1 = await create_test_conversation(db, business_id=biz_1.id)
        conv_2 = await create_test_conversation(db, business_id=biz_2.id)

        shared_request_id = uuid.uuid4()

        # Insert into Biz 1
        msg_1 = await message_repository.create_message(
            db=db,
            conversation_id=conv_1.id,
            business_id=biz_1.id,
            role="user",
            content="Biz 1 message",
            request_id=shared_request_id,
        )

        # Insert same request_id into Biz 2 must succeed!
        msg_2 = await message_repository.create_message(
            db=db,
            conversation_id=conv_2.id,
            business_id=biz_2.id,
            role="user",
            content="Biz 2 message",
            request_id=shared_request_id,
        )

        assert msg_1.id != msg_2.id
        assert msg_1.business_id == biz_1.id
        assert msg_2.business_id == biz_2.id
        assert msg_1.request_id == shared_request_id
        assert msg_2.request_id == shared_request_id


@pytest.mark.asyncio
async def test_duplicate_request_id_rejected_within_same_business():
    """Verifies that duplicate request_id within the same business raises IntegrityError across conversations."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Unique Key Biz")
        conv_1 = await create_test_conversation(db, business_id=biz.id)
        conv_2 = await create_test_conversation(db, business_id=biz.id)

        duplicate_req_id = uuid.uuid4()

        # 1. First insert in conversation 1 succeeds
        await message_repository.create_message(
            db=db,
            conversation_id=conv_1.id,
            business_id=biz.id,
            role="user",
            content="Initial message",
            request_id=duplicate_req_id,
        )

        # 2. Duplicate insert in same conversation raises IntegrityError on uq_messages_business_request_id
        with pytest.raises(IntegrityError):
            async with db.begin_nested():
                await message_repository.create_message(
                    db=db,
                    conversation_id=conv_1.id,
                    business_id=biz.id,
                    role="user",
                    content="Duplicate in same conversation",
                    request_id=duplicate_req_id,
                )

        # 3. Duplicate insert in different conversation of SAME business ALSO raises IntegrityError!
        with pytest.raises(IntegrityError):
            async with db.begin_nested():
                await message_repository.create_message(
                    db=db,
                    conversation_id=conv_2.id,
                    business_id=biz.id,
                    role="user",
                    content="Cross-conversation duplicate in same business",
                    request_id=duplicate_req_id,
                )


@pytest.mark.asyncio
async def test_first_turn_lookup_when_conversation_id_unknown():
    """Verifies that get_by_business_request_id recovers the conversation_id for turn 1 client retries."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "First Turn Recovery Biz")
        conv = await create_test_conversation(db, business_id=biz.id)
        turn1_req_id = uuid.uuid4()

        user_msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=biz.id,
            role="user",
            content="Initial inquiry on turn 1",
            request_id=turn1_req_id,
        )

        # Client disconnects and retries with conversation_id=None, passing only (biz.id, turn1_req_id)
        recovered = await message_repository.get_by_business_request_id(db, biz.id, turn1_req_id)
        assert recovered is not None
        assert recovered.id == user_msg.id
        assert recovered.conversation_id == conv.id  # Conversation identity successfully recovered!


@pytest.mark.asyncio
async def test_assistant_reply_creation_and_retrieval():
    """Verifies creating an assistant reply linked via reply_to_id and retrieving it via get_reply_by_user_message_id."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)

        user_msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Do you accept credit cards?",
            request_id=uuid.uuid4(),
        )

        # Before reply exists, lookup returns None
        assert await message_repository.get_reply_by_user_message_id(db, user_msg.id) is None

        # Create assistant reply
        asst_msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="assistant",
            content="Yes, we accept Visa, Mastercard, and PayPak.",
            reply_to_id=user_msg.id,
        )

        # Lookup returns the exact assistant reply
        found_reply = await message_repository.get_reply_by_user_message_id(db, user_msg.id)
        assert found_reply is not None
        assert found_reply.id == asst_msg.id
        assert found_reply.reply_to_id == user_msg.id
        assert found_reply.content == "Yes, we accept Visa, Mastercard, and PayPak."


@pytest.mark.asyncio
async def test_duplicate_assistant_reply_returns_existing_idempotent():
    """Verifies that create_assistant_reply_idempotent safely returns the existing reply on duplicate submissions."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)

        user_msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Price check query",
            request_id=uuid.uuid4(),
        )

        # 1. First submission creates assistant reply
        reply1, created1 = await message_repository.create_assistant_reply_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            content="The standard price is $50.",
            reply_to_id=user_msg.id,
        )
        assert created1 is True
        assert reply1.id is not None
        assert reply1.reply_to_id == user_msg.id
        assert reply1.content == "The standard price is $50."

        # 2. Duplicate submission for the same user message returns existing record with created=False
        reply2, created2 = await message_repository.create_assistant_reply_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            content="Different content that must be ignored",
            reply_to_id=user_msg.id,
        )
        assert created2 is False
        assert reply2.id == reply1.id
        assert reply2.content == "The standard price is $50."

        # Verify only 1 reply exists in database
        all_replies = await db.execute(
            select(Message).where(Message.reply_to_id == user_msg.id)
        )
        assert len(list(all_replies.scalars().all())) == 1


@pytest.mark.asyncio
async def test_direct_duplicate_assistant_reply_raises_integrity_error():
    """Verifies that the partial unique index uq_messages_reply_to_id raises IntegrityError on direct raw duplicate."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)

        user_msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Query",
            request_id=uuid.uuid4(),
        )

        # Insert reply 1
        await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="assistant",
            content="Reply 1",
            reply_to_id=user_msg.id,
        )

        # Direct second reply for same user_msg.id triggers IntegrityError on uq_messages_reply_to_id
        with pytest.raises(IntegrityError):
            await message_repository.create_message(
                db=db,
                conversation_id=conv.id,
                business_id=conv.business_id,
                role="assistant",
                content="Reply 2 colliding",
                reply_to_id=user_msg.id,
            )
        await db.rollback()


@pytest.mark.asyncio
async def test_two_different_user_messages_have_own_assistant_replies():
    """Verifies that two separate user messages each have their own independent assistant reply."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)

        u1 = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="User turn 1",
            request_id=uuid.uuid4(),
        )
        u2 = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="User turn 2",
            request_id=uuid.uuid4(),
        )

        r1, created1 = await message_repository.create_assistant_reply_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            content="Assistant reply 1",
            reply_to_id=u1.id,
        )
        r2, created2 = await message_repository.create_assistant_reply_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            content="Assistant reply 2",
            reply_to_id=u2.id,
        )

        assert created1 is True
        assert created2 is True
        assert r1.id != r2.id
        assert r1.reply_to_id == u1.id
        assert r2.reply_to_id == u2.id


@pytest.mark.asyncio
async def test_create_message_idempotent_creates_and_deduplicates():
    """Verifies create_message_idempotent creates new user message and returns existing on duplicate."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)
        req_id = uuid.uuid4()

        m1, created1 = await message_repository.create_message_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Original message",
            request_id=req_id,
        )
        assert created1 is True

        m2, created2 = await message_repository.create_message_idempotent(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Resubmitted content",
            request_id=req_id,
        )
        assert created2 is False
        assert m2.id == m1.id
        assert m2.content == "Original message"


@pytest.mark.asyncio
async def test_repository_methods_flush_not_commit():
    """Verifies that repository methods flush changes to session but do not commit, allowing clean rollback."""
    async with async_session_factory() as db:
        conv = await create_test_conversation(db)
        req_id = uuid.uuid4()

        msg = await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            business_id=conv.business_id,
            role="user",
            content="Uncommitted turn",
            request_id=req_id,
        )
        assert msg.id is not None

        # Verify transaction is still active (not committed by repository)
        assert db.in_transaction()

        # Rollback discards the message
        await db.rollback()

        # Query in new session should find nothing
        async with async_session_factory() as verify_db:
            found = await message_repository.get_by_id(verify_db, msg.id)
            assert found is None
