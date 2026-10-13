"""Business database repository."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.business_member import BusinessMember


class BusinessRepository:
    """Repository handling persistence operations for Business entities."""

    async def create_business(
        self,
        db: AsyncSession,
        name: str,
        slug: str,
        is_active: bool = True,
    ) -> Business:
        """Creates and flushes a new business record without committing."""
        business = Business(
            name=name.strip(),
            slug=slug.strip().lower(),
            is_active=is_active,
        )
        db.add(business)
        await db.flush()
        return business

    async def get_by_id(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        only_active: bool = False,
    ) -> Optional[Business]:
        """Fetches a business by its UUID primary key."""
        stmt = select(Business).where(Business.id == business_id)
        if only_active:
            stmt = stmt.where(Business.is_active == True)  # noqa: E712
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(
        self,
        db: AsyncSession,
        slug: str,
        only_active: bool = False,
    ) -> Optional[Business]:
        """Fetches a business by its unique slug."""
        normalized_slug = slug.strip().lower()
        stmt = select(Business).where(Business.slug == normalized_slug)
        if only_active:
            stmt = stmt.where(Business.is_active == True)  # noqa: E712
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_businesses_for_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        only_active: bool = True,
    ) -> List[Business]:
        """Retrieves all businesses that a user is a member of through BusinessMember."""
        stmt = (
            select(Business)
            .join(BusinessMember, Business.id == BusinessMember.business_id)
            .where(BusinessMember.user_id == user_id)
            .order_by(Business.created_at.desc())
        )
        if only_active:
            stmt = stmt.where(Business.is_active == True)  # noqa: E712
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_primary_business_for_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        only_active: bool = True,
    ) -> Optional[Business]:
        """Retrieves the first/primary business for a user if one exists."""
        businesses = await self.get_businesses_for_user(db, user_id, only_active=only_active)
        return businesses[0] if businesses else None


business_repository = BusinessRepository()
