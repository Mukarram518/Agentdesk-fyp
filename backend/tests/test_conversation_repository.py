"""Tests for ConversationRepository (Phase 7 - Step 2).

Verifies:
1. Creating a conversation with defaults and custom attributes.
2. Retrieving a conversation by ID with strict tenant isolation.
3. Eager-loading messages via include_messages.
4. Updating conversation language and status with tenant isolation.
5. Closing a conversation (ended_at, outcome, summary) with tenant isolation.
6. Unified update_conversation method with tenant isolation.
7. Retrieving bounded recent messages in chronological order.
8. Tenant isolation for bounded recent messages (cross-business returns empty list).
9. Listing conversations for a business with filtering and pagination.
"""

from datetime import datetime, timezone, timedelta
import uuid
import pytest

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.conversation import (
    Conversation,
    ConversationChannel,
    ConversationStatus,
)
from app.models.message import Message, MessageRole
from app.repositories.conversation_repository import conversation_repository
from app.repositories.message_repository import message_repository


async def create_test_business(db, name: str = "Chat Repo Biz") -> Business:
    """Helper to persist a test business tenant."""
    biz = Business(
        name=name,
        slug=f"conv-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


@pytest.mark.asyncio
async def test_create_conversation_defaults():
    """Verifies creating a conversation with default channel, language, and status."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Default Conv Biz")

        conv = await conversation_repository.create_conversation(
            db=db,
            business_id=biz.id,
        )

        assert conv.id is not None
        assert conv.business_id == biz.id
        assert conv.channel == "web"
        assert conv.language == "en"
        assert conv.status == "active"
        assert conv.started_at is not None
        assert conv.ended_at is None
        assert conv.outcome is None
        assert conv.summary is None
        assert conv.created_at is not None
        assert conv.updated_at is not None


@pytest.mark.asyncio
async def test_create_conversation_custom_attributes():
    """Verifies creating a conversation with custom channel, language, and status."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Custom Conv Biz")
        custom_start = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)

        conv = await conversation_repository.create_conversation(
            db=db,
            business_id=biz.id,
            channel=ConversationChannel.WHATSAPP.value,
            language="ur",
            status=ConversationStatus.COMPLETED.value,
            started_at=custom_start,
        )

        assert conv.channel == "whatsapp"
        assert conv.language == "ur"
        assert conv.status == "completed"
        assert conv.started_at == custom_start


@pytest.mark.asyncio
async def test_get_by_id_tenant_isolation():
    """Verifies that conversation lookup strictly enforces tenant boundaries."""
    async with async_session_factory() as db:
        biz_1 = await create_test_business(db, "Tenant 1 Biz")
        biz_2 = await create_test_business(db, "Tenant 2 Biz")

        conv_1 = await conversation_repository.create_conversation(
            db=db,
            business_id=biz_1.id,
        )

        # 1. Successful lookup by owning business
        found = await conversation_repository.get_by_id(db, biz_1.id, conv_1.id)
        assert found is not None
        assert found.id == conv_1.id
        assert found.business_id == biz_1.id

        # 2. Cross-tenant lookup returns None
        cross_found = await conversation_repository.get_by_id(db, biz_2.id, conv_1.id)
        assert cross_found is None

        # 3. Nonexistent conversation returns None
        assert await conversation_repository.get_by_id(db, biz_1.id, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_get_by_id_include_messages():
    """Verifies include_messages eagerly loads associated conversation messages."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Eager Load Biz")
        conv = await conversation_repository.create_conversation(db=db, business_id=biz.id)

        await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            role=MessageRole.USER.value,
            content="Hello there!",
        )
        await message_repository.create_message(
            db=db,
            conversation_id=conv.id,
            role=MessageRole.ASSISTANT.value,
            content="Hi! How can I assist you today?",
        )

        # Lookup with eager loaded messages
        loaded = await conversation_repository.get_by_id(
            db, biz.id, conv.id, include_messages=True
        )
        assert loaded is not None
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "Hello there!"
        assert loaded.messages[1].content == "Hi! How can I assist you today?"


@pytest.mark.asyncio
async def test_update_language_and_status():
    """Verifies updating language and status while respecting tenant boundaries."""
    async with async_session_factory() as db:
        biz_1 = await create_test_business(db, "Language Update Biz 1")
        biz_2 = await create_test_business(db, "Language Update Biz 2")

        conv = await conversation_repository.create_conversation(
            db=db, business_id=biz_1.id, language="en", status="active"
        )

        # Cross-tenant update attempts return None and make no modifications
        assert await conversation_repository.update_language(db, biz_2.id, conv.id, "ur") is None
        assert await conversation_repository.update_status(db, biz_2.id, conv.id, "completed") is None

        # Verify unchanged
        refetched = await conversation_repository.get_by_id(db, biz_1.id, conv.id)
        assert refetched.language == "en"
        assert refetched.status == "active"

        # Authorized tenant updates succeed
        updated_lang = await conversation_repository.update_language(db, biz_1.id, conv.id, "ur")
        assert updated_lang is not None
        assert updated_lang.language == "ur"

        updated_status = await conversation_repository.update_status(
            db, biz_1.id, conv.id, ConversationStatus.ABANDONED.value
        )
        assert updated_status is not None
        assert updated_status.status == "abandoned"


@pytest.mark.asyncio
async def test_close_conversation():
    """Verifies closing a conversation updates ended_at, status, outcome, and summary."""
    async with async_session_factory() as db:
        biz_1 = await create_test_business(db, "Close Biz 1")
        biz_2 = await create_test_business(db, "Close Biz 2")

        conv = await conversation_repository.create_conversation(db=db, business_id=biz_1.id)

        # Cross-tenant close returns None
        assert await conversation_repository.close_conversation(
            db=db,
            business_id=biz_2.id,
            conversation_id=conv.id,
            outcome="lead_captured",
        ) is None

        # Authorized close succeeds
        custom_ended = datetime(2026, 6, 1, 15, 30, 0, tzinfo=timezone.utc)
        closed = await conversation_repository.close_conversation(
            db=db,
            business_id=biz_1.id,
            conversation_id=conv.id,
            status=ConversationStatus.COMPLETED.value,
            outcome="appointment_booked",
            summary="Customer scheduled a consultation for Tuesday.",
            ended_at=custom_ended,
        )

        assert closed is not None
        assert closed.status == "completed"
        assert closed.outcome == "appointment_booked"
        assert closed.summary == "Customer scheduled a consultation for Tuesday."
        assert closed.ended_at == custom_ended


@pytest.mark.asyncio
async def test_update_conversation_general():
    """Verifies general multi-attribute update on conversation."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "General Update Biz")
        conv = await conversation_repository.create_conversation(db=db, business_id=biz.id)

        updated = await conversation_repository.update_conversation(
            db=db,
            business_id=biz.id,
            conversation_id=conv.id,
            language="roman_urdu",
            status="paused",
            outcome="in_progress",
            summary="Partial qualification complete.",
        )

        assert updated is not None
        assert updated.language == "roman_urdu"
        assert updated.status == "paused"
        assert updated.outcome == "in_progress"
        assert updated.summary == "Partial qualification complete."


@pytest.mark.asyncio
async def test_get_recent_messages_ordering_and_limit():
    """Verifies get_recent_messages retrieves the most recent N messages in chronological order."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Recent Msg Biz")
        conv = await conversation_repository.create_conversation(db=db, business_id=biz.id)

        # Insert 5 sequential messages
        base_time = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
        created_msgs = []
        for i in range(5):
            msg = Message(
                conversation_id=conv.id,
                business_id=biz.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i + 1}",
                created_at=base_time + timedelta(minutes=i),
            )
            db.add(msg)
            created_msgs.append(msg)
        await db.flush()

        # Retrieve last 3 messages: should be Message 3, Message 4, Message 5 in chronological order
        recent_3 = await conversation_repository.get_recent_messages(
            db=db,
            business_id=biz.id,
            conversation_id=conv.id,
            limit=3,
        )

        assert len(recent_3) == 3
        assert [m.content for m in recent_3] == ["Message 3", "Message 4", "Message 5"]

        # Retrieve all with limit=10: should be Message 1..5 in chronological order
        recent_all = await conversation_repository.get_recent_messages(
            db=db,
            business_id=biz.id,
            conversation_id=conv.id,
            limit=10,
        )
        assert len(recent_all) == 5
        assert [m.content for m in recent_all] == [
            "Message 1",
            "Message 2",
            "Message 3",
            "Message 4",
            "Message 5",
        ]


@pytest.mark.asyncio
async def test_get_recent_messages_tenant_isolation():
    """Verifies that cross-tenant access to get_recent_messages returns an empty list."""
    async with async_session_factory() as db:
        biz_1 = await create_test_business(db, "Tenant 1 Msg Biz")
        biz_2 = await create_test_business(db, "Tenant 2 Msg Biz")

        conv_1 = await conversation_repository.create_conversation(db=db, business_id=biz_1.id)
        await message_repository.create_message(
            db=db,
            conversation_id=conv_1.id,
            role="user",
            content="Sensitive business data",
        )

        # Cross-tenant retrieval
        leaked = await conversation_repository.get_recent_messages(
            db=db,
            business_id=biz_2.id,
            conversation_id=conv_1.id,
            limit=10,
        )
        assert leaked == []


@pytest.mark.asyncio
async def test_list_by_business_filtering_and_pagination():
    """Verifies listing conversations for a business with channel/status filters and pagination."""
    async with async_session_factory() as db:
        biz_1 = await create_test_business(db, "List Biz 1")
        biz_2 = await create_test_business(db, "List Biz 2")

        c1 = await conversation_repository.create_conversation(
            db=db, business_id=biz_1.id, channel="web", status="active"
        )
        c2 = await conversation_repository.create_conversation(
            db=db, business_id=biz_1.id, channel="web", status="completed"
        )
        c3 = await conversation_repository.create_conversation(
            db=db, business_id=biz_1.id, channel="whatsapp", status="active"
        )
        # Other tenant conversation
        c_other = await conversation_repository.create_conversation(
            db=db, business_id=biz_2.id, channel="web", status="active"
        )

        # 1. Total for biz_1
        all_biz_1 = await conversation_repository.list_by_business(db, biz_1.id)
        assert len(all_biz_1) == 3
        assert {c.id for c in all_biz_1} == {c1.id, c2.id, c3.id}

        # 2. Filter by channel="web"
        web_only = await conversation_repository.list_by_business(db, biz_1.id, channel="web")
        assert len(web_only) == 2
        assert {c.id for c in web_only} == {c1.id, c2.id}

        # 3. Filter by status="active"
        active_only = await conversation_repository.list_by_business(db, biz_1.id, status="active")
        assert len(active_only) == 2
        assert {c.id for c in active_only} == {c1.id, c3.id}

        # 4. Pagination
        paginated = await conversation_repository.list_by_business(db, biz_1.id, limit=2, offset=1)
        assert len(paginated) == 2
