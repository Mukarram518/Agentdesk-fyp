"""Focused API tests for AgentDesk Phase 4.1 Business Endpoints.

Tests:
- POST /api/v1/businesses (creation, owner assignment, custom slug, duplicate slug 409, validation 422, unauthenticated 401, tamper resistance)
- GET /api/v1/businesses (listing user's active businesses, empty list, tenant isolation, inactive exclusion, unauthenticated 401)
- GET /api/v1/businesses/current (primary business resolution 200, no business 404, inactive business 404, unauthenticated 401)
- GET /api/v1/businesses/{business_id} (authorized retrieval 200, cross-tenant unauthorized 404, nonexistent 404, inactive 404, invalid UUID 422, unauthenticated 401)
"""

import uuid
from typing import Tuple
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole

settings = get_settings()


async def create_authenticated_user(
    async_client: AsyncClient, name: str = "Test User"
) -> Tuple[dict, str]:
    """Helper that registers, logs in, and returns (user_data, session_token)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
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


# ============================================================================
# 1. POST /api/v1/businesses Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_business_success(async_client: AsyncClient):
    """Verifies that an authenticated user can create a business and is assigned owner."""
    user, token = await create_authenticated_user(async_client, name="Dr. Alex Smith")
    biz_name = f"Alex Dental Clinic {uuid.uuid4().hex[:6]}"

    response = await async_client.post(
        "/api/v1/businesses",
        json={"name": biz_name},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == biz_name
    assert "id" in data
    assert data["is_active"] is True
    assert data["role"] == MemberRole.OWNER.value
    assert data["created_at"] is not None
    assert data["updated_at"] is not None

    # Verify atomic DB persistence
    async with async_session_factory() as db:
        biz_id = uuid.UUID(data["id"])
        db_biz = await db.get(Business, biz_id)
        assert db_biz is not None
        assert db_biz.name == biz_name

        member_res = await db.execute(
            BusinessMember.__table__.select().where(
                BusinessMember.business_id == biz_id,
                BusinessMember.user_id == uuid.UUID(user["id"]),
            )
        )
        membership = member_res.mappings().one_or_none()
        assert membership is not None
        assert membership["role"] == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_create_business_with_custom_slug(async_client: AsyncClient):
    """Verifies creating a business with a custom valid URL slug."""
    _, token = await create_authenticated_user(async_client)
    custom_slug = f"custom-optics-{uuid.uuid4().hex[:6]}"

    response = await async_client.post(
        "/api/v1/businesses",
        json={"name": "Custom Optics Lab", "slug": custom_slug},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == custom_slug


@pytest.mark.asyncio
async def test_create_business_duplicate_slug_conflict(async_client: AsyncClient):
    """Verifies creating a business with an existing slug returns HTTP 409 Conflict."""
    _, token1 = await create_authenticated_user(async_client)
    _, token2 = await create_authenticated_user(async_client)
    shared_slug = f"shared-slug-{uuid.uuid4().hex[:6]}"

    res1 = await async_client.post(
        "/api/v1/businesses",
        json={"name": "First Enterprise", "slug": shared_slug},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res1.status_code == 201

    # Second user attempts duplicate slug
    res2 = await async_client.post(
        "/api/v1/businesses",
        json={"name": "Second Enterprise", "slug": shared_slug},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_create_business_validation_errors(async_client: AsyncClient):
    """Verifies invalid business names and slugs return HTTP 422."""
    _, token = await create_authenticated_user(async_client)

    # Empty name
    res_empty = await async_client.post(
        "/api/v1/businesses",
        json={"name": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_empty.status_code == 422

    # Malformed slug (spaces, symbols)
    res_slug = await async_client.post(
        "/api/v1/businesses",
        json={"name": "Valid Name", "slug": "invalid slug with spaces"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_slug.status_code == 422


@pytest.mark.asyncio
async def test_create_business_unauthenticated(async_client: AsyncClient):
    """Verifies unauthenticated business creation returns HTTP 401."""
    res = await async_client.post(
        "/api/v1/businesses",
        json={"name": "Unauthorized Enterprise"},
    )
    assert res.status_code == 401
    assert "Not authenticated" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_business_ignores_client_role_tampering(async_client: AsyncClient):
    """Verifies client attempts to inject user_id or role cannot override authenticated owner."""
    user, token = await create_authenticated_user(async_client)
    fake_user_id = str(uuid.uuid4())

    res = await async_client.post(
        "/api/v1/businesses",
        json={
            "name": f"Tamper Test {uuid.uuid4().hex[:6]}",
            "role": "member",
            "user_id": fake_user_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = response_data = res.json()
    assert response_data["role"] == MemberRole.OWNER.value

    # Verify DB ownership is strictly the authenticated user
    async with async_session_factory() as db:
        biz_id = uuid.UUID(data["id"])
        member_res = await db.execute(
            BusinessMember.__table__.select().where(
                BusinessMember.business_id == biz_id,
            )
        )
        membership = member_res.mappings().one()
        assert membership["user_id"] == uuid.UUID(user["id"])
        assert membership["role"] == MemberRole.OWNER.value


# ============================================================================
# 2. GET /api/v1/businesses Tests
# ============================================================================

@pytest.mark.asyncio
async def test_list_businesses_authenticated(async_client: AsyncClient):
    """Verifies listing active businesses for the authenticated user."""
    _, token = await create_authenticated_user(async_client)

    name1 = f"Business 1 {uuid.uuid4().hex[:6]}"
    name2 = f"Business 2 {uuid.uuid4().hex[:6]}"

    await async_client.post(
        "/api/v1/businesses",
        json={"name": name1},
        headers={"Authorization": f"Bearer {token}"},
    )
    await async_client.post(
        "/api/v1/businesses",
        json={"name": name2},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = await async_client.get(
        "/api/v1/businesses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    businesses = res.json()
    assert len(businesses) == 2
    names = [b["name"] for b in businesses]
    assert name1 in names
    assert name2 in names
    for b in businesses:
        assert b["role"] == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_list_businesses_empty_for_new_user(async_client: AsyncClient):
    """Verifies listing businesses returns [] for a user with no businesses."""
    _, token = await create_authenticated_user(async_client)

    res = await async_client.get(
        "/api/v1/businesses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_businesses_tenant_isolation(async_client: AsyncClient):
    """Verifies tenant isolation: User A never sees User B's businesses."""
    _, token_a = await create_authenticated_user(async_client, name="User A")
    _, token_b = await create_authenticated_user(async_client, name="User B")

    name_a = f"Biz A {uuid.uuid4().hex[:6]}"
    name_b = f"Biz B {uuid.uuid4().hex[:6]}"

    await async_client.post(
        "/api/v1/businesses",
        json={"name": name_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    await async_client.post(
        "/api/v1/businesses",
        json={"name": name_b},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    res_a = await async_client.get(
        "/api/v1/businesses",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    res_b = await async_client.get(
        "/api/v1/businesses",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert [b["name"] for b in res_a.json()] == [name_a]
    assert [b["name"] for b in res_b.json()] == [name_b]


@pytest.mark.asyncio
async def test_list_businesses_excludes_inactive(async_client: AsyncClient):
    """Verifies deactivated businesses are excluded from the listing."""
    _, token = await create_authenticated_user(async_client)
    create_res = await async_client.post(
        "/api/v1/businesses",
        json={"name": f"Deactivated {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    biz_id = uuid.UUID(create_res.json()["id"])

    # Deactivate business in database
    async with async_session_factory() as db:
        biz = await db.get(Business, biz_id)
        biz.is_active = False
        await db.commit()

    res = await async_client.get(
        "/api/v1/businesses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_businesses_unauthenticated(async_client: AsyncClient):
    """Verifies GET /api/v1/businesses returns HTTP 401 without authentication."""
    res = await async_client.get("/api/v1/businesses")
    assert res.status_code == 401


# ============================================================================
# 3. GET /api/v1/businesses/current Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_current_business_success(async_client: AsyncClient):
    """Verifies retrieving the authenticated user's current active business."""
    _, token = await create_authenticated_user(async_client)
    biz_name = f"Current Clinic {uuid.uuid4().hex[:6]}"

    created = await async_client.post(
        "/api/v1/businesses",
        json={"name": biz_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    created_id = created.json()["id"]

    res = await async_client.get(
        "/api/v1/businesses/current",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == created_id
    assert data["name"] == biz_name
    assert data["role"] == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_get_current_business_no_business_returns_404(async_client: AsyncClient):
    """Verifies 404 is returned when user has not onboarded a business yet."""
    _, token = await create_authenticated_user(async_client)

    res = await async_client.get(
        "/api/v1/businesses/current",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert "No active business found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_business_inactive_returns_404(async_client: AsyncClient):
    """Verifies 404 is returned when user's business is deactivated."""
    _, token = await create_authenticated_user(async_client)
    created = await async_client.post(
        "/api/v1/businesses",
        json={"name": f"Inactive Current {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    biz_id = uuid.UUID(created.json()["id"])

    async with async_session_factory() as db:
        biz = await db.get(Business, biz_id)
        biz.is_active = False
        await db.commit()

    res = await async_client.get(
        "/api/v1/businesses/current",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert "No active business found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_business_unauthenticated(async_client: AsyncClient):
    """Verifies GET /api/v1/businesses/current returns 401 when unauthenticated."""
    res = await async_client.get("/api/v1/businesses/current")
    assert res.status_code == 401


# ============================================================================
# 4. GET /api/v1/businesses/{business_id} Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_business_by_id_authorized(async_client: AsyncClient):
    """Verifies retrieving business details by ID when user is an active member."""
    _, token = await create_authenticated_user(async_client)
    biz_name = f"Detail Clinic {uuid.uuid4().hex[:6]}"

    created = await async_client.post(
        "/api/v1/businesses",
        json={"name": biz_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    biz_id = created.json()["id"]

    res = await async_client.get(
        f"/api/v1/businesses/{biz_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == biz_id
    assert data["name"] == biz_name
    assert data["role"] == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_get_business_by_id_nonexistent_returns_404(async_client: AsyncClient):
    """Verifies requesting a random non-existent UUID returns HTTP 404."""
    _, token = await create_authenticated_user(async_client)
    random_id = uuid.uuid4()

    res = await async_client.get(
        f"/api/v1/businesses/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert "Business not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_business_by_id_cross_tenant_unauthorized_returns_404(
    async_client: AsyncClient,
):
    """Verifies requesting another user's business returns 404 without leaking data existence."""
    _, token_a = await create_authenticated_user(async_client, name="User A")
    _, token_b = await create_authenticated_user(async_client, name="User B")

    created_a = await async_client.post(
        "/api/v1/businesses",
        json={"name": f"Private Biz {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    biz_a_id = created_a.json()["id"]

    # User B attempts to access User A's business by ID
    res_b = await async_client.get(
        f"/api/v1/businesses/{biz_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b.status_code == 404
    assert "Business not found" in res_b.json()["detail"]


@pytest.mark.asyncio
async def test_get_business_by_id_inactive_returns_404(async_client: AsyncClient):
    """Verifies accessing a deactivated business by ID returns HTTP 404."""
    _, token = await create_authenticated_user(async_client)
    created = await async_client.post(
        "/api/v1/businesses",
        json={"name": f"Inactive Detail {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    biz_id = uuid.UUID(created.json()["id"])

    async with async_session_factory() as db:
        biz = await db.get(Business, biz_id)
        biz.is_active = False
        await db.commit()

    res = await async_client.get(
        f"/api/v1/businesses/{biz_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert "Business not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_business_by_id_invalid_uuid_returns_422(async_client: AsyncClient):
    """Verifies passing a malformed string as business_id returns HTTP 422."""
    _, token = await create_authenticated_user(async_client)

    res = await async_client.get(
        "/api/v1/businesses/not-a-valid-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_business_by_id_unauthenticated(async_client: AsyncClient):
    """Verifies requesting business details without authentication returns HTTP 401."""
    random_id = uuid.uuid4()
    res = await async_client.get(f"/api/v1/businesses/{random_id}")
    assert res.status_code == 401
