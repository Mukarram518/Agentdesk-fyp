"""Integration tests for AgentDesk Agent Configuration API Endpoints (Phase 4B).

Tests:
1. Unauthenticated requests return 401 Unauthorized (GET, PUT, PATCH).
2. Non-owner members receive 403 Forbidden (GET, PUT, PATCH).
3. Authenticated user without business receives 404 Not Found.
4. GET auto-initializes and returns default configuration (200 OK).
5. PUT successfully updates full and partial configuration (200 OK).
6. PATCH successfully performs partial configuration update (200 OK).
7. Clearing optional fields (greeting, voice_id) to None (200 OK).
8. Input validation: invalid tone returns 422 Unprocessable Entity.
9. Input validation: empty or unsupported language_priority returns 422.
10. Input validation: overlong greeting (>1000 chars) returns 422.
11. Input validation: overlong voice_id (>100 chars) returns 422.
12. Input validation: unknown extra fields return 422.
13. Strict multi-tenant isolation: Business A and Business B configs do not leak or overwrite.
14. Persistence across subsequent GET requests.
"""

import uuid
from typing import Tuple
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.business_member import BusinessMember, MemberRole

settings = get_settings()


async def create_authenticated_user(
    async_client: AsyncClient, name: str = "Test User"
) -> Tuple[dict, str]:
    """Registers, logs in, and returns (user_data, session_token)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"

    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": name},
    )
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
    user_data = reg_res.json()["user"]

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    session_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    async_client.cookies.clear()

    return user_data, session_token


async def create_owner_with_business(
    async_client: AsyncClient, biz_name: str = "Agent Config Biz"
) -> Tuple[dict, str, dict]:
    """Creates an authenticated user and onboards a new business as owner."""
    user, token = await create_authenticated_user(async_client, name="Owner User")
    biz_res = await async_client.post(
        "/api/v1/businesses",
        json={"name": f"{biz_name} {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert biz_res.status_code == 201, f"Business creation failed: {biz_res.text}"
    business_data = biz_res.json()
    return user, token, business_data


async def add_member_to_business(
    business_id: uuid.UUID, user_id: uuid.UUID, role: str = MemberRole.MEMBER.value
) -> None:
    """Directly attaches a user as a member/non-owner to a business."""
    async with async_session_factory() as db:
        member = BusinessMember(
            business_id=business_id,
            user_id=user_id,
            role=role,
        )
        db.add(member)
        await db.commit()


# ============================================================================
# 1. Authentication Tests (401)
# ============================================================================


@pytest.mark.asyncio
async def test_unauthenticated_requests_return_401(async_client: AsyncClient):
    """Verifies unauthenticated calls to all endpoints return 401."""
    get_res = await async_client.get("/api/v1/agents/config")
    assert get_res.status_code == 401

    put_res = await async_client.put(
        "/api/v1/agents/config",
        json={"tone": "friendly"},
    )
    assert put_res.status_code == 401

    patch_res = await async_client.patch(
        "/api/v1/agents/config",
        json={"tone": "friendly"},
    )
    assert patch_res.status_code == 401


# ============================================================================
# 2. Authorization Tests (403 and 404)
# ============================================================================


@pytest.mark.asyncio
async def test_unauthorized_non_owner_returns_403(async_client: AsyncClient):
    """Verifies that non-owner business members receive HTTP 403 Forbidden."""
    _, owner_token, biz = await create_owner_with_business(async_client, "Owner Biz")
    biz_id = uuid.UUID(biz["id"])

    # Create a second user and attach as non-owner member
    _, member_token = await create_authenticated_user(async_client, name="Staff Member")
    async with async_session_factory() as db:
        from app.models.user import User
        from sqlalchemy import select
        res = await db.execute(select(User).where(User.email.like("user_%@example.com")).order_by(User.created_at.desc()))
        staff_user = res.scalars().first()

    await add_member_to_business(biz_id, staff_user.id, role=MemberRole.MEMBER.value)

    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Non-owner GET -> 403
    get_res = await async_client.get("/api/v1/agents/config", headers=member_headers)
    assert get_res.status_code == 403
    assert "Only the business owner" in get_res.json()["detail"]

    # Non-owner PUT -> 403
    put_res = await async_client.put(
        "/api/v1/agents/config",
        headers=member_headers,
        json={"tone": "friendly"},
    )
    assert put_res.status_code == 403

    # Non-owner PATCH -> 403
    patch_res = await async_client.patch(
        "/api/v1/agents/config",
        headers=member_headers,
        json={"tone": "friendly"},
    )
    assert patch_res.status_code == 403


@pytest.mark.asyncio
async def test_user_without_business_returns_404(async_client: AsyncClient):
    """Verifies that an authenticated user who has not onboarded a business gets 404."""
    _, token = await create_authenticated_user(async_client, "Unonboarded User")
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get("/api/v1/agents/config", headers=headers)
    assert res.status_code == 404
    assert "No active business found" in res.json()["detail"]


# ============================================================================
# 3. GET /config Default Initialization
# ============================================================================


@pytest.mark.asyncio
async def test_get_agent_config_initializes_default(async_client: AsyncClient):
    """Verifies GET /api/v1/agents/config initializes and returns default config."""
    _, token, biz = await create_owner_with_business(async_client, "Fresh Biz")
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get("/api/v1/agents/config", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["business_id"] == biz["id"]
    assert data["voice_enabled"] is True
    assert data["chat_enabled"] is True
    assert data["lead_enabled"] is True
    assert data["voice_id"] is None
    assert data["tone"] == "helpful"
    assert data["greeting"] is None
    assert data["language_priority"] == ["en", "ur"]
    assert "created_at" in data
    assert "updated_at" in data


# ============================================================================
# 4. PUT & PATCH Configuration Updates
# ============================================================================


@pytest.mark.asyncio
async def test_put_agent_config_success(async_client: AsyncClient):
    """Verifies updating config fields using PUT."""
    _, token, biz = await create_owner_with_business(async_client, "Update Biz")
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "voice_enabled": False,
        "chat_enabled": True,
        "lead_enabled": False,
        "voice_id": "eleven_labs_sarah",
        "tone": "friendly",
        "greeting": "Hello! Welcome to our clinic.",
        "language_priority": ["ur", "en"],
    }

    res = await async_client.put(
        "/api/v1/agents/config",
        headers=headers,
        json=update_payload,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["business_id"] == biz["id"]
    assert data["voice_enabled"] is False
    assert data["chat_enabled"] is True
    assert data["lead_enabled"] is False
    assert data["voice_id"] == "eleven_labs_sarah"
    assert data["tone"] == "friendly"
    assert data["greeting"] == "Hello! Welcome to our clinic."
    assert data["language_priority"] == ["ur", "en"]


@pytest.mark.asyncio
async def test_patch_agent_config_partial_update(async_client: AsyncClient):
    """Verifies updating a single field using PATCH preserves other settings."""
    _, token, biz = await create_owner_with_business(async_client, "Patch Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Set initial values via PUT
    await async_client.put(
        "/api/v1/agents/config",
        headers=headers,
        json={
            "voice_enabled": False,
            "tone": "professional",
            "greeting": "Welcome to law firm.",
            "language_priority": ["en"],
        },
    )

    # Step 2: PATCH only the tone
    patch_res = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"tone": "direct"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()

    # tone updated
    assert data["tone"] == "direct"
    # others preserved
    assert data["voice_enabled"] is False
    assert data["greeting"] == "Welcome to law firm."
    assert data["language_priority"] == ["en"]


@pytest.mark.asyncio
async def test_clear_optional_fields(async_client: AsyncClient):
    """Verifies that greeting and voice_id can be cleared to None."""
    _, token, biz = await create_owner_with_business(async_client, "Clear Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Set greeting and voice_id
    await async_client.put(
        "/api/v1/agents/config",
        headers=headers,
        json={"greeting": "Initial Greeting", "voice_id": "voice_123"},
    )

    # Clear via empty strings
    res = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"greeting": "", "voice_id": ""},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["greeting"] is None
    assert data["voice_id"] is None


# ============================================================================
# 5. Validation Tests (422)
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_tone_returns_422(async_client: AsyncClient):
    """Verifies invalid tone choices return 422 Unprocessable Entity."""
    _, token, _ = await create_owner_with_business(async_client, "Tone Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Unknown tone
    res = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"tone": "aggressive"},
    )
    assert res.status_code == 422
    assert "Allowed tones are" in res.text

    # Empty tone
    res_empty = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"tone": "   "},
    )
    assert res_empty.status_code == 422


@pytest.mark.asyncio
async def test_invalid_language_priority_returns_422(async_client: AsyncClient):
    """Verifies unsupported or empty language priority returns 422."""
    _, token, _ = await create_owner_with_business(async_client, "Lang Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Empty list
    res_empty = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"language_priority": []},
    )
    assert res_empty.status_code == 422

    # Unsupported language
    res_invalid = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"language_priority": ["en", "es"]},
    )
    assert res_invalid.status_code == 422
    assert "Unsupported language code" in res_invalid.text


@pytest.mark.asyncio
async def test_overlong_inputs_return_422(async_client: AsyncClient):
    """Verifies overlong greeting and voice_id return 422."""
    _, token, _ = await create_owner_with_business(async_client, "Length Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Greeting > 1000 characters
    res_greeting = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"greeting": "A" * 1001},
    )
    assert res_greeting.status_code == 422

    # Voice ID > 100 characters
    res_voice = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"voice_id": "V" * 101},
    )
    assert res_voice.status_code == 422


@pytest.mark.asyncio
async def test_unknown_fields_return_422(async_client: AsyncClient):
    """Verifies extra unrecognized fields are rejected with 422."""
    _, token, _ = await create_owner_with_business(async_client, "Extra Biz")
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.patch(
        "/api/v1/agents/config",
        headers=headers,
        json={"malicious_field": "injected_value"},
    )
    assert res.status_code == 422


# ============================================================================
# 6. Multi-Tenant Isolation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_tenant_isolation_between_businesses(async_client: AsyncClient):
    """Verifies strict tenant isolation between two distinct business owners."""
    # Create Business A and Business B
    _, token_a, biz_a = await create_owner_with_business(async_client, "Tenant Alpha")
    _, token_b, biz_b = await create_owner_with_business(async_client, "Tenant Beta")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Business A customizes configuration
    res_a = await async_client.put(
        "/api/v1/agents/config",
        headers=headers_a,
        json={
            "tone": "friendly",
            "voice_enabled": False,
            "greeting": "Greeting from Alpha Clinic",
            "language_priority": ["ur"],
        },
    )
    assert res_a.status_code == 200

    # Business B retrieves configuration - MUST NOT receive Business A's settings
    res_b = await async_client.get("/api/v1/agents/config", headers=headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["business_id"] == biz_b["id"]
    assert data_b["tone"] == "helpful"  # Default
    assert data_b["voice_enabled"] is True  # Default
    assert data_b["greeting"] is None
    assert data_b["language_priority"] == ["en", "ur"]

    # Business B updates their own configuration
    res_b_update = await async_client.put(
        "/api/v1/agents/config",
        headers=headers_b,
        json={
            "tone": "direct",
            "voice_enabled": True,
            "greeting": "Greeting from Beta Auto",
            "language_priority": ["en"],
        },
    )
    assert res_b_update.status_code == 200

    # Business A re-fetches - Alpha's configuration remains completely intact
    res_a_check = await async_client.get("/api/v1/agents/config", headers=headers_a)
    assert res_a_check.status_code == 200
    data_a_check = res_a_check.json()
    assert data_a_check["business_id"] == biz_a["id"]
    assert data_a_check["tone"] == "friendly"
    assert data_a_check["voice_enabled"] is False
    assert data_a_check["greeting"] == "Greeting from Alpha Clinic"
    assert data_a_check["language_priority"] == ["ur"]


# ============================================================================
# 7. Persistence Across Subsequent GET Calls
# ============================================================================


@pytest.mark.asyncio
async def test_persistence_across_subsequent_get(async_client: AsyncClient):
    """Verifies that updates persist to the database and match subsequent GET responses."""
    _, token, biz = await create_owner_with_business(async_client, "Persistence Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: PUT updates
    update_res = await async_client.put(
        "/api/v1/agents/config",
        headers=headers,
        json={
            "tone": "professional",
            "lead_enabled": False,
            "greeting": "Persisted Greeting Test",
            "language_priority": ["en", "ur"],
            "voice_id": "persisted_voice_id",
        },
    )
    assert update_res.status_code == 200
    put_data = update_res.json()

    # Step 2: GET verification
    get_res = await async_client.get("/api/v1/agents/config", headers=headers)
    assert get_res.status_code == 200
    get_data = get_res.json()

    assert get_data["business_id"] == biz["id"]
    assert get_data["tone"] == "professional"
    assert get_data["lead_enabled"] is False
    assert get_data["greeting"] == "Persisted Greeting Test"
    assert get_data["voice_id"] == "persisted_voice_id"
    assert get_data["language_priority"] == ["en", "ur"]
    assert get_data["updated_at"] == put_data["updated_at"]

