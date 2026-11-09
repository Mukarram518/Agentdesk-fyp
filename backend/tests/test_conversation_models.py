"""Unit tests for Phase 7 Conversation, Message, and Business origin models.

Verifies:
1. Conversation model fields, column defaults, constraints, and relationships.
2. Message model fields, role constraints, non-empty content constraint, idempotency request_id, and relationships.
3. Business model allowed_origins configuration, safe empty default, and origin validation helper.
4. Correct registration in app.models and Base.metadata.tables.
"""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import (
    Base,
    Business,
    Conversation,
    ConversationChannel,
    ConversationStatus,
    Message,
    MessageRole,
)


@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No live database connection needed for pure model definition tests."""
    yield


@pytest.fixture(autouse=True)
def auto_reset_rate_limits():
    """No rate limit reset needed for in-memory model tests."""
    yield


# =====================================================================
# 1. Registration and Metadata Presence Tests
# =====================================================================

def test_models_registered_in_declarative_base():
    """Verifies that conversations, messages, and businesses tables are registered in Base.metadata."""
    table_names = Base.metadata.tables.keys()
    assert "conversations" in table_names
    assert "messages" in table_names
    assert "businesses" in table_names


def test_models_public_exports_from_app_models():
    """Verifies all required model classes and enums can be imported directly from app.models."""
    from app import models

    assert hasattr(models, "Conversation")
    assert hasattr(models, "ConversationChannel")
    assert hasattr(models, "ConversationStatus")
    assert hasattr(models, "Message")
    assert hasattr(models, "MessageRole")
    assert hasattr(models, "Business")


# =====================================================================
# 2. Conversation Model Tests
# =====================================================================

def test_conversation_model_columns_and_types():
    """Verifies all required Conversation columns, nullabilities, and foreign keys."""
    table = Base.metadata.tables["conversations"]

    # 1. Primary key
    assert "id" in table.c
    assert table.c.id.primary_key is True
    assert isinstance(table.c.id.type, UUID)
    assert table.c.id.default.is_callable is True
    assert table.c.id.default.arg.__name__ == "uuid4"

    # 2. Foreign key to businesses.id
    assert "business_id" in table.c
    assert table.c.business_id.nullable is False
    assert table.c.business_id.index is True
    fk = list(table.c.business_id.foreign_keys)[0]
    assert fk.target_fullname == "businesses.id"
    assert fk.ondelete == "CASCADE"

    # 3. Channel with default "web"
    assert "channel" in table.c
    assert table.c.channel.nullable is False
    assert table.c.channel.default.arg == "web"
    assert table.c.channel.server_default.arg.text == "'web'"

    # 4. Language, status, timestamps, outcome, summary
    assert "language" in table.c
    assert table.c.language.nullable is False
    assert table.c.language.default.arg == "en"
    assert table.c.language.server_default.arg.text == "'en'"

    assert "status" in table.c
    assert table.c.status.nullable is False
    assert table.c.status.default.arg == "active"
    assert table.c.status.server_default.arg.text == "'active'"

    assert "started_at" in table.c
    assert table.c.started_at.nullable is False

    assert "ended_at" in table.c
    assert table.c.ended_at.nullable is True

    assert "outcome" in table.c
    assert table.c.outcome.nullable is True

    assert "summary" in table.c
    assert table.c.summary.nullable is True

    assert "created_at" in table.c
    assert table.c.created_at.nullable is False

    assert "updated_at" in table.c
    assert table.c.updated_at.nullable is False

    # 5. Composite unique constraint on (id, business_id)
    from sqlalchemy import UniqueConstraint
    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    uq_names = {c.name for c in unique_constraints}
    assert "uq_conversations_id_business_id" in uq_names
    uq = next(c for c in unique_constraints if c.name == "uq_conversations_id_business_id")
    assert set(uq.columns.keys()) == {"id", "business_id"}


def test_conversation_instance_instantiation():
    """Verifies instantiation and attribute values for Conversation."""
    conv_id = uuid.uuid4()
    biz_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    conv = Conversation(
        id=conv_id,
        business_id=biz_id,
        channel=ConversationChannel.WEB.value,
        language="en",
        status=ConversationStatus.ACTIVE.value,
        started_at=now,
    )

    assert conv.id == conv_id
    assert conv.business_id == biz_id
    assert conv.channel == "web"
    assert conv.language == "en"
    assert conv.status == "active"
    assert conv.started_at == now
    assert conv.ended_at is None
    assert conv.outcome is None
    assert conv.summary is None
    assert repr(conv).startswith("<Conversation")


def test_conversation_custom_attributes():
    """Verifies Conversation with custom attributes (WhatsApp, Urdu, completed)."""
    biz_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    conv = Conversation(
        business_id=biz_id,
        channel=ConversationChannel.WHATSAPP.value,
        language="ur",
        status=ConversationStatus.COMPLETED.value,
        started_at=now,
        ended_at=now,
        outcome="booked_appointment",
        summary="Customer booked Dr. Ahmed at 3 PM.",
    )

    assert conv.channel == "whatsapp"
    assert conv.language == "ur"
    assert conv.status == "completed"
    assert conv.outcome == "booked_appointment"
    assert conv.summary == "Customer booked Dr. Ahmed at 3 PM."
    assert conv.ended_at == now


# =====================================================================
# 3. Message Model Tests
# =====================================================================

def test_message_model_columns_and_types():
    """Verifies Message columns, nullabilities, idempotency key, and foreign keys."""
    table = Base.metadata.tables["messages"]

    # 1. Primary key
    assert "id" in table.c
    assert table.c.id.primary_key is True
    assert isinstance(table.c.id.type, UUID)
    assert table.c.id.default.is_callable is True
    assert table.c.id.default.arg.__name__ == "uuid4"

    # 2. Conversation foreign key and composite relationship
    assert "conversation_id" in table.c
    assert table.c.conversation_id.nullable is False
    assert table.c.conversation_id.index is True

    # 3. Business foreign key
    assert "business_id" in table.c
    assert table.c.business_id.nullable is False
    assert table.c.business_id.index is True
    biz_fks = [fk for fk in table.c.business_id.foreign_keys if fk.target_fullname == "businesses.id"]
    assert len(biz_fks) == 1
    assert biz_fks[0].ondelete == "CASCADE"

    # 4. Role and content
    assert "role" in table.c
    assert table.c.role.nullable is False

    assert "content" in table.c
    assert table.c.content.nullable is False

    # 5. Request ID for idempotency (nullable UUID, indexed)
    assert "request_id" in table.c
    assert table.c.request_id.nullable is True
    assert table.c.request_id.index is True
    assert isinstance(table.c.request_id.type, UUID)

    # 6. Reply-to ID (nullable UUID, self-referencing foreign key, indexed)
    assert "reply_to_id" in table.c
    assert table.c.reply_to_id.nullable is True
    assert table.c.reply_to_id.index is True
    assert isinstance(table.c.reply_to_id.type, UUID)
    reply_fks = [fk for fk in table.c.reply_to_id.foreign_keys if fk.target_fullname == "messages.id"]
    assert len(reply_fks) == 1
    assert reply_fks[0].ondelete == "SET NULL"

    # 7. Timestamp
    assert "created_at" in table.c
    assert table.c.created_at.nullable is False


def test_message_check_constraints():
    """Verifies that check constraints for role, non-empty content, and reply-to restrictions are present."""
    table = Base.metadata.tables["messages"]
    constraints = {c.name: c for c in table.constraints if hasattr(c, "sqltext")}

    assert "check_message_role" in constraints
    assert "role IN ('user', 'assistant')" in str(constraints["check_message_role"].sqltext)

    assert "check_message_content_not_empty" in constraints
    assert "length(trim(content)) > 0" in str(constraints["check_message_content_not_empty"].sqltext)

    assert "check_message_reply_to_assistant_only" in constraints
    assert "reply_to_id IS NULL OR role = 'assistant'" in str(constraints["check_message_reply_to_assistant_only"].sqltext)


def test_message_instance_creation():
    """Verifies instantiation of user and assistant messages with idempotency and reply_to."""
    msg_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    biz_id = uuid.uuid4()
    req_id = uuid.uuid4()
    asst_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    user_msg = Message(
        id=msg_id,
        conversation_id=conv_id,
        business_id=biz_id,
        role=MessageRole.USER.value,
        content="What time do you open tomorrow?",
        request_id=req_id,
        reply_to_id=None,
        created_at=now,
    )

    assert user_msg.id == msg_id
    assert user_msg.conversation_id == conv_id
    assert user_msg.business_id == biz_id
    assert user_msg.role == "user"
    assert user_msg.content == "What time do you open tomorrow?"
    assert user_msg.request_id == req_id
    assert user_msg.reply_to_id is None
    assert user_msg.created_at == now
    assert repr(user_msg).startswith("<Message")

    asst_msg = Message(
        id=asst_id,
        conversation_id=conv_id,
        business_id=biz_id,
        role=MessageRole.ASSISTANT.value,
        content="We open at 9:00 AM tomorrow.",
        request_id=None,
        reply_to_id=msg_id,
    )
    assert asst_msg.id == asst_id
    assert asst_msg.business_id == biz_id
    assert asst_msg.role == "assistant"
    assert asst_msg.request_id is None
    assert asst_msg.reply_to_id == msg_id


# =====================================================================
# 4. Business Website-Origin Tests
# =====================================================================

def test_business_allowed_origins_column():
    """Verifies allowed_origins column on businesses table as JSONB with empty default."""
    table = Base.metadata.tables["businesses"]

    assert "allowed_origins" in table.c
    assert isinstance(table.c.allowed_origins.type, JSONB)
    assert table.c.allowed_origins.nullable is False
    assert table.c.allowed_origins.default.is_callable is True
    assert table.c.allowed_origins.default.arg.__name__ == "list"
    assert table.c.allowed_origins.server_default.arg.text == "'[]'::jsonb"


def test_business_allowed_origins_default_value():
    """Verifies that Business instance defaults to an empty list and does not allow arbitrary origins."""
    biz = Business(name="Dental Care", slug="dental-care")

    # allowed_website_origins safe getter returns empty list
    assert biz.allowed_website_origins == []

    # Arbitrary origins must be rejected by default
    assert biz.is_origin_allowed("https://arbitrary-site.com") is False
    assert biz.is_origin_allowed("http://localhost:3000") is False
    assert biz.is_origin_allowed("") is False
    assert biz.is_origin_allowed(None) is False
    assert biz.is_origin_allowed("*") is False


def test_business_allowed_origins_explicit_empty_list():
    """Verifies that Business with explicit empty list rejects all origins."""
    biz = Business(name="Dental Care", slug="dental-care", allowed_origins=[])

    assert biz.allowed_origins == []
    assert biz.allowed_website_origins == []
    assert biz.is_origin_allowed("https://example.com") is False


def test_business_allowed_origins_configuration_and_matching():
    """Verifies that explicitly configured origins match correctly with normalization."""
    biz = Business(
        name="Tech Solutions",
        slug="tech-solutions",
        allowed_origins=["https://techsolutions.com", "https://app.techsolutions.com/"],
    )

    # Exact match
    assert biz.is_origin_allowed("https://techsolutions.com") is True

    # Trailing slash normalization
    assert biz.is_origin_allowed("https://techsolutions.com/") is True
    assert biz.is_origin_allowed("https://app.techsolutions.com") is True

    # Case-insensitive matching
    assert biz.is_origin_allowed("HTTPS://TECHSOLUTIONS.COM") is True

    # Unlisted origins rejected
    assert biz.is_origin_allowed("https://other-site.com") is False
    assert biz.is_origin_allowed("https://malicious-techsolutions.com") is False


def test_business_allowed_website_origins_setter_alias():
    """Verifies that allowed_website_origins property alias acts as a drop-in setter."""
    biz = Business(name="Shop", slug="shop")
    biz.allowed_website_origins = ["https://myshop.pk"]

    assert biz.allowed_origins == ["https://myshop.pk"]
    assert biz.is_origin_allowed("https://myshop.pk") is True


# =====================================================================
# 5. Relationship Wiring Tests
# =====================================================================

def test_relationship_declarations():
    """Verifies SQLAlchemy relationship mapping between Business, Conversation, and Message."""
    # 1. Business -> conversations
    biz_mapper = inspect(Business)
    assert "conversations" in biz_mapper.relationships
    biz_rel = biz_mapper.relationships["conversations"]
    assert biz_rel.target.name == "conversations"
    assert biz_rel.back_populates == "business"

    # 2. Conversation -> business & messages
    conv_mapper = inspect(Conversation)
    assert "business" in conv_mapper.relationships
    assert "messages" in conv_mapper.relationships

    conv_biz_rel = conv_mapper.relationships["business"]
    assert conv_biz_rel.target.name == "businesses"
    assert conv_biz_rel.back_populates == "conversations"

    conv_msg_rel = conv_mapper.relationships["messages"]
    assert conv_msg_rel.target.name == "messages"
    assert conv_msg_rel.back_populates == "conversation"

    # 3. Message -> conversation
    msg_mapper = inspect(Message)
    assert "conversation" in msg_mapper.relationships
    msg_conv_rel = msg_mapper.relationships["conversation"]
    assert msg_conv_rel.target.name == "conversations"
    assert msg_conv_rel.back_populates == "messages"
