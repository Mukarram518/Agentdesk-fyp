"""User database repository."""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class UserRepository:
    """Repository handling persistence operations for User entities."""

    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Fetches a user by primary key ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Fetches a user by email address (case-insensitive normalized)."""
        normalized_email = email.strip().lower()
        result = await db.execute(
            select(User).where(User.email == normalized_email)
        )
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, db: AsyncSession, google_sub: str) -> Optional[User]:
        """Fetches a user by Google OAuth provider subject ID."""
        result = await db.execute(
            select(User).where(User.google_sub == google_sub)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        db: AsyncSession,
        email: str,
        password_hash: Optional[str] = None,
        full_name: Optional[str] = None,
        is_verified: bool = False,
        google_sub: Optional[str] = None,
    ) -> User:
        """Creates and persists a new user entity."""
        normalized_email = email.strip().lower()
        user = User(
            email=normalized_email,
            password_hash=password_hash,
            full_name=full_name.strip() if full_name else None,
            is_verified=is_verified,
            google_sub=google_sub,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        return user


user_repository = UserRepository()
