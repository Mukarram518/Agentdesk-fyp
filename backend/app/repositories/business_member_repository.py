"""Business member database repository."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_member import BusinessMember, MemberRole


class BusinessMemberRepository:
    """Repository handling persistence operations for BusinessMember entities."""

    async def create_member(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str = MemberRole.MEMBER.value,
    ) -> BusinessMember:
        """Creates and flushes a new business membership record without committing."""
        member = BusinessMember(
            business_id=business_id,
            user_id=user_id,
            role=role,
        )
        db.add(member)
        await db.flush()
        return member

    async def get_membership(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[BusinessMember]:
        """Retrieves the membership record for a given user in a specific business."""
        stmt = select(BusinessMember).where(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_membership_with_business(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[BusinessMember]:
        """Retrieves membership with the related Business entity eagerly loaded."""
        stmt = (
            select(BusinessMember)
            .options(selectinload(BusinessMember.business))
            .where(
                BusinessMember.business_id == business_id,
                BusinessMember.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_memberships_for_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[BusinessMember]:
        """Lists all business memberships for a given user."""
        stmt = (
            select(BusinessMember)
            .where(BusinessMember.user_id == user_id)
            .order_by(BusinessMember.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_memberships_for_business(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
    ) -> List[BusinessMember]:
        """Lists all members for a given business."""
        stmt = (
            select(BusinessMember)
            .where(BusinessMember.business_id == business_id)
            .order_by(BusinessMember.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


business_member_repository = BusinessMemberRepository()
