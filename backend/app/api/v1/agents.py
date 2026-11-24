"""Agent configuration API routes for AgentDesk."""

from typing import Tuple
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.business import require_business_owner
from app.core.database import get_db
from app.models.business import Business
from app.models.business_member import BusinessMember
from app.schemas.agent_config import AgentConfigResponse, AgentConfigUpdate
from app.services.agent_config_service import agent_config_service

router = APIRouter()


@router.get(
    "/config",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get business agent configuration",
)
async def get_agent_config(
    business_and_member: Tuple[Business, BusinessMember] = Depends(require_business_owner),
    db: AsyncSession = Depends(get_db),
) -> AgentConfigResponse:
    """Retrieves the agent configuration for the authenticated business.

    Security Guarantees:
    - business_id is strictly derived from the authenticated session context.
    - Requires business owner permissions (HTTP 403 for non-owners).
    - Automatically initializes default configuration on first access.
    """
    business, _ = business_and_member
    config = await agent_config_service.get_or_create_config(db, business_id=business.id)
    return AgentConfigResponse.from_orm_entry(config)


@router.put(
    "/config",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Update business agent configuration (PUT)",
)
async def update_agent_config_put(
    payload: AgentConfigUpdate,
    business_and_member: Tuple[Business, BusinessMember] = Depends(require_business_owner),
    db: AsyncSession = Depends(get_db),
) -> AgentConfigResponse:
    """Updates agent configuration fields for the authenticated business using HTTP PUT.

    Security Guarantees:
    - business_id is strictly derived from the authenticated session context.
    - Requires business owner permissions (HTTP 403 for non-owners).
    - Cross-tenant tampering is strictly prevented.
    - Input parameters are validated before persistence.
    """
    business, _ = business_and_member
    updated = await agent_config_service.update_config(
        db=db,
        business_id=business.id,
        payload=payload,
    )
    return AgentConfigResponse.from_orm_entry(updated)


@router.patch(
    "/config",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Update business agent configuration (PATCH)",
)
async def update_agent_config_patch(
    payload: AgentConfigUpdate,
    business_and_member: Tuple[Business, BusinessMember] = Depends(require_business_owner),
    db: AsyncSession = Depends(get_db),
) -> AgentConfigResponse:
    """Updates agent configuration fields for the authenticated business using HTTP PATCH.

    Provides complete compatibility with API design specifications.
    """
    business, _ = business_and_member
    updated = await agent_config_service.update_config(
        db=db,
        business_id=business.id,
        payload=payload,
    )
    return AgentConfigResponse.from_orm_entry(updated)

