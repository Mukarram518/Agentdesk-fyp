"""Unit tests for Phase 7 Web Chat Pydantic schemas (Step 5D).

Verifies:
1. Valid first-message request with no conversation_id.
2. Valid follow-up request with conversation_id.
3. Invalid or missing request_id.
4. Invalid conversation_id.
5. Empty message.
6. Whitespace-only message.
7. Message exceeding 2000 characters (2000 boundary).
8. Valid response structure and serialization.
9. Rejection of unexpected fields (extra="forbid").
10. No business_id accepted from the client.
"""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError

from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageRequest,
    ChatMessageResponse,
)


def test_valid_first_turn_request_no_conversation_id():
    """Verifies valid first message request when conversation_id is omitted or None."""
    req_id = uuid.uuid4()

    # Omitted conversation_id
    req1 = ChatMessageRequest(
        message="What are your consultation timings?",
        request_id=req_id,
    )
    assert req1.conversation_id is None
    assert req1.message == "What are your consultation timings?"
    assert req1.request_id == req_id

    # Explicit None conversation_id
    req2 = ChatMessageRequest(
        conversation_id=None,
        message="Hello AgentDesk",
        request_id=req_id,
    )
    assert req2.conversation_id is None
    assert req2.message == "Hello AgentDesk"


def test_valid_follow_up_request_with_conversation_id():
    """Verifies valid subsequent turn request with explicit conversation_id."""
    conv_id = uuid.uuid4()
    req_id = uuid.uuid4()

    req = ChatMessageRequest(
        conversation_id=conv_id,
        message="Can I book an appointment with Dr. Ahmed?",
        request_id=req_id,
    )
    assert req.conversation_id == conv_id
    assert req.message == "Can I book an appointment with Dr. Ahmed?"
    assert req.request_id == req_id


def test_invalid_or_missing_request_id():
    """Verifies that missing or malformed request_id is rejected by Pydantic validation."""
    # 1. Missing request_id
    with pytest.raises(ValidationError) as exc_info:
        ChatMessageRequest.model_validate({"message": "Hello without request ID"})
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("request_id",) and e["type"] == "missing" for e in errors)

    # 2. Invalid non-UUID request_id
    with pytest.raises(ValidationError) as exc_info2:
        ChatMessageRequest.model_validate({
            "message": "Hello",
            "request_id": "not-a-valid-uuid-string",
        })
    errors2 = exc_info2.value.errors()
    assert any(e["loc"] == ("request_id",) and "uuid" in e["type"] for e in errors2)


def test_invalid_conversation_id():
    """Verifies that non-UUID conversation_id is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ChatMessageRequest.model_validate({
            "conversation_id": "invalid-conv-uuid",
            "message": "Hello",
            "request_id": str(uuid.uuid4()),
        })
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("conversation_id",) and "uuid" in e["type"] for e in errors)


def test_empty_message_rejected():
    """Verifies that completely empty message is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ChatMessageRequest(
            message="",
            request_id=uuid.uuid4(),
        )
    assert "Message content cannot be empty or whitespace-only" in str(exc_info.value)


def test_whitespace_only_message_rejected():
    """Verifies that whitespace-only message strings are rejected."""
    for invalid in ("   ", "\t\t", "\n\n", "   \r\n   "):
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageRequest(
                message=invalid,
                request_id=uuid.uuid4(),
            )
        assert "Message content cannot be empty or whitespace-only" in str(exc_info.value)


def test_message_character_limit_boundaries():
    """Verifies that 2000 characters is accepted, while 2001 characters is rejected."""
    req_id = uuid.uuid4()

    # Exact 2000 character message must pass
    valid_2000_char_msg = "a" * 2000
    req = ChatMessageRequest(
        message=valid_2000_char_msg,
        request_id=req_id,
    )
    assert len(req.message) == 2000

    # 2001 character message must fail
    invalid_2001_char_msg = "a" * 2001
    with pytest.raises(ValidationError) as exc_info:
        ChatMessageRequest(
            message=invalid_2001_char_msg,
            request_id=req_id,
        )
    assert "Message content cannot exceed 2000 characters" in str(exc_info.value) or "at most 2000 characters" in str(exc_info.value)


def test_valid_chat_message_response_structure():
    """Verifies ChatMessageResponse structure and serialization."""
    conv_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    response = ChatMessageResponse(
        conversation_id=conv_id,
        message=ChatMessageItem(
            id=msg_id,
            role="assistant",
            content="We offer primary healthcare and dental procedures.",
            created_at=now,
        ),
    )

    assert response.conversation_id == conv_id
    assert response.message.id == msg_id
    assert response.message.role == "assistant"
    assert response.message.content == "We offer primary healthcare and dental procedures."
    assert response.message.created_at == now

    dumped = response.model_dump()
    assert dumped["conversation_id"] == conv_id
    assert dumped["message"]["id"] == msg_id
    assert dumped["message"]["role"] == "assistant"
    assert dumped["message"]["content"] == "We offer primary healthcare and dental procedures."
    assert "sources" not in dumped
    assert "provider" not in dumped
    assert "prompt" not in dumped


def test_rejection_of_unexpected_fields():
    """Verifies that unexpected fields are strictly rejected via extra='forbid'."""
    with pytest.raises(ValidationError) as exc_info:
        ChatMessageRequest.model_validate({
            "message": "Hello",
            "request_id": str(uuid.uuid4()),
            "unexpected_parameter": "should_be_forbidden",
        })
    errors = exc_info.value.errors()
    assert any(e["type"] == "extra_forbidden" for e in errors)


def test_rejection_of_business_id_from_client():
    """Verifies that client cannot supply business_id in the request payload."""
    with pytest.raises(ValidationError) as exc_info:
        ChatMessageRequest.model_validate({
            "message": "Attempting cross-tenant spoofing",
            "request_id": str(uuid.uuid4()),
            "business_id": str(uuid.uuid4()),
        })
    errors = exc_info.value.errors()
    assert any(
        e["loc"] == ("business_id",) and e["type"] == "extra_forbidden"
        for e in errors
    )
