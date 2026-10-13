"""Tests for BusinessService: business onboarding, slug validation, atomic creation, and tenant isolation."""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.database import async_session_factory
from app.models.business_member import MemberRole
from app.repositories import user_repository, business_repository
from app.services.business_service import business_service, BusinessService


@pytest.mark.asyncio
async def test_create_business_for_user_success():
    """Verifies that business creation succeeds and automatically establishes owner membership."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(
            db,
            email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Dr. Jane Doe",
        )

        business, membership = await business_service.create_business_for_user(
            db=db,
            user=user,
            name="Apex Dental Care",
        )

        assert business.id is not None
        assert business.name == "Apex Dental Care"
        assert business.slug == "apex-dental-care"
        assert business.is_active is True

        assert membership.id is not None
        assert membership.business_id == business.id
        assert membership.user_id == user.id
        assert membership.role == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_slug_generation_and_normalization():
    """Verifies that slug generation handles special characters, apostrophes, and custom slugs."""
    assert BusinessService.slugify("Dr. John's Dental & Care!") == "dr-johns-dental-care"
    assert BusinessService.slugify("  ---Super   Salon---  ") == "super-salon"
    assert BusinessService.slugify("Café 123") == "caf-123"

    async with async_session_factory() as db:
        user = await user_repository.create_user(db, email=f"u_{uuid.uuid4().hex[:8]}@example.com")

        # Custom slug provided
        custom_slug = f"my-custom-slug-{uuid.uuid4().hex[:6]}"
        biz, _ = await business_service.create_business_for_user(
            db=db,
            user=user,
            name="Another Store",
            slug=custom_slug,
        )
        assert biz.slug == custom_slug


@pytest.mark.asyncio
async def test_reject_empty_name_or_invalid_slug():
    """Verifies that invalid, empty, or whitespace-only names are rejected with HTTP 422."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(db, email=f"u_{uuid.uuid4().hex[:8]}@example.com")

        # Empty name
        with pytest.raises(HTTPException) as exc1:
            await business_service.create_business_for_user(db=db, user=user, name="")
        assert exc1.value.status_code == 422
        assert "cannot be empty" in exc1.value.detail

        # Whitespace name
        with pytest.raises(HTTPException) as exc2:
            await business_service.create_business_for_user(db=db, user=user, name="   ")
        assert exc2.value.status_code == 422

        # Non-alphanumeric symbols only (generates empty slug)
        with pytest.raises(HTTPException) as exc3:
            await business_service.create_business_for_user(db=db, user=user, name="!@#$%^&*")
        assert exc3.value.status_code == 422
        assert "alphanumeric" in exc3.value.detail


@pytest.mark.asyncio
async def test_duplicate_slug_conflict_raises_409():
    """Verifies that slug collisions return a clear HTTP 409 Conflict."""
    async with async_session_factory() as db:
        user1 = await user_repository.create_user(db, email=f"u1_{uuid.uuid4().hex[:8]}@example.com")
        user2 = await user_repository.create_user(db, email=f"u2_{uuid.uuid4().hex[:8]}@example.com")

        unique_name = f"Unique Business {uuid.uuid4().hex[:8]}"
        await business_service.create_business_for_user(db=db, user=user1, name=unique_name)

        # Attempt to create duplicate with identical name/slug
        with pytest.raises(HTTPException) as exc:
            await business_service.create_business_for_user(db=db, user=user2, name=unique_name)
        assert exc.value.status_code == 409
        assert "already exists" in exc.value.detail


@pytest.mark.asyncio
async def test_rollback_on_failure_leaves_no_orphaned_business():
    """Verifies that if an error occurs during atomic creation, transaction is rolled back."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(db, email=f"u_{uuid.uuid4().hex[:8]}@example.com")
        target_slug = f"atomic-test-{uuid.uuid4().hex[:8]}"

        # Mock membership creation to simulate an integrity / database failure
        with patch.object(
            business_service.business_member_repo,
            "create_member",
            side_effect=IntegrityError("INSERT INTO business_members", {}, Exception("Simulated DB error")),
        ):
            with pytest.raises(HTTPException) as exc:
                await business_service.create_business_for_user(
                    db=db,
                    user=user,
                    name="Atomic Test Biz",
                    slug=target_slug,
                )
            assert exc.value.status_code == 409

        # Ensure the business was rolled back and does not exist
        persisted = await business_repository.get_by_slug(db, target_slug)
        assert persisted is None


@pytest.mark.asyncio
async def test_tenant_isolation_in_business_retrieval():
    """Verifies that users can only retrieve businesses they belong to and cannot access other tenants."""
    async with async_session_factory() as db:
        user_a = await user_repository.create_user(db, email=f"ua_{uuid.uuid4().hex[:8]}@example.com")
        user_b = await user_repository.create_user(db, email=f"ub_{uuid.uuid4().hex[:8]}@example.com")

        biz_a, _ = await business_service.create_business_for_user(
            db=db, user=user_a, name=f"Biz A {uuid.uuid4().hex[:6]}"
        )
        biz_b, _ = await business_service.create_business_for_user(
            db=db, user=user_b, name=f"Biz B {uuid.uuid4().hex[:6]}"
        )

        # User A retrieves their own primary business
        res_a = await business_service.get_current_user_business(db, user_id=user_a.id)
        assert res_a is not None
        assert res_a[0].id == biz_a.id

        # User B retrieves their own primary business
        res_b = await business_service.get_current_user_business(db, user_id=user_b.id)
        assert res_b is not None
        assert res_b[0].id == biz_b.id

        # User A explicitly attempts to request User B's business_id -> strictly blocked (returns None)
        unauthorized_a = await business_service.get_current_user_business(
            db, user_id=user_a.id, business_id=biz_b.id
        )
        assert unauthorized_a is None

        # User B explicitly attempts to request User A's business_id -> strictly blocked (returns None)
        unauthorized_b = await business_service.get_current_user_business(
            db, user_id=user_b.id, business_id=biz_a.id
        )
        assert unauthorized_b is None


@pytest.mark.asyncio
async def test_inactive_business_not_returned():
    """Verifies that deactivated businesses are filtered out by get_current_user_business."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(db, email=f"u_{uuid.uuid4().hex[:8]}@example.com")
        biz, _ = await business_service.create_business_for_user(
            db=db, user=user, name=f"Deactivated Biz {uuid.uuid4().hex[:6]}"
        )

        # Deactivate business
        biz.is_active = False
        await db.flush()

        res = await business_service.get_current_user_business(db, user_id=user.id)
        assert res is None
