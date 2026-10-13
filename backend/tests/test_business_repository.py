"""Tests for Business and BusinessMember repository layer."""

import uuid
import pytest
from app.core.database import async_session_factory
from app.models.business_member import MemberRole
from app.repositories import (
    business_repository,
    business_member_repository,
    user_repository,
)


@pytest.mark.asyncio
async def test_create_and_get_business_by_id():
    """Verifies creating a business and retrieving it by primary key ID."""
    async with async_session_factory() as db:
        unique_slug = f"acme-{uuid.uuid4().hex[:8]}"
        business = await business_repository.create_business(
            db,
            name="Acme Health Clinic",
            slug=unique_slug,
            is_active=True,
        )

        assert business.id is not None
        assert business.name == "Acme Health Clinic"
        assert business.slug == unique_slug
        assert business.is_active is True

        fetched = await business_repository.get_by_id(db, business.id)
        assert fetched is not None
        assert fetched.id == business.id
        assert fetched.name == "Acme Health Clinic"
        assert fetched.slug == unique_slug


@pytest.mark.asyncio
async def test_get_business_by_slug_case_insensitive():
    """Verifies slug retrieval is case-insensitive and normalized."""
    async with async_session_factory() as db:
        unique_slug = f"dentist-{uuid.uuid4().hex[:8]}"
        business = await business_repository.create_business(
            db,
            name="Dentist Care",
            slug=unique_slug,
        )

        # Upper case lookup
        fetched_upper = await business_repository.get_by_slug(db, unique_slug.upper())
        assert fetched_upper is not None
        assert fetched_upper.id == business.id

        # Lower case lookup
        fetched_lower = await business_repository.get_by_slug(db, unique_slug.lower())
        assert fetched_lower is not None
        assert fetched_lower.id == business.id


@pytest.mark.asyncio
async def test_filtering_inactive_businesses():
    """Verifies only_active filters inactive businesses where appropriate."""
    async with async_session_factory() as db:
        unique_slug = f"inactive-{uuid.uuid4().hex[:8]}"
        business = await business_repository.create_business(
            db,
            name="Inactive Corp",
            slug=unique_slug,
            is_active=False,
        )

        # get_by_id with only_active=True
        assert await business_repository.get_by_id(db, business.id, only_active=True) is None
        # get_by_id with only_active=False
        active_false = await business_repository.get_by_id(db, business.id, only_active=False)
        assert active_false is not None
        assert active_false.id == business.id

        # get_by_slug with only_active=True
        assert await business_repository.get_by_slug(db, unique_slug, only_active=True) is None
        # get_by_slug with only_active=False
        assert await business_repository.get_by_slug(db, unique_slug, only_active=False) is not None


@pytest.mark.asyncio
async def test_create_and_get_membership():
    """Verifies creating and querying a business membership."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(
            db,
            email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Business Owner",
        )
        business = await business_repository.create_business(
            db,
            name="Solitary Business",
            slug=f"biz-{uuid.uuid4().hex[:8]}",
        )

        membership = await business_member_repository.create_member(
            db,
            business_id=business.id,
            user_id=user.id,
            role=MemberRole.OWNER.value,
        )

        assert membership.id is not None
        assert membership.role == "owner"
        assert membership.business_id == business.id
        assert membership.user_id == user.id

        fetched = await business_member_repository.get_membership(db, business.id, user.id)
        assert fetched is not None
        assert fetched.id == membership.id
        assert fetched.role == "owner"


@pytest.mark.asyncio
async def test_get_businesses_for_user_and_primary_lookup():
    """Verifies fetching user businesses through BusinessMember join."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(
            db,
            email=f"multi_{uuid.uuid4().hex[:8]}@example.com",
        )
        biz1 = await business_repository.create_business(
            db,
            name="First Business",
            slug=f"first-{uuid.uuid4().hex[:8]}",
        )
        biz2 = await business_repository.create_business(
            db,
            name="Second Business",
            slug=f"second-{uuid.uuid4().hex[:8]}",
        )
        inactive_biz = await business_repository.create_business(
            db,
            name="Inactive Business",
            slug=f"inactive-{uuid.uuid4().hex[:8]}",
            is_active=False,
        )

        await business_member_repository.create_member(db, biz1.id, user.id, role=MemberRole.OWNER.value)
        await business_member_repository.create_member(db, biz2.id, user.id, role=MemberRole.MEMBER.value)
        await business_member_repository.create_member(db, inactive_biz.id, user.id, role=MemberRole.MEMBER.value)

        # Active businesses only (default)
        active_user_businesses = await business_repository.get_businesses_for_user(db, user.id, only_active=True)
        assert len(active_user_businesses) == 2
        biz_ids = {b.id for b in active_user_businesses}
        assert biz1.id in biz_ids
        assert biz2.id in biz_ids
        assert inactive_biz.id not in biz_ids

        # All businesses including inactive
        all_user_businesses = await business_repository.get_businesses_for_user(db, user.id, only_active=False)
        assert len(all_user_businesses) == 3

        # Primary business lookup
        primary = await business_repository.get_primary_business_for_user(db, user.id)
        assert primary is not None
        assert primary.id in {biz1.id, biz2.id}


@pytest.mark.asyncio
async def test_list_memberships_for_user_and_business():
    """Verifies listing memberships by user or business."""
    async with async_session_factory() as db:
        user1 = await user_repository.create_user(db, email=f"u1_{uuid.uuid4().hex[:8]}@example.com")
        user2 = await user_repository.create_user(db, email=f"u2_{uuid.uuid4().hex[:8]}@example.com")
        biz = await business_repository.create_business(db, name="Team Business", slug=f"team-{uuid.uuid4().hex[:8]}")

        await business_member_repository.create_member(db, biz.id, user1.id, role=MemberRole.OWNER.value)
        await business_member_repository.create_member(db, biz.id, user2.id, role=MemberRole.ADMIN.value)

        biz_members = await business_member_repository.list_memberships_for_business(db, biz.id)
        assert len(biz_members) == 2

        user1_memberships = await business_member_repository.list_memberships_for_user(db, user1.id)
        assert len(user1_memberships) == 1
        assert user1_memberships[0].business_id == biz.id


@pytest.mark.asyncio
async def test_get_membership_with_eager_loaded_business():
    """Verifies get_membership_with_business eagerly loads the related Business model."""
    async with async_session_factory() as db:
        user = await user_repository.create_user(db, email=f"eager_{uuid.uuid4().hex[:8]}@example.com")
        biz = await business_repository.create_business(
            db,
            name="Eager Loaded Clinic",
            slug=f"eager-{uuid.uuid4().hex[:8]}",
        )
        await business_member_repository.create_member(db, biz.id, user.id, role=MemberRole.OWNER.value)

        membership = await business_member_repository.get_membership_with_business(db, biz.id, user.id)
        assert membership is not None
        assert membership.business is not None
        assert membership.business.id == biz.id
        assert membership.business.name == "Eager Loaded Clinic"
