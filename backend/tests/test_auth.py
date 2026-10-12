"""Authentication endpoint and lifecycle tests.

Verifies:
- Registration success, duplicate email rejection, input validation
- Login success, incorrect password rejection, generic errors
- Session cookie issuance, attributes, expiration, and revocation
- Current user profile endpoint (/api/v1/auth/me)
- Successful logout and session revocation
- Preserving existing business and membership relationships
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.security import verify_password
from app.models.user import User
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.session import UserSession

settings = get_settings()


@pytest.mark.asyncio
async def test_successful_registration(async_client: AsyncClient):
    """Verifies that a new user can register successfully with valid details."""
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "StrongPassword123!",
        "full_name": "Test User",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    user_data = data["user"]
    assert user_data["email"] == unique_email
    assert user_data["full_name"] == "Test User"
    assert user_data["verified"] is False
    assert user_data["is_active"] is True
    assert "id" in user_data
    # Ensure password and hash are not leaked in response
    assert "password" not in user_data
    assert "password_hash" not in user_data


@pytest.mark.asyncio
async def test_duplicate_email_rejection(async_client: AsyncClient):
    """Verifies that registering with an already existing email is rejected with HTTP 409."""
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "StrongPassword123!",
        "full_name": "First Account",
    }
    res1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Attempt second registration with same email
    res2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert "already exists" in data["detail"]


@pytest.mark.asyncio
async def test_password_hash_storage_and_verification(async_client: AsyncClient):
    """Verifies that password is stored as an Argon2id hash and plaintext is never saved."""
    unique_email = f"hash_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "SuperSecretPassword123!"
    payload = {
        "email": unique_email,
        "password": raw_password,
        "full_name": "Hash Verification",
    }
    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == unique_email)
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.password_hash is not None
        # Argon2id identifier prefix
        assert user.password_hash.startswith("$argon2id$")
        # Ensure plaintext password is not in database
        assert user.password_hash != raw_password
        # Verify hash matches plaintext
        assert verify_password(raw_password, user.password_hash) is True
        assert verify_password("WrongPassword123!", user.password_hash) is False


@pytest.mark.asyncio
async def test_successful_login(async_client: AsyncClient):
    """Verifies successful login, response payload, and session cookie."""
    unique_email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "SecurePassword123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password, "full_name": "Login User"},
    )

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": raw_password},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["user"]["email"] == unique_email

    # Check session cookie
    cookies = login_res.cookies
    assert settings.SESSION_COOKIE_NAME in cookies
    token = cookies[settings.SESSION_COOKIE_NAME]
    assert len(token) > 20


@pytest.mark.asyncio
async def test_incorrect_password_rejection(async_client: AsyncClient):
    """Verifies that incorrect passwords are rejected with generic 401 Unauthorized."""
    unique_email = f"wrongpw_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "SecurePassword123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password},
    )

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "IncorrectPassword999!"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_nonexistent_email_rejection(async_client: AsyncClient):
    """Verifies that non-existent users receive the identical generic error message."""
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_ghost@example.com", "password": "AnyPassword123!"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_missing_and_invalid_credentials(async_client: AsyncClient):
    """Verifies validation on missing fields, bad email format, and weak password."""
    # Missing email
    res1 = await async_client.post(
        "/api/v1/auth/register",
        json={"password": "Password123!"},
    )
    assert res1.status_code == 422

    # Invalid email format
    res2 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "Password123!"},
    )
    assert res2.status_code == 422

    # Password too short (<8 chars)
    res3 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_current_user_endpoint_with_valid_session(async_client: AsyncClient):
    """Verifies GET /api/v1/auth/me returns current user with valid session cookie."""
    unique_email = f"me_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password, "full_name": "Me Profile"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": raw_password},
    )
    session_token = login_res.cookies[settings.SESSION_COOKIE_NAME]

    # Make request with cookie
    me_res = await async_client.get(
        "/api/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: session_token},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == unique_email
    assert me_data["full_name"] == "Me Profile"
    assert me_data["verified"] is False
    assert me_data["is_active"] is True


@pytest.mark.asyncio
async def test_current_user_endpoint_without_session(async_client: AsyncClient):
    """Verifies GET /api/v1/auth/me returns 401 Unauthorized when unauthenticated."""
    res = await async_client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "Not authenticated" in res.json()["detail"]


@pytest.mark.asyncio
async def test_successful_logout(async_client: AsyncClient):
    """Verifies logout revokes the session and clears authentication cookies."""
    unique_email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": raw_password},
    )
    session_token = login_res.cookies[settings.SESSION_COOKIE_NAME]

    # Logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        cookies={settings.SESSION_COOKIE_NAME: session_token},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Subsequent request using the revoked token should fail with 401
    me_res = await async_client.get(
        "/api/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: session_token},
    )
    assert me_res.status_code == 401


@pytest.mark.asyncio
async def test_rejected_use_of_expired_session(async_client: AsyncClient):
    """Verifies that an expired session in database is rejected with HTTP 401."""
    unique_email = f"expired_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": raw_password},
    )
    session_token = login_res.cookies[settings.SESSION_COOKIE_NAME]

    # Manually expire the session in database
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == unique_email))
        user = result.scalar_one()
        user_sessions = await session.execute(
            select(UserSession).where(UserSession.user_id == user.id)
        )
        for s in user_sessions.scalars():
            s.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await session.commit()

    # Attempt access with expired session
    res = await async_client.get(
        "/api/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: session_token},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_session_cookie_security_attributes(async_client: AsyncClient):
    """Verifies that the session cookie includes HttpOnly, SameSite, and Path attributes."""
    unique_email = f"cookie_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": raw_password},
    )
    set_cookie_header = login_res.headers.get("set-cookie", "")
    assert settings.SESSION_COOKIE_NAME in set_cookie_header
    assert "HttpOnly" in set_cookie_header or "httponly" in set_cookie_header.lower()
    assert "samesite=lax" in set_cookie_header.lower()
    assert "path=/" in set_cookie_header.lower()


@pytest.mark.asyncio
async def test_existing_business_and_membership_relationships_intact(async_client: AsyncClient):
    """Verifies that Phase 2 business and membership models remain fully intact."""
    unique_email = f"bizowner_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "Password123!"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password, "full_name": "Biz Owner"},
    )
    user_id = uuid.UUID(reg_res.json()["user"]["id"])

    # Attach business and membership to user
    async with async_session_factory() as session:
        business = Business(
            name="Salon Bella",
            slug=f"salon-bella-{uuid.uuid4().hex[:6]}",
        )
        session.add(business)
        await session.flush()

        member = BusinessMember(
            business_id=business.id,
            user_id=user_id,
            role=MemberRole.OWNER,
        )
        session.add(member)
        await session.commit()

        # Query user with memberships
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.memberships))
        )
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        assert user is not None
        assert len(user.memberships) == 1
        assert user.memberships[0].business_id == business.id
        assert user.memberships[0].role == MemberRole.OWNER
