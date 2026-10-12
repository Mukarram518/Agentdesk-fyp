"""Authentication dependencies for protecting backend endpoints."""

from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import auth_service

settings = get_settings()


def get_session_token(request: Request) -> Optional[str]:
    """Extracts session token from HttpOnly cookie or Authorization Bearer header."""
    # 1. Primary: HttpOnly Cookie
    cookie_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    # 2. Secondary fallback: Authorization Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that authenticates and returns the active current user.

    Raises HTTP 401 Unauthorized if:
    - Session token is missing
    - Session is not found, expired, or revoked
    - User account is inactive
    """
    raw_token = get_session_token(request)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await auth_service.get_user_by_session(db, raw_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Dependency that returns current user if authenticated, or None if unauthenticated."""
    raw_token = get_session_token(request)
    if not raw_token:
        return None

    return await auth_service.get_user_by_session(db, raw_token)
