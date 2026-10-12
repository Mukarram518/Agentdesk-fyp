"""Authentication service coordinating registration, login, session lifecycle, and Google OAuth."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.core.security import (
    hash_password,
    verify_password,
    dummy_verify_password,
    validate_password_strength,
    generate_session_token,
    hash_session_token,
)
from app.models.user import User
from app.repositories.user_repository import user_repository, UserRepository
from app.repositories.session_repository import session_repository, SessionRepository

settings = get_settings()


class AuthService:
    """Service encapsulating authentication business logic."""

    def __init__(
        self,
        user_repo: UserRepository = user_repository,
        session_repo: SessionRepository = session_repository,
    ) -> None:
        self.user_repo = user_repo
        self.session_repo = session_repo

    async def register(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        full_name: Optional[str] = None,
    ) -> User:
        """Registers a new user with secure password hashing."""
        # 1. Validate password policy
        strength_error = validate_password_strength(password)
        if strength_error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=strength_error,
            )

        # 2. Check for duplicate email
        normalized_email = email.strip().lower()
        existing_user = await self.user_repo.get_by_email(db, normalized_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # 3. Hash password using Argon2id
        pw_hash = hash_password(password)

        # 4. Persist user entity
        user = await self.user_repo.create_user(
            db=db,
            email=normalized_email,
            password_hash=pw_hash,
            full_name=full_name,
            is_verified=False,
            google_sub=None,
        )
        return user

    async def login(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, str]:
        """Authenticates user credentials and establishes a server-side session.

        Guarantees:
        - Generic error messages that do not leak whether an account exists.
        - Constant-time dummy verification when user is not found.
        - Persists only the SHA-256 hash of the generated session token.
        """
        normalized_email = email.strip().lower()
        user = await self.user_repo.get_by_email(db, normalized_email)

        # If user does not exist or has no password hash (e.g. Google-only account)
        if user is None or not user.password_hash:
            dummy_verify_password()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # Verify password safely using Argon2id
        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # Verify account active status
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # Issue secure session token and persist only its SHA-256 hash
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.SESSION_EXPIRE_SECONDS
        )

        await self.session_repo.create_session(
            db=db,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return user, raw_token

    async def logout(self, db: AsyncSession, raw_token: Optional[str]) -> bool:
        """Revokes the active session corresponding to the provided token."""
        if not raw_token:
            return False
        token_hash = hash_session_token(raw_token)
        return await self.session_repo.revoke_session(db, token_hash)

    async def get_user_by_session(
        self,
        db: AsyncSession,
        raw_token: Optional[str],
    ) -> Optional[User]:
        """Resolves authenticated User from a raw session token.

        Validates that session exists, is not revoked, and is not expired.
        """
        if not raw_token:
            return None

        token_hash = hash_session_token(raw_token)
        session = await self.session_repo.get_by_token_hash(db, token_hash)

        if session is None or not session.is_valid:
            return None

        if not session.user or not session.user.is_active:
            return None

        # Update last active timestamp
        await self.session_repo.touch_session(db, session.id)

        return session.user

    def get_google_auth_url(self, state: str) -> str:
        """Generates Google OAuth 2.0 authorization URL."""
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Google OAuth is not configured on this server.",
            )

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI or f"{settings.BACKEND_HOST}/api/v1/auth/google/callback",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def handle_google_callback(
        self,
        db: AsyncSession,
        code: str,
        state: str,
        expected_state: Optional[str],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        mock_userinfo: Optional[Dict[str, Any]] = None,
    ) -> Tuple[User, str]:
        """Handles Google OAuth authorization code exchange and session establishment.

        Follows strict security rules:
        - Validates OAuth state.
        - Rejects unverified email addresses.
        - Does NOT automatically link accounts by email without prior explicit setup.
        """
        # 1. State validation against CSRF
        if not state or not expected_state or state != expected_state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state parameter.",
            )

        # 2. Exchange code for tokens & fetch userinfo
        if mock_userinfo is not None:
            userinfo = mock_userinfo
        else:
            if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="Google OAuth is not configured.",
                )

            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    token_res = await client.post(token_url, data=data)
                    if token_res.status_code != 200:
                        logger.warning(f"Google token exchange failed: {token_res.text}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Failed to exchange authorization code with Google.",
                        )
                    token_data = token_res.json()
                    access_token = token_data.get("access_token")

                    # Fetch userinfo
                    userinfo_res = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if userinfo_res.status_code != 200:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Failed to retrieve profile from Google.",
                        )
                    userinfo = userinfo_res.json()
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error during Google OAuth flow: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Error communicating with Google identity services.",
                )

        # 3. Validate userinfo attributes
        google_sub = userinfo.get("sub")
        email = userinfo.get("email")
        email_verified = userinfo.get("email_verified", False)
        full_name = userinfo.get("name")

        if not google_sub or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incomplete identity information returned by Google.",
            )

        # Reject unverified emails
        if not email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account email is not verified.",
            )

        normalized_email = email.strip().lower()

        # 4. Lookup by google_sub first
        user = await self.user_repo.get_by_google_sub(db, google_sub)
        if user is None:
            # Check if email exists on another account
            existing_email_user = await self.user_repo.get_by_email(db, normalized_email)
            if existing_email_user:
                # Do not automatically link accounts
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "An account with this email address already exists. "
                        "Automatic account linking is not permitted."
                    ),
                )

            # Create new user
            user = await self.user_repo.create_user(
                db=db,
                email=normalized_email,
                password_hash=None,
                full_name=full_name,
                is_verified=True,
                google_sub=google_sub,
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
            )

        # 5. Establish session
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.SESSION_EXPIRE_SECONDS
        )

        await self.session_repo.create_session(
            db=db,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return user, raw_token


auth_service = AuthService()
