"""Authentication endpoints for AgentDesk."""

import secrets
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import (
    rate_limit_login,
    rate_limit_register,
    get_client_ip,
)
from app.api.dependencies.auth import (
    get_current_user,
    get_session_token,
)
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    AuthResponse,
    LogoutResponse,
    GoogleAuthUrlResponse,
)
from app.services.auth_service import auth_service

settings = get_settings()

router = APIRouter()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
    dependencies=[Depends(rate_limit_register)],
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Registers a new user account with secure Argon2id password hashing.

    Validates:
    - RFC compliant email format
    - Password complexity policy (8-128 chars, letters, digits/symbols)
    - Duplicate email rejection with HTTP 409
    """
    user = await auth_service.register(
        db=db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    return AuthResponse(user=UserResponse.from_orm_user(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate user and establish session",
    dependencies=[Depends(rate_limit_login)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticates credentials, verifies Argon2id hash, and sets HttpOnly session cookie."""
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    user, raw_token = await auth_service.login(
        db=db,
        email=payload.email,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRE_SECONDS,
        path="/",
    )

    return AuthResponse(user=UserResponse.from_orm_user(user))


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke session and clear authentication cookie",
)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    """Revokes the active session in database and clears the browser session cookie."""
    raw_token = get_session_token(request)
    if raw_token:
        await auth_service.logout(db, raw_token)

    # Invalidate session cookie
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    return LogoutResponse(success=True)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve authenticated current user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Returns profile information for the authenticated user session."""
    return UserResponse.from_orm_user(current_user)


@router.get(
    "/google",
    summary="Initiate Google OAuth 2.0 flow",
)
async def google_login(
    response: Response,
    redirect: bool = True,
):
    """Generates Google OAuth URL and sets CSRF state cookie."""
    state = secrets.token_urlsafe(32)
    auth_url = auth_service.get_google_auth_url(state)

    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=600,
        path="/",
    )

    if redirect:
        redirect_res = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
        redirect_res.set_cookie(
            key="oauth_state",
            value=state,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite="lax",
            max_age=600,
            path="/",
        )
        return redirect_res

    return GoogleAuthUrlResponse(authorization_url=auth_url)


@router.get(
    "/google/callback",
    summary="Handle Google OAuth 2.0 callback",
)
async def google_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Processes Google OAuth callback, verifies identity, sets session cookie, and redirects."""
    expected_state = request.cookies.get("oauth_state")
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    user, raw_token = await auth_service.handle_google_callback(
        db=db,
        code=code,
        state=state,
        expected_state=expected_state,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    redirect_res = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/",
        status_code=status.HTTP_302_FOUND,
    )

    # Set session cookie
    redirect_res.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRE_SECONDS,
        path="/",
    )

    # Clear state cookie
    redirect_res.delete_cookie(
        key="oauth_state",
        path="/",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
    )

    return redirect_res
