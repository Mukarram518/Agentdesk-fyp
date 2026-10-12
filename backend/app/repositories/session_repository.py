"""User session database repository."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import UserSession


class SessionRepository:
    """Repository handling persistence operations for UserSession entities."""

    async def create_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        """Persists a new server-side session."""
        session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            is_revoked=False,
        )
        db.add(session)
        await db.flush()
        return session

    async def get_by_token_hash(
        self, db: AsyncSession, token_hash: str
    ) -> Optional[UserSession]:
        """Retrieves an active session with eagerly loaded user by token hash."""
        stmt = (
            select(UserSession)
            .options(selectinload(UserSession.user))
            .where(UserSession.token_hash == token_hash)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_session(self, db: AsyncSession, token_hash: str) -> bool:
        """Marks a session as revoked."""
        stmt = (
            update(UserSession)
            .where(UserSession.token_hash == token_hash)
            .values(is_revoked=True)
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount > 0

    async def revoke_all_for_user(self, db: AsyncSession, user_id: uuid.UUID) -> int:
        """Revokes all active sessions for a user."""
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked == False)  # noqa: E712
            .values(is_revoked=True)
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount

    async def touch_session(self, db: AsyncSession, session_id: uuid.UUID) -> None:
        """Updates last_active_at timestamp for a session."""
        stmt = (
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(last_active_at=datetime.now(timezone.utc))
        )
        await db.execute(stmt)
        await db.flush()


session_repository = SessionRepository()
