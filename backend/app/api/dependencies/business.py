"""Business-related FastAPI dependencies for tenant scoping and authorization."""

from typing import Tuple
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.user import User
from app.services.business_service import business_service


async def get_current_business_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Business, BusinessMember]:
    """Dependency that resolves the active business and membership for the current user.

    Guarantees:
    - Strictly derives business from the authenticated user's session.
    - Never trusts an untrusted client-supplied business ID as proof of access.
    - Raises HTTP 404 if the user has not onboarded a business yet or if it is inactive.
    """
    result = await business_service.get_current_user_business(db, user_id=user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active business found for this account. Please complete business onboarding.",
        )
    return result


async def get_current_business(
    business_and_member: Tuple[Business, BusinessMember] = Depends(
        get_current_business_membership
    ),
) -> Business:
    """Dependency that returns the active Business entity for the current user."""
    business, _ = business_and_member
    return business


async def require_business_owner(
    business_and_member: Tuple[Business, BusinessMember] = Depends(
        get_current_business_membership
    ),
) -> Tuple[Business, BusinessMember]:
    """Dependency that restricts access to the business owner only.

    Raises HTTP 403 Forbidden if the user is not an owner of the active business.
    """
    _, membership = business_and_member
    if membership.role != MemberRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the business owner is authorized to perform this operation.",
        )
    return business_and_member
