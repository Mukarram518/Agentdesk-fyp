"""Integration tests for AgentDesk Web Chat API (Phase 7 - Step 5F).

Verifies the public chat endpoint POST /api/v1/chat/messages:
1. Valid authenticated first-turn request creates conversation and messages (200).
2. Valid authenticated follow-up request preserves conversation thread (200).
3. Missing widget token rejected with 401.
4. Invalid widget token signature/tampered token rejected with 401.
5. Token supplied in query parameter is strictly rejected with 401.
6. Missing Origin header rejected with 403 (no Referer fallback).
7. Disallowed Origin header rejected with 403.
8. Cross-tenant conversation access rejected with 404.
9. Invalid request body (missing request_id, empty message, whitespace, length) returns 422.
10. Client-supplied business_id rejected with 422.
11. ChatService lock acquisition timeout maps to HTTP 503.
12. ChatService lease loss maps to HTTP 503.
13. Redis unavailable maps to HTTP 503.
14. Unexpected internal errors return safe generic HTTP 500 without leaking details.
15. Response JSON matches the documented public contract without internal metadata.
16. Existing API routes (health, auth, businesses, knowledge) remain functional.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict
from unittest.mock import patch
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.exceptions import ServiceUnavailableError
from app.core.redis import get_redis_client
from app.core.widget_auth import generate_widget_token
from app.models.business import Business
from app.models.conversation import Conversation, ConversationChannel
from app.models.message import Message, MessageRole
from app.orchestrator.schemas import (
    AgentTurnOutput,
    AgentType,
    IntentType,
    LanguageCode,
)
from app.repositories.conversation_repository import conversation_repository
from app.services.chat_service import (
    ChatLeaseLostError,
    ChatLockTimeoutError,
    chat_service,
    ConversationNotFoundError,
)

settings = get_settings()
TEST_WIDGET_SECRET = "super-secret-widget-signing-key-for-tests-32b!"


@pytest_asyncio.fixture(autouse=True)
async def setup_widget_secret(monkeypatch):
    """Configures dedicated test widget token secret and cleans up Redis test keys."""
    monkeypatch.setattr(settings, "WIDGET_TOKEN_SECRET", TEST_WIDGET_SECRET)
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


async def create_test_business(
    allowed_origin: str = "https://client.example.com",
    name: str = "Web Chat Biz",
) -> Business:
    """Helper to persist a test business with allowed widget origin."""
    async with async_session_factory() as db:
        biz = Business(
            name=name,
            slug=f"chat-biz-{uuid.uuid4().hex[:8]}",
            allowed_origins=[allowed_origin],
            is_active=True,
        )
        db.add(biz)
        await db.commit()
        await db.refresh(biz)
        return biz


def get_auth_headers(
    business_id: uuid.UUID,
    origin: str = "https://client.example.com",
    secret: str = TEST_WIDGET_SECRET,
    use_bearer: bool = False,
) -> Dict[str, str]:
    """Generates valid widget authentication headers."""
    token = generate_widget_token(business_id=business_id, secret=secret)
    if use_bearer:
        return {
            "Authorization": f"Bearer {token}",
            "Origin": origin,
        }
    return {
        "X-Widget-Token": token,
        "Origin": origin,
    }


# =====================================================================
# 1. Valid Authenticated First-Turn Request
# =====================================================================

@pytest.mark.asyncio
async def test_valid_authenticated_first_turn(async_client: AsyncClient):
    """Verifies that a valid widget request without conversation_id starts a new thread."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)
    req_id = str(uuid.uuid4())

    payload = {
        "message": "What are your services?",
        "request_id": req_id,
    }

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()

    assert "conversation_id" in data
    assert uuid.UUID(data["conversation_id"])
    assert "message" in data
    assert data["message"]["role"] == "assistant"
    assert data["message"]["content"] != ""
    assert "id" in data["message"]
    assert "created_at" in data["message"]


# =====================================================================
# 2. Valid Authenticated Follow-Up Request
# =====================================================================

@pytest.mark.asyncio
async def test_valid_authenticated_follow_up(async_client: AsyncClient):
    """Verifies that a follow-up request in an existing conversation preserves thread identity."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id, use_bearer=True)

    # First turn
    turn1_payload = {
        "message": "Hello",
        "request_id": str(uuid.uuid4()),
    }
    res1 = await async_client.post("/api/v1/chat/messages", json=turn1_payload, headers=headers)
    assert res1.status_code == 200
    conv_id = res1.json()["conversation_id"]

    # Follow-up turn
    turn2_payload = {
        "conversation_id": conv_id,
        "message": "Tell me more about pricing",
        "request_id": str(uuid.uuid4()),
    }
    res2 = await async_client.post("/api/v1/chat/messages", json=turn2_payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["conversation_id"] == conv_id
    assert data2["message"]["role"] == "assistant"
    assert data2["message"]["id"] != res1.json()["message"]["id"]


# =====================================================================
# 3. Missing Widget Token
# =====================================================================

@pytest.mark.asyncio
async def test_missing_widget_token(async_client: AsyncClient):
    """Verifies that requests without a widget token return HTTP 401."""
    payload = {
        "message": "Hello",
        "request_id": str(uuid.uuid4()),
    }
    headers = {"Origin": "https://client.example.com"}

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
    assert res.status_code == 401
    assert "missing" in res.text.lower() or "token" in res.text.lower()


# =====================================================================
# 4. Invalid Widget Token
# =====================================================================

@pytest.mark.asyncio
async def test_invalid_widget_token(async_client: AsyncClient):
    """Verifies that requests with a forged or invalid token return HTTP 401."""
    payload = {
        "message": "Hello",
        "request_id": str(uuid.uuid4()),
    }
    headers = {
        "X-Widget-Token": "invalid.tampered.token-signature",
        "Origin": "https://client.example.com",
    }

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
    assert res.status_code == 401
    assert "invalid" in res.text.lower() or "malformed" in res.text.lower()


# =====================================================================
# 5. Token Supplied in Query Parameter is Rejected
# =====================================================================

@pytest.mark.asyncio
async def test_token_supplied_in_query_parameter_rejected(async_client: AsyncClient):
    """Verifies that widget tokens sent via query parameters are strictly rejected with 401."""
    biz = await create_test_business()
    valid_token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET)

    payload = {
        "message": "Hello query token",
        "request_id": str(uuid.uuid4()),
    }
    headers = {"Origin": "https://client.example.com"}

    # Attempt sending token via query param
    url = f"/api/v1/chat/messages?widget_token={valid_token}"
    res = await async_client.post(url, json=payload, headers=headers)

    assert res.status_code == 401
    assert "query parameter is not allowed" in res.json()["detail"].lower()


# =====================================================================
# 6. Missing Origin Header (No Referer Fallback for POST)
# =====================================================================

@pytest.mark.asyncio
async def test_missing_origin_header(async_client: AsyncClient):
    """Verifies that POST chat requests without Origin header return 403 even if Referer is present."""
    biz = await create_test_business()
    token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET)

    payload = {
        "message": "Origin check",
        "request_id": str(uuid.uuid4()),
    }
    # Referer provided, but Origin missing
    headers = {
        "X-Widget-Token": token,
        "Referer": "https://client.example.com/widget-page",
    }

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
    assert res.status_code == 403
    assert "origin" in res.text.lower()


# =====================================================================
# 7. Disallowed Origin Header
# =====================================================================

@pytest.mark.asyncio
async def test_disallowed_origin_header(async_client: AsyncClient):
    """Verifies that requests from unauthorized origins return HTTP 403."""
    biz = await create_test_business(allowed_origin="https://authorized.example.com")
    token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET)

    payload = {
        "message": "Testing origin security",
        "request_id": str(uuid.uuid4()),
    }
    headers = {
        "X-Widget-Token": token,
        "Origin": "https://malicious-attacker.com",
    }

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
    assert res.status_code == 403
    assert "origin" in res.text.lower()


# =====================================================================
# 8. Cross-Tenant Conversation Access
# =====================================================================

@pytest.mark.asyncio
async def test_cross_tenant_conversation_access(async_client: AsyncClient):
    """Verifies that requesting another tenant's conversation ID returns HTTP 404."""
    biz_a = await create_test_business(name="Tenant A")
    biz_b = await create_test_business(name="Tenant B")

    # Create conversation for Tenant A
    async with async_session_factory() as db:
        conv_a = await conversation_repository.create_conversation(
            db=db, business_id=biz_a.id, channel=ConversationChannel.WEB.value
        )
        await db.commit()

    # Tenant B tries to message Tenant A's conversation
    headers_b = get_auth_headers(biz_b.id)
    payload = {
        "conversation_id": str(conv_a.id),
        "message": "Unauthorized intrusion attempt",
        "request_id": str(uuid.uuid4()),
    }

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers_b)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# =====================================================================
# 9. Invalid Request Body
# =====================================================================

@pytest.mark.asyncio
async def test_invalid_request_body_validation(async_client: AsyncClient):
    """Verifies that invalid payloads fail Pydantic validation with HTTP 422."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)

    # 1. Missing request_id
    res1 = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "Valid text"},
        headers=headers,
    )
    assert res1.status_code == 422

    # 2. Empty message
    res2 = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "", "request_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert res2.status_code == 422

    # 3. Whitespace-only message
    res3 = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "   \n\t  ", "request_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert res3.status_code == 422

    # 4. Message exceeds 2000 characters
    res4 = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "x" * 2001, "request_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert res4.status_code == 422


# =====================================================================
# 10. Client-Supplied business_id Rejected
# =====================================================================

@pytest.mark.asyncio
async def test_client_supplied_business_id_rejected(async_client: AsyncClient):
    """Verifies that passing business_id in payload is rejected with 422 (extra='forbid')."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)

    payload = {
        "message": "Hello",
        "request_id": str(uuid.uuid4()),
        "business_id": str(biz.id),  # Client attempting to supply tenant identity
    }

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
    assert res.status_code == 422
    assert "extra_forbidden" in str(res.json()).lower() or "business_id" in str(res.json()).lower()


# =====================================================================
# 11. ChatService Lock Timeout Maps to 503
# =====================================================================

@pytest.mark.asyncio
async def test_chat_service_lock_timeout_maps_to_503(async_client: AsyncClient):
    """Verifies that ChatLockTimeoutError from service maps to HTTP 503 with Retry-After header."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)
    payload = {
        "message": "Lock timeout test",
        "request_id": str(uuid.uuid4()),
    }

    with patch.object(
        chat_service,
        "handle_chat_turn",
        side_effect=ChatLockTimeoutError("Chat coordination timeout. Please retry shortly."),
    ):
        res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
        assert res.status_code == 503
        assert "timeout" in res.json()["detail"].lower()
        assert "retry-after" in res.headers


# =====================================================================
# 12. ChatService Lease Loss Maps to 503
# =====================================================================

@pytest.mark.asyncio
async def test_chat_service_lease_loss_maps_to_503(async_client: AsyncClient):
    """Verifies that ChatLeaseLostError from service maps to HTTP 503 with Retry-After header."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)
    payload = {
        "message": "Lease loss test",
        "request_id": str(uuid.uuid4()),
    }

    with patch.object(
        chat_service,
        "handle_chat_turn",
        side_effect=ChatLeaseLostError("Distributed lock lease expired during processing."),
    ):
        res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
        assert res.status_code == 503
        assert "lease expired" in res.json()["detail"].lower()
        assert "retry-after" in res.headers


# =====================================================================
# 13. Redis Unavailable Maps to 503
# =====================================================================

@pytest.mark.asyncio
async def test_redis_unavailable_maps_to_503(async_client: AsyncClient):
    """Verifies that ServiceUnavailableError maps to HTTP 503 with Retry-After header."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)
    payload = {
        "message": "Redis down test",
        "request_id": str(uuid.uuid4()),
    }

    with patch.object(
        chat_service,
        "handle_chat_turn",
        side_effect=ServiceUnavailableError("Redis", "Chat coordination service temporarily unavailable."),
    ):
        res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
        assert res.status_code == 503
        assert "temporarily unavailable" in res.json()["detail"].lower()
        assert "retry-after" in res.headers


# =====================================================================
# 14. Unexpected Internal Errors Return Safe 500
# =====================================================================

@pytest.mark.asyncio
async def test_unexpected_internal_error_returns_safe_500(async_client: AsyncClient):
    """Verifies that unexpected unhandled errors return safe generic 500 without leaking stack trace."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)
    payload = {
        "message": "Internal error check",
        "request_id": str(uuid.uuid4()),
    }

    with patch.object(
        chat_service,
        "handle_chat_turn",
        side_effect=RuntimeError("Secret database connection failure: postgres://user:secretpass@host:5432/db"),
    ):
        res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
        assert res.status_code == 500
        data = res.json()
        assert data["detail"] == "An unexpected error occurred while processing your chat request."
        # Confirm no credentials or raw exception messages leaked
        assert "secretpass" not in res.text
        assert "postgres://" not in res.text
        assert "RuntimeError" not in res.text


# =====================================================================
# 15. Response JSON Matches Documented Contract
# =====================================================================

@pytest.mark.asyncio
async def test_response_json_matches_documented_contract(async_client: AsyncClient):
    """Verifies response structure contains strictly documented fields and no internal metadata."""
    biz = await create_test_business()
    headers = get_auth_headers(biz.id)
    payload = {
        "message": "Verify contract schema",
        "request_id": str(uuid.uuid4()),
    }

    res = await async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Top-level keys must ONLY be conversation_id and message
    assert set(data.keys()) == {"conversation_id", "message"}

    # Message keys must ONLY be id, role, content, created_at
    assert set(data["message"].keys()) == {"id", "role", "content", "created_at"}

    # Sensitive/internal metadata must NOT be present
    forbidden_fields = [
        "sources", "usage", "token_usage", "confidence", "agent",
        "intent", "provider", "model", "metadata", "turn_time_ms",
        "business_id", "request_id", "reply_to_id",
    ]
    for field in forbidden_fields:
        assert field not in data, f"Field '{field}' leaked in top-level response"
        assert field not in data["message"], f"Field '{field}' leaked in message object"


# =====================================================================
# 16. Existing API Routes Remain Functional
# =====================================================================

@pytest.mark.asyncio
async def test_existing_api_routes_remain_functional(async_client: AsyncClient):
    """Verifies that registering chat routes did not disrupt existing routes and endpoints."""
    # 1. Root health endpoint
    res_health = await async_client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] in ("healthy", "degraded")

    # 2. V1 health endpoint
    res_v1_health = await async_client.get("/api/v1/health")
    assert res_v1_health.status_code == 200

    # 3. V1 auth endpoint is mounted and responds with validation error on empty payload
    res_auth = await async_client.post("/api/v1/auth/login", json={})
    assert res_auth.status_code == 422

    # 4. Root service info endpoint
    res_root = await async_client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["app"] == settings.APP_NAME


# =====================================================================
# 17. High Concurrency: 20 Simultaneous Duplicate Requests
# =====================================================================

@pytest.mark.asyncio
async def test_high_concurrency_twenty_simultaneous_duplicate_requests(async_client: AsyncClient):
    """Verifies that 20 simultaneous duplicate requests with identical (business_id, request_id):
    1. Are safely serialized by the distributed lock.
    2. Exactly 1 AI orchestration turn occurs.
    3. Exactly 1 user message and 1 assistant message are persisted in the database.
    4. All 20 requests succeed with HTTP 200.
    5. All 20 responses return identical conversation_id and message.id.
    6. Zero database constraint violations, deadlocks, or duplicate rows.
    """
    biz = await create_test_business(name="20-Worker Concurrency Biz")
    headers = get_auth_headers(biz.id)
    req_id = uuid.uuid4()
    payload = {
        "message": "Twenty simultaneous workers testing idempotency",
        "request_id": str(req_id),
    }

    call_counter = 0

    async def delayed_handle_turn(*args, **kwargs):
        nonlocal call_counter
        call_counter += 1
        await asyncio.sleep(0.08)
        return AgentTurnOutput(
            response="Consistent twenty-worker answer.",
            language=LanguageCode.EN,
            intent=IntentType.FAQ,
            agent=AgentType.CHAT,
            confidence=0.95,
        )

    # Patch orchestrator to count calls and add slight latency
    with patch.object(chat_service.orchestrator, "handle_turn", side_effect=delayed_handle_turn):
        # Fire 20 simultaneous requests
        tasks = [
            async_client.post("/api/v1/chat/messages", json=payload, headers=headers)
            for _ in range(20)
        ]
        responses = await asyncio.gather(*tasks)

    # 1. All 20 requests must return HTTP 200
    for r in responses:
        assert r.status_code == 200, f"Worker returned unexpected status {r.status_code}: {r.text}"

    # 2. Extract conversation_id and message.id across all 20 responses
    results = [r.json() for r in responses]
    conversation_ids = {r["conversation_id"] for r in results}
    message_ids = {r["message"]["id"] for r in results}
    contents = {r["message"]["content"] for r in results}

    # All 20 workers got the exact same conversation and message
    assert len(conversation_ids) == 1
    assert len(message_ids) == 1
    assert len(contents) == 1
    assert "Consistent twenty-worker answer." in contents

    # 3. AI Orchestrator was executed exactly once
    assert call_counter == 1

    # 4. Check DB state: exactly 1 conversation and 2 messages
    async with async_session_factory() as db:
        conv_id = uuid.UUID(list(conversation_ids)[0])
        messages = await conversation_repository.get_recent_messages(
            db=db, business_id=biz.id, conversation_id=conv_id, limit=20
        )
        assert len(messages) == 2
        user_msgs = [m for m in messages if m.role == MessageRole.USER.value]
        asst_msgs = [m for m in messages if m.role == MessageRole.ASSISTANT.value]
        assert len(user_msgs) == 1
        assert len(asst_msgs) == 1
        assert asst_msgs[0].reply_to_id == user_msgs[0].id
