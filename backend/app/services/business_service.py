"""Business service coordinating business creation, tenant validation, and memberships."""

import re
import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.user import User
from app.repositories.business_repository import business_repository, BusinessRepository
from app.repositories.business_member_repository import (
    business_member_repository,
    BusinessMemberRepository,
)


class BusinessService:
    """Service encapsulating business onboarding and tenant scoping business logic."""

    def __init__(
        self,
        business_repo: BusinessRepository = business_repository,
        business_member_repo: BusinessMemberRepository = business_member_repository,
    ) -> None:
        self.business_repo = business_repo
        self.business_member_repo = business_member_repo

    @staticmethod
    def slugify(text: str) -> str:
        """Converts a business name into a URL-friendly slug.

        Normalizes to lowercase, strips apostrophes, replaces non-alphanumeric characters
        with hyphens, and removes leading/trailing hyphens.
        """
        # Lowercase and remove apostrophes
        s = text.lower().replace("'", "").replace("’", "")
        # Replace non-alphanumeric sequences with a hyphen
        s = re.sub(r"[^a-z0-9]+", "-", s)
        # Strip leading and trailing hyphens
        s = s.strip("-")
        return s

    async def create_business_for_user(
        self,
        db: AsyncSession,
        user: User,
        name: str,
        slug: Optional[str] = None,
    ) -> Tuple[Business, BusinessMember]:
        """Creates a new business entity and assigns the authenticated user as owner.

        Guarantees:
        - Validates business name and generates a URL-safe slug.
        - Enforces slug uniqueness and provides clear conflict messaging.
        - Atomically writes Business and BusinessMember in one transaction.
        - Rolls back completely on failure so no orphaned business or membership exists.
        - Strictly binds ownership to authenticated user.id with hardcoded 'owner' role.
        """
        if not user or not user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to create a business.",
            )

        # 1. Normalize and validate business name
        cleaned_name = name.strip() if name else ""
        if not cleaned_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Business name cannot be empty.",
            )
        if len(cleaned_name) < 2 or len(cleaned_name) > 255:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Business name must be between 2 and 255 characters.",
            )

        # 2. Generate and validate URL slug
        if slug and slug.strip():
            cleaned_slug = self.slugify(slug.strip())
        else:
            cleaned_slug = self.slugify(cleaned_name)

        if not cleaned_slug or len(cleaned_slug) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Business name must contain at least 2 alphanumeric characters to produce a valid slug.",
            )
        if len(cleaned_slug) > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Business slug cannot exceed 100 characters.",
            )

        # 3. Check slug availability
        existing = await self.business_repo.get_by_slug(db, cleaned_slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A business with the slug '{cleaned_slug}' already exists.",
            )

        # 4. Atomic creation: Business + BusinessMember (owner)
        try:
            business = await self.business_repo.create_business(
                db=db,
                name=cleaned_name,
                slug=cleaned_slug,
                is_active=True,
            )
            membership = await self.business_member_repo.create_member(
                db=db,
                business_id=business.id,
                user_id=user.id,
                role=MemberRole.OWNER.value,
            )
            # Flush both entities together to check database integrity constraints
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            logger.warning(
                f"Integrity conflict creating business '{cleaned_name}' with slug '{cleaned_slug}': {exc}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A business with the slug '{cleaned_slug}' already exists.",
            )
        except Exception as exc:
            await db.rollback()
            logger.error(f"Unexpected error creating business '{cleaned_name}': {exc}")
            raise

        return business, membership

    async def get_user_businesses(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[Business]:
        """Returns all active businesses the user belongs to, ordered by most recent."""
        return await self.business_repo.get_businesses_for_user(
            db, user_id=user_id, only_active=True
        )

    async def get_user_businesses_with_roles(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[Tuple[Business, Optional[str]]]:
        """Returns all active businesses for the user paired with their membership role."""
        businesses = await self.get_user_businesses(db, user_id=user_id)
        results: List[Tuple[Business, Optional[str]]] = []
        for biz in businesses:
            membership = await self.business_member_repo.get_membership(
                db, business_id=biz.id, user_id=user_id
            )
            role = membership.role if membership else None
            results.append((biz, role))
        return results

    async def get_current_user_business(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        business_id: Optional[uuid.UUID] = None,
    ) -> Optional[Tuple[Business, BusinessMember]]:
        """Retrieves an active business and membership for the authenticated user.

        Security Guarantees:
        - If business_id is provided, verifies that user_id is an active member of that business.
          Never returns a business purely because its ID was supplied by a client.
        - If business_id is not provided, deterministically selects the user's primary/first active business.
        - Returns None if the user has no active businesses or is not a member of the requested business.
        """
        if business_id is not None:
            # Explicit business requested: verify tenant authorization via membership
            membership = await self.business_member_repo.get_membership_with_business(
                db, business_id=business_id, user_id=user_id
            )
            if (
                not membership
                or not membership.business
                or not membership.business.is_active
            ):
                return None
            return membership.business, membership

        # Deterministic primary business lookup: most recent active membership
        memberships = await self.business_member_repo.list_memberships_for_user(db, user_id)
        for m in memberships:
            full_m = await self.business_member_repo.get_membership_with_business(
                db, business_id=m.business_id, user_id=user_id
            )
            if full_m and full_m.business and full_m.business.is_active:
                return full_m.business, full_m

        return None


business_service = BusinessService()
