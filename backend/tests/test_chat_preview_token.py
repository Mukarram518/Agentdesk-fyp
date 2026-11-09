"""Tests for AgentDesk Dashboard Preview Token (Phase 7 - Step 7A).

Verifies the authenticated preview-token endpoint POST /api/v1/chat/preview-token:
1. Authenticated business owner can obtain a preview token (200).
2. Authenticated business admin can obtain a preview token (200).
3. Unauthenticated request receives 401.
4. Regular member receives 403 Forbidden.
5. User without an active business receives 404.
6. Inactive business cannot issue preview tokens (404).
7. Cross-business token issuance is rejected (404).
8. Specific business_id in payload where user is authorized succeeds (200).
9. Extra fields in payload rejected with 422.
10. Preview token expiration matches response and JWT exp claim.
11. Preview token is accepted by POST /api/v1/chat/messages from trusted dashboard origin (200).
12. Preview token is rejected by POST /api/v1/chat/messages from untrusted external origin (403).
13. Preview token missing Origin header is rejected (403).
14. Expired preview token is rejected by chat endpoint (401).
15. Non-boolean is_preview claim type is rejected (401).
16. Public widget token (is_preview=False) strictly obeys business.allowed_origins and cannot use dashboard origin.
17. Empty or invalid trusted-origin configuration fails closed (403).
18. Signing secret is never returned in response or leaked.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, Tuple
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.redis import get_redis_client
from app.core.widget_auth import (
    WidgetTokenError,
    generate_widget_token,
    verify_widget_token,
)
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.user import User

settings = get_settings()
TEST_WIDGET_SECRET = "super-secret-widget-signing-key-for-tests-32b!"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_environment(monkeypatch):
    """Configures test widget secret and cleans up Redis lock keys."""
    monkeypatch.setattr(settings, "WIDGET_TOKEN_SECRET", TEST_WIDGET_SECRET)
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"])

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


async def create_user_and_token(
    async_client: AsyncClient, name: str = "Test User"
) -> Tuple[dict, str]:
    """Helper that registers, logs in, and returns (user_data, session_token)."""
    email = f"preview_user_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"

    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": name},
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()["user"]

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    session_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    async_client.cookies.clear()

    return user_data, session_token


async def create_business_for_user(
    async_client: AsyncClient, session_token: str, name: Optional[str] = None
) -> dict:
    """Helper that creates a business for an authenticated user with a globally unique name and slug."""
    base_name = name or "Preview Test Biz"
    biz_name = f"{base_name} {uuid.uuid4().hex[:8]}"
    res = await async_client.post(
        "/api/v1/businesses",
        json={"name": biz_name},
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert res.status_code == 201
    return res.json()


# =====================================================================
# 1. Preview Token Issuance Tests
# =====================================================================

@pytest.mark.asyncio
async def test_owner_can_obtain_preview_token(async_client: AsyncClient):
    """Verifies that an authenticated business owner can obtain a preview token."""
    _, session_token = await create_user_and_token(async_client, name="Owner User")
    biz = await create_business_for_user(async_client, session_token, name="Owner Clinic")

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert "expires_at" in data

    # Verify token payload
    payload = verify_widget_token(data["token"], secret=TEST_WIDGET_SECRET)
    assert payload.business_id == uuid.UUID(biz["id"])
    assert payload.is_preview is True
    assert payload.token_type == "widget"


@pytest.mark.asyncio
async def test_admin_can_obtain_preview_token(async_client: AsyncClient):
    """Verifies that an authenticated business admin can obtain a preview token."""
    owner_user, owner_token = await create_user_and_token(async_client, name="Owner User")
    biz = await create_business_for_user(async_client, owner_token, name="Admin Managed Biz")

    admin_user, admin_token = await create_user_and_token(async_client, name="Admin User")

    # Add admin user as ADMIN in the business
    async with async_session_factory() as db:
        member = BusinessMember(
            business_id=uuid.UUID(biz["id"]),
            user_id=uuid.UUID(admin_user["id"]),
            role=MemberRole.ADMIN.value,
        )
        db.add(member)
        await db.commit()

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    payload = verify_widget_token(data["token"], secret=TEST_WIDGET_SECRET)
    assert payload.business_id == uuid.UUID(biz["id"])
    assert payload.is_preview is True


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(async_client: AsyncClient):
    """Verifies that unauthenticated requests receive 401."""
    res = await async_client.post("/api/v1/chat/preview-token")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_regular_member_role_rejected_403(async_client: AsyncClient):
    """Verifies that a user with role 'member' receives 403 Forbidden."""
    owner_user, owner_token = await create_user_and_token(async_client, name="Owner User")
    biz = await create_business_for_user(async_client, owner_token, name="Staff Biz")

    staff_user, staff_token = await create_user_and_token(async_client, name="Staff Member")

    # Add staff user as MEMBER
    async with async_session_factory() as db:
        member = BusinessMember(
            business_id=uuid.UUID(biz["id"]),
            user_id=uuid.UUID(staff_user["id"]),
            role=MemberRole.MEMBER.value,
        )
        db.add(member)
        await db.commit()

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert res.status_code == 403
    assert "Only business owners and admins" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_without_business_returns_404(async_client: AsyncClient):
    """Verifies that a user without any business membership receives 404."""
    _, token = await create_user_and_token(async_client, name="No Biz User")

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_inactive_business_returns_404(async_client: AsyncClient):
    """Verifies that an inactive business cannot issue preview tokens."""
    _, token = await create_user_and_token(async_client, name="Inactive Biz User")
    biz = await create_business_for_user(async_client, token, name="To Deactivate")

    # Deactivate business in DB
    async with async_session_factory() as db:
        db_biz = await db.get(Business, uuid.UUID(biz["id"]))
        db_biz.is_active = False
        await db.commit()

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_cross_business_id_in_payload_rejected_404(async_client: AsyncClient):
    """Verifies that an owner cannot request a preview token for another business."""
    _, token_a = await create_user_and_token(async_client, name="Owner A")
    biz_a = await create_business_for_user(async_client, token_a, name="Biz A")

    _, token_b = await create_user_and_token(async_client, name="Owner B")
    biz_b = await create_business_for_user(async_client, token_b, name="Biz B")

    # User A tries to pass biz_b["id"]
    res = await async_client.post(
        "/api/v1/chat/preview-token",
        json={"business_id": biz_b["id"]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_valid_specific_business_id_succeeds(async_client: AsyncClient):
    """Verifies passing a valid business_id the user owns succeeds."""
    _, token = await create_user_and_token(async_client, name="Multi Biz Owner")
    biz = await create_business_for_user(async_client, token, name="Multi Biz 1")

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        json={"business_id": biz["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    payload = verify_widget_token(data["token"], secret=TEST_WIDGET_SECRET)
    assert payload.business_id == uuid.UUID(biz["id"])


@pytest.mark.asyncio
async def test_extra_fields_in_payload_rejected_422(async_client: AsyncClient):
    """Verifies extra fields in request body are rejected with 422."""
    _, token = await create_user_and_token(async_client, name="Extra Field User")
    await create_business_for_user(async_client, token)

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        json={"unexpected_extra": "hack"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_preview_token_expiration_accuracy(async_client: AsyncClient):
    """Verifies token expiration timestamp matches response and JWT exp claim."""
    _, token = await create_user_and_token(async_client, name="Expiration User")
    await create_business_for_user(async_client, token)

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()

    exp_from_res = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
    payload = verify_widget_token(data["token"], secret=TEST_WIDGET_SECRET)

    # Expiry in payload matches expires_at in response within 1 second
    diff = abs((exp_from_res - payload.expires_at).total_seconds())
    assert diff <= 1.0


# =====================================================================
# 2. Integration with POST /api/v1/chat/messages
# =====================================================================

@pytest.mark.asyncio
async def test_preview_token_accepted_by_chat_from_dashboard_origin(async_client: AsyncClient):
    """Verifies chat endpoint accepts preview token with trusted dashboard Origin."""
    _, session_token = await create_user_and_token(async_client, name="Dashboard User")
    biz = await create_business_for_user(async_client, session_token, name="Chat Preview Biz")

    # 1. Obtain preview token
    token_res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert token_res.status_code == 200
    preview_token = token_res.json()["token"]

    # 2. Submit chat message using preview token and trusted dashboard origin
    chat_payload = {
        "message": "Testing preview chat from dashboard",
        "request_id": str(uuid.uuid4()),
    }
    chat_res = await async_client.post(
        "/api/v1/chat/messages",
        json=chat_payload,
        headers={
            "X-Widget-Token": preview_token,
            "Origin": "http://localhost:3000",
        },
    )
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "conversation_id" in data
    assert data["message"]["role"] == "assistant"
    assert data["message"]["content"] is not None


@pytest.mark.asyncio
async def test_preview_token_rejected_from_untrusted_origin(async_client: AsyncClient):
    """Verifies that presenting a preview token from an untrusted origin returns 403."""
    _, session_token = await create_user_and_token(async_client, name="Dashboard User")
    await create_business_for_user(async_client, session_token)

    token_res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    preview_token = token_res.json()["token"]

    # Submit from an untrusted external origin
    chat_res = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "Hack attempt", "request_id": str(uuid.uuid4())},
        headers={
            "X-Widget-Token": preview_token,
            "Origin": "https://malicious-external-site.com",
        },
    )
    assert chat_res.status_code == 403
    assert "Origin is not authorized for preview" in chat_res.json()["detail"]


@pytest.mark.asyncio
async def test_preview_token_missing_origin_rejected_403(async_client: AsyncClient):
    """Verifies that presenting a preview token without Origin header returns 403."""
    _, session_token = await create_user_and_token(async_client, name="Dashboard User")
    await create_business_for_user(async_client, session_token)

    token_res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    preview_token = token_res.json()["token"]

    chat_res = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "No origin", "request_id": str(uuid.uuid4())},
        headers={"X-Widget-Token": preview_token},
    )
    assert chat_res.status_code == 403


@pytest.mark.asyncio
async def test_expired_preview_token_rejected_401(async_client: AsyncClient):
    """Verifies that an expired preview token is rejected with 401."""
    biz_id = uuid.uuid4()
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    expired_token = generate_widget_token(
        business_id=biz_id,
        secret=TEST_WIDGET_SECRET,
        expire_minutes=15,
        issued_at=expired_time,
        is_preview=True,
    )

    chat_res = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "Expired test", "request_id": str(uuid.uuid4())},
        headers={
            "X-Widget-Token": expired_token,
            "Origin": "http://localhost:3000",
        },
    )
    assert chat_res.status_code == 401
    assert "expired" in chat_res.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_is_preview_type_rejected_401(async_client: AsyncClient):
    """Verifies that a token with a non-boolean is_preview claim is rejected with 401."""
    import base64
    import hashlib
    import hmac
    import json
    import secrets

    biz_id = uuid.uuid4()
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(biz_id),
        "business_id": str(biz_id),
        "type": "widget",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
        "jti": secrets.token_hex(16),
        "is_preview": "true",  # String instead of boolean!
    }

    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = hmac.new(TEST_WIDGET_SECRET.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    tampered_token = f"{header_b64}.{payload_b64}.{sig_b64}"

    # 1. Unit-level assertion verifying exact exception message
    with pytest.raises(WidgetTokenError, match="Invalid 'is_preview' claim: expected boolean"):
        verify_widget_token(tampered_token, secret=TEST_WIDGET_SECRET)

    # 2. Endpoint-level assertion verifying 401 Unauthorized
    chat_res = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "Type spoof", "request_id": str(uuid.uuid4())},
        headers={
            "X-Widget-Token": tampered_token,
            "Origin": "http://localhost:3000",
        },
    )
    assert chat_res.status_code == 401
    assert "Malformed or invalid widget token" in chat_res.json()["detail"]


@pytest.mark.asyncio
async def test_public_widget_token_obeys_business_allowed_origins(async_client: AsyncClient):
    """Verifies that normal public widget tokens (is_preview=False) cannot use dashboard origin unless in allowed_origins."""
    # Create business with custom allowed_origins
    async with async_session_factory() as db:
        biz = Business(
            name="Public Client Biz",
            slug=f"public-biz-{uuid.uuid4().hex[:6]}",
            allowed_origins=["https://client-production-site.com"],
            is_active=True,
        )
        db.add(biz)
        await db.commit()
        await db.refresh(biz)

    # Public token (is_preview=False)
    public_token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET, is_preview=False)

    # 1. Replay from dashboard origin: MUST BE REJECTED (403)
    chat_res_dashboard = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "From dashboard", "request_id": str(uuid.uuid4())},
        headers={
            "X-Widget-Token": public_token,
            "Origin": "http://localhost:3000",
        },
    )
    assert chat_res_dashboard.status_code == 403
    assert "Origin is not authorized for this business" in chat_res_dashboard.json()["detail"]

    # 2. Presentation from permitted client site: MUST SUCCEED (200)
    chat_res_allowed = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "From allowed client", "request_id": str(uuid.uuid4())},
        headers={
            "X-Widget-Token": public_token,
            "Origin": "https://client-production-site.com",
        },
    )
    assert chat_res_allowed.status_code == 200


@pytest.mark.asyncio
async def test_empty_or_invalid_trusted_origin_config_fails_closed(async_client: AsyncClient, monkeypatch):
    """Verifies that if server trusted origins configuration is empty, preview tokens fail closed (403)."""
    _, session_token = await create_user_and_token(async_client, name="Fails Closed User")
    await create_business_for_user(async_client, session_token)

    token_res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    preview_token = token_res.json()["token"]

    # Server configuration cleared
    monkeypatch.setattr(settings, "FRONTEND_URL", "")
    monkeypatch.setattr(settings, "CORS_ORIGINS", [])

    chat_res = await async_client.post(
        "/api/v1/chat/messages",
        json={"message": "Fails closed check", "request_id": str(uuid.uuid4())},
        headers={
            "X-Widget-Token": preview_token,
            "Origin": "http://localhost:3000",
        },
    )
    assert chat_res.status_code == 403
    assert "Origin is not authorized for preview" in chat_res.json()["detail"]


@pytest.mark.asyncio
async def test_preview_token_does_not_expose_secret_or_log_raw_token(
    async_client: AsyncClient, caplog
):
    """Verifies signing secret is never returned and raw token is not logged."""
    _, token = await create_user_and_token(async_client, name="Security Audit User")
    await create_business_for_user(async_client, token)

    caplog.set_level(logging.INFO)

    res = await async_client.post(
        "/api/v1/chat/preview-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()

    # Response schema keys strictly limited to token and expires_at
    assert set(data.keys()) == {"token", "expires_at"}

    # Secret must never be in body or text
    assert TEST_WIDGET_SECRET not in res.text

    # Complete raw token must not be in log output
    assert data["token"] not in caplog.text
