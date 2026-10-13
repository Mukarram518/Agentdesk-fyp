"""Business API routes for AgentDesk onboarding, listing, and tenant scoping."""

import uuid
from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.business import get_current_business_membership
from app.core.database import get_db
from app.models.business import Business
from app.models.business_member import BusinessMember
from app.models.user import User
from app.schemas.business import BusinessCreate, BusinessResponse
from app.services.business_service import business_service

router = APIRouter()


@router.post(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business",
)
async def create_business(
    payload: BusinessCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessResponse:
    """Creates a new business entity and assigns the authenticated user as owner.

    Security Guarantees:
    - user_id and owner identity are strictly derived from the authenticated session.
    - Client-supplied role or owner tampering is prevented.
    - Slug collision results in a 409 Conflict.
    - Business and owner membership are committed atomically.
    """
    business, membership = await business_service.create_business_for_user(
        db=db,
        user=user,
        name=payload.name,
        slug=payload.slug,
    )
    return BusinessResponse.from_orm_business(business, role=membership.role)


@router.get(
    "",
    response_model=List[BusinessResponse],
    status_code=status.HTTP_200_OK,
    summary="List authenticated user's active businesses",
)
async def list_businesses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[BusinessResponse]:
    """Retrieves all active businesses the authenticated user is a member of.

    Security Guarantees:
    - Strictly scoped to the authenticated user's memberships.
    - Never returns businesses belonging to other tenants.
    - Deactivated businesses are excluded.
    - Attaches the authenticated user's actual role for each business.
    """
    items = await business_service.get_user_businesses_with_roles(db, user_id=user.id)
    return [
        BusinessResponse.from_orm_business(biz, role=role)
        for biz, role in items
    ]


@router.get(
    "/current",
    response_model=BusinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current active business",
)
async def get_current_business(
    business_and_member: Tuple[Business, BusinessMember] = Depends(
        get_current_business_membership
    ),
) -> BusinessResponse:
    """Returns the authenticated user's primary/active business and role.

    Guarantees:
    - Resolves business deterministically using the existing dependency.
    - Returns 404 if no active business is associated with the authenticated account.
    """
    business, membership = business_and_member
    return BusinessResponse.from_orm_business(business, role=membership.role)


@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get business details by ID",
)
async def get_business_by_id(
    business_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessResponse:
    """Retrieves business details by UUID if the authenticated user is an active member.

    Security Guarantees:
    - Enforces tenant isolation: nonexistent, unauthorized, or inactive businesses return 404.
    - Cross-tenant data existence is never disclosed.
    - User identity and role are strictly derived from the verified database membership.
    """
    result = await business_service.get_current_user_business(
        db=db, user_id=user.id, business_id=business_id
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )
    business, membership = result
    return BusinessResponse.from_orm_business(business, role=membership.role)
