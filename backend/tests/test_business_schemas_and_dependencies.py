"""Tests for Business Pydantic schemas and FastAPI business dependencies.

Covers:
- BusinessCreate validation, whitespace stripping, slug normalization, invalid characters, length bounds.
- BusinessResponse serialization, ORM attribute mapping, factory method, and exclusion of sensitive data.
- get_current_business_membership dependency (success, missing business 404, inactive business 404).
- get_current_business dependency extraction.
- require_business_owner dependency authorization (owner 200, member/admin 403).
- Verification that dependencies do not accept untrusted client-supplied business IDs.
"""

import inspect
import uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.api.dependencies.business import (
    get_current_business,
    get_current_business_membership,
    require_business_owner,
)
from app.core.database import async_session_factory
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.repositories import business_repository, business_member_repository, user_repository
from app.schemas.business import BusinessCreate, BusinessCreateRequest, BusinessResponse
from app.services.business_service import business_service


# ============================================================================
# 1. BusinessCreate Schema Tests
# ============================================================================

def test_business_create_valid_name_only():
    """Verifies that BusinessCreate succeeds with name only and strips whitespace."""
    data = BusinessCreate(name="  Acme Dental Studio  ")
    assert data.name == "Acme Dental Studio"
    assert data.slug is None


def test_business_create_valid_with_custom_slug():
    """Verifies custom slug is stripped and lowercased."""
    data = BusinessCreate(name="Acme Dental Studio", slug="  Acme-Dental-Studio  ")
    assert data.name == "Acme Dental Studio"
    assert data.slug == "acme-dental-studio"


def test_business_create_empty_or_whitespace_slug_is_none():
    """Verifies whitespace-only slug is normalized to None (so service can auto-generate)."""
    data = BusinessCreate(name="Acme Dental Studio", slug="   ")
    assert data.slug is None


def test_business_create_alias_compatibility():
    """Verifies BusinessCreateRequest is an alias for BusinessCreate."""
    assert BusinessCreateRequest is BusinessCreate


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "   ",
        "A",  # Less than 2 chars
        "A" * 256,  # Greater than 255 chars
    ],
)
def test_business_create_invalid_names(invalid_name):
    """Verifies that invalid business names raise ValidationError."""
    with pytest.raises(ValidationError):
        BusinessCreate(name=invalid_name)


@pytest.mark.parametrize(
    "invalid_slug",
    [
        "a",  # Less than 2 chars
        "a" * 101,  # Greater than 100 chars
        "acme dental",  # Contains spaces
        "acme_dental",  # Contains underscores
        "acme@dental",  # Contains special symbols
        "-acme",  # Leading hyphen
        "acme-",  # Trailing hyphen
        "acme--dental",  # Double hyphen
    ],
)
def test_business_create_invalid_slugs(invalid_slug):
    """Verifies that invalid custom slugs raise ValidationError."""
    with pytest.raises(ValidationError):
        BusinessCreate(name="Acme Dental", slug=invalid_slug)


def test_business_create_rejects_client_injected_fields():
    """Verifies that extra client fields (user_id, role, id) are not part of the schema."""
    data = BusinessCreate(name="Acme Dental")
    assert not hasattr(data, "user_id")
    assert not hasattr(data, "role")
    assert not hasattr(data, "id")
    assert not hasattr(data, "is_active")


# ============================================================================
# 2. BusinessResponse Schema Tests
# ============================================================================

def test_business_response_serialization():
    """Verifies BusinessResponse serializes all required fields."""
    now = datetime.now(timezone.utc)
    biz_id = uuid.uuid4()
    res = BusinessResponse(
        id=biz_id,
        name="Acme Dental",
        slug="acme-dental",
        is_active=True,
        role="owner",
        created_at=now,
        updated_at=now,
    )

    dumped = res.model_dump()
    assert dumped["id"] == biz_id
    assert dumped["name"] == "Acme Dental"
    assert dumped["slug"] == "acme-dental"
    assert dumped["is_active"] is True
    assert dumped["role"] == "owner"
    assert dumped["created_at"] == now
    assert dumped["updated_at"] == now

    # Verify no sensitive data or internal relationship keys exist
    assert "hashed_password" not in dumped
    assert "session_token" not in dumped
    assert "users" not in dumped
    assert "members" not in dumped


def test_business_response_from_orm_factory():
    """Verifies the from_orm_business factory method with a mock ORM model."""
    now = datetime.now(timezone.utc)
    biz_id = uuid.uuid4()

    class MockBusiness:
        id = biz_id
        name = "Apex Medical"
        slug = "apex-medical"
        is_active = True
        created_at = now
        updated_at = now

    res = BusinessResponse.from_orm_business(MockBusiness(), role="admin")
    assert res.id == biz_id
    assert res.name == "Apex Medical"
    assert res.slug == "apex-medical"
    assert res.is_active is True
    assert res.role == "admin"
    assert res.created_at == now
    assert res.updated_at == now


# ============================================================================
# 3. Business Dependencies Tests
# ============================================================================

def test_dependencies_do_not_accept_untrusted_client_business_id():
    """Verifies dependencies inspect user context only and accept no untrusted client business_id."""
    sig_membership = inspect.signature(get_current_business_membership)
    assert "business_id" not in sig_membership.parameters
    assert "client_business_id" not in sig_membership.parameters
    assert "user" in sig_membership.parameters
    assert "db" in sig_membership.parameters

    sig_current = inspect.signature(get_current_business)
    assert "business_id" not in sig_current.parameters
    assert "business_and_member" in sig_current.parameters

    sig_owner = inspect.signature(require_business_owner)
    assert "business_id" not in sig_owner.parameters
    assert "business_and_member" in sig_owner.parameters


@pytest.mark.asyncio
async def test_get_current_business_membership_success():
    """Verifies resolving active business and membership for a valid user."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(
            db,
            email=f"dep_owner_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Dr. Dependency Test",
        )
        biz_name = f"Dependency Success Clinic {uuid.uuid4().hex[:8]}"
        created_biz, created_member = await business_service.create_business_for_user(
            db=db,
            user=user,
            name=biz_name,
        )

        biz, member = await get_current_business_membership(user=user, db=db)
        assert biz.id == created_biz.id
        assert biz.name == biz_name
        assert member.id == created_member.id
        assert member.role == MemberRole.OWNER.value

        # Test get_current_business extraction
        extracted_biz = await get_current_business((biz, member))
        assert extracted_biz.id == created_biz.id

        # Test require_business_owner success
        owner_biz, owner_member = await require_business_owner((biz, member))
        assert owner_biz.id == created_biz.id
        assert owner_member.role == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_get_current_business_membership_no_business_raises_404():
    """Verifies 404 is raised if the user has no onboarded business."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(
            db,
            email=f"dep_nobiz_{uuid.uuid4().hex[:8]}@example.com",
            full_name="No Biz User",
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_business_membership(user=user, db=db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "No active business found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_business_membership_inactive_business_raises_404():
    """Verifies 404 is raised if the user's business is deactivated."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(
            db,
            email=f"dep_inactive_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Inactive Biz User",
        )
        biz_name = f"Inactive Clinic {uuid.uuid4().hex[:8]}"
        biz, _ = await business_service.create_business_for_user(
            db=db,
            user=user,
            name=biz_name,
        )

        # Deactivate the business
        biz.is_active = False
        await db.commit()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_business_membership(user=user, db=db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "No active business found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_business_owner_rejects_non_owner():
    """Verifies 403 Forbidden is raised when the user is a member/admin, not an owner."""
    now = datetime.now(timezone.utc)
    mock_biz = Business(
        id=uuid.uuid4(),
        name="Staff Business",
        slug="staff-business",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    # Member role
    member_record = BusinessMember(
        id=uuid.uuid4(),
        business_id=mock_biz.id,
        user_id=uuid.uuid4(),
        role=MemberRole.MEMBER.value,
        created_at=now,
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_business_owner((mock_biz, member_record))

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Only the business owner is authorized" in exc_info.value.detail

    # Admin role (also not owner)
    admin_record = BusinessMember(
        id=uuid.uuid4(),
        business_id=mock_biz.id,
        user_id=uuid.uuid4(),
        role=MemberRole.ADMIN.value,
        created_at=now,
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_business_owner((mock_biz, admin_record))

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Only the business owner is authorized" in exc_info.value.detail
