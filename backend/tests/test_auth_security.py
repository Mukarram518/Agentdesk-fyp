"""Security and edge-case tests for authentication.

Verifies:
- Session token hashing in database (no raw token leakage)
- Authentication rate limiting on login and register
- Google OAuth URL generation, state validation, account linking restrictions, and mock callback
- Timing-safe dummy hash verification
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.rate_limit import reset_rate_limits
from app.core.security import hash_session_token, dummy_verify_password
from app.models.user import User
from app.models.session import UserSession
from app.services.auth_service import auth_service

settings = get_settings()


@pytest.mark.asyncio
async def test_session_token_stored_hashed_never_raw(async_client: AsyncClient):
    """Verifies that database only stores SHA-256 hash of session token, not raw token."""
    unique_email = f"hashsec_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": raw_password},
    )
    raw_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    expected_hash = hash_session_token(raw_token)

    async with async_session_factory() as session:
        result = await session.execute(
            select(UserSession).where(UserSession.token_hash == expected_hash)
        )
        stored_session = result.scalar_one_or_none()
        assert stored_session is not None
        assert stored_session.token_hash == expected_hash
        # Ensure the raw token string is NOT stored as token_hash
        assert stored_session.token_hash != raw_token


@pytest.mark.asyncio
async def test_authentication_rate_limiting(async_client: AsyncClient):
    """Verifies that exceeding the allowed login attempts results in HTTP 429."""
    client_ip_header = {"X-Forwarded-For": "198.51.100.42"}
    unique_email = f"ratelimit_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "Password123!"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": raw_password},
        headers=client_ip_header,
    )

    # Trigger multiple requests up to rate limit
    for _ in range(settings.AUTH_RATE_LIMIT_LOGIN):
        res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "WrongPassword123!"},
            headers=client_ip_header,
        )
        assert res.status_code == 401

    # Next attempt should be rate limited
    limited_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "WrongPassword123!"},
        headers=client_ip_header,
    )
    assert limited_res.status_code == 429
    assert "Too many attempts" in limited_res.json()["detail"]


@pytest.mark.asyncio
async def test_google_oauth_endpoint_and_state_cookie(async_client: AsyncClient, monkeypatch):
    """Verifies GET /api/v1/auth/google initiates flow and sets secure state cookie."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-google-secret")

    res = await async_client.get("/api/v1/auth/google?redirect=false")
    assert res.status_code == 200
    data = res.json()
    assert "authorization_url" in data
    assert "accounts.google.com" in data["authorization_url"]
    assert "oauth_state" in res.cookies


@pytest.mark.asyncio
async def test_google_callback_rejects_invalid_state(async_client: AsyncClient):
    """Verifies callback rejects invalid or missing OAuth state with HTTP 400."""
    res = await async_client.get(
        "/api/v1/auth/google/callback?code=mock_code&state=forged_state",
        cookies={"oauth_state": "legitimate_state"},
    )
    assert res.status_code == 400
    assert "state" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_google_oauth_registration_and_login_flow(monkeypatch):
    """Verifies Google callback registers a new verified user and creates valid session."""
    mock_sub = f"google_sub_{uuid.uuid4().hex[:12]}"
    mock_email = f"google_user_{uuid.uuid4().hex[:8]}@example.com"
    mock_userinfo = {
        "sub": mock_sub,
        "email": mock_email,
        "email_verified": True,
        "name": "Google Test User",
    }

    async with async_session_factory() as session:
        user, raw_token = await auth_service.handle_google_callback(
            db=session,
            code="valid_mock_code",
            state="state123",
            expected_state="state123",
            mock_userinfo=mock_userinfo,
        )
        assert user.email == mock_email
        assert user.google_sub == mock_sub
        assert user.is_verified is True
        assert user.password_hash is None
        assert raw_token is not None

        # Verify session is valid in database
        resolved_user = await auth_service.get_user_by_session(session, raw_token)
        assert resolved_user is not None
        assert resolved_user.id == user.id


@pytest.mark.asyncio
async def test_google_oauth_rejects_unverified_email():
    """Verifies that Google accounts with unverified email addresses are rejected."""
    mock_userinfo = {
        "sub": "sub_unverified",
        "email": "unverified@example.com",
        "email_verified": False,
        "name": "Unverified User",
    }
    from fastapi import HTTPException
    async with async_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.handle_google_callback(
                db=session,
                code="code",
                state="state123",
                expected_state="state123",
                mock_userinfo=mock_userinfo,
            )
        assert exc_info.value.status_code == 400
        assert "not verified" in exc_info.value.detail


@pytest.mark.asyncio
async def test_google_oauth_prevents_automatic_account_linking(async_client: AsyncClient):
    """Verifies that an existing password user is not automatically linked via Google callback."""
    unique_email = f"link_target_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": "Password123!"},
    )

    mock_userinfo = {
        "sub": f"google_sub_{uuid.uuid4().hex[:8]}",
        "email": unique_email,
        "email_verified": True,
        "name": "Existing User",
    }
    from fastapi import HTTPException
    async with async_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.handle_google_callback(
                db=session,
                code="code",
                state="state123",
                expected_state="state123",
                mock_userinfo=mock_userinfo,
            )
        assert exc_info.value.status_code == 409
        assert "linking" in exc_info.value.detail.lower()


def test_dummy_verify_password_executes_safely():
    """Verifies that timing-attack defense helper executes without raising exceptions."""
    dummy_verify_password()
