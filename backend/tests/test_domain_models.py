"""Tests for Phase 2 Database Domain Schema & Multi-Tenancy Foundation.

Verifies:
1. Users can be created with UUID PK, timezone-aware timestamps, and active status.
2. Businesses can be created with UUID PK, unique slug, and active status.
3. A user can belong to a business via BusinessMember with a valid role.
4. A user can belong to multiple businesses.
5. A business can have multiple users.
6. Duplicate (business_id, user_id) membership is rejected.
7. Duplicate user email is rejected.
8. Duplicate business slug is rejected.
9. Foreign-key relationships work correctly with cascading deletions.
10. The schema supports business-level tenant isolation through business_id.
11. Invalid foreign keys are rejected.
12. Invalid membership roles are rejected by check constraint.
"""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.models import User, Business, BusinessMember, MemberRole


@pytest.fixture
async def db_session():
    """Provides an active AsyncSession for domain model testing."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()


# =====================================================================
# 1. User Creation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_create_user_success(db_session):
    """Verifies a user can be created with UUID PK, email, and timezone-aware timestamps."""
    unique_email = f"test_user_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.email == unique_email
    assert user.full_name == "Test User"
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)
    assert user.created_at.tzinfo is not None
    assert isinstance(user.updated_at, datetime)
    assert user.updated_at.tzinfo is not None

    # Clean up
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_duplicate_user_email_rejected(db_session):
    """Verifies that duplicate user email violates unique constraint."""
    shared_email = f"dup_user_{uuid.uuid4().hex[:8]}@example.com"
    user1 = User(email=shared_email, full_name="User One")
    db_session.add(user1)
    await db_session.commit()

    user2 = User(email=shared_email, full_name="User Two")
    db_session.add(user2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()

    # Clean up user1
    await db_session.delete(user1)
    await db_session.commit()


# =====================================================================
# 2. Business Creation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_create_business_success(db_session):
    """Verifies a business can be created with UUID PK, slug, and timezone-aware timestamps."""
    unique_slug = f"biz-{uuid.uuid4().hex[:8]}"
    business = Business(
        name="AgentDesk Corp",
        slug=unique_slug,
        is_active=True,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)

    assert isinstance(business.id, uuid.UUID)
    assert business.name == "AgentDesk Corp"
    assert business.slug == unique_slug
    assert business.is_active is True
    assert isinstance(business.created_at, datetime)
    assert business.created_at.tzinfo is not None
    assert isinstance(business.updated_at, datetime)
    assert business.updated_at.tzinfo is not None

    # Clean up
    await db_session.delete(business)
    await db_session.commit()


@pytest.mark.asyncio
async def test_duplicate_business_slug_rejected(db_session):
    """Verifies that duplicate business slug violates unique constraint."""
    shared_slug = f"dup-biz-{uuid.uuid4().hex[:8]}"
    biz1 = Business(name="Biz Alpha", slug=shared_slug)
    db_session.add(biz1)
    await db_session.commit()

    biz2 = Business(name="Biz Beta", slug=shared_slug)
    db_session.add(biz2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()

    # Clean up biz1
    await db_session.delete(biz1)
    await db_session.commit()


# =====================================================================
# 3. Membership & Relationship Tests
# =====================================================================

@pytest.mark.asyncio
async def test_user_belongs_to_business(db_session):
    """Verifies a user can belong to a business with an assigned role."""
    unique_email = f"member_{uuid.uuid4().hex[:8]}@example.com"
    unique_slug = f"membership-biz-{uuid.uuid4().hex[:8]}"

    user = User(email=unique_email, full_name="Owner Alice")
    business = Business(name="Alice Enterprise", slug=unique_slug)
    db_session.add_all([user, business])
    await db_session.commit()

    member = BusinessMember(
        business_id=business.id,
        user_id=user.id,
        role=MemberRole.OWNER.value,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)

    assert isinstance(member.id, uuid.UUID)
    assert member.business_id == business.id
    assert member.user_id == user.id
    assert member.role == "owner"
    assert isinstance(member.created_at, datetime)
    assert member.created_at.tzinfo is not None

    # Verify relationship navigation from Business to User
    stmt = (
        select(Business)
        .where(Business.id == business.id)
        .options(selectinload(Business.members).selectinload(BusinessMember.user))
    )
    res = await db_session.execute(stmt)
    loaded_biz = res.scalar_one()
    assert len(loaded_biz.members) == 1
    assert loaded_biz.members[0].user.email == unique_email

    # Clean up (deleting business cascades to membership)
    await db_session.delete(loaded_biz)
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_user_belongs_to_multiple_businesses(db_session):
    """Verifies a single user can belong to multiple businesses with different roles."""
    unique_email = f"multi_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=unique_email, full_name="Consultant Bob")
    biz_a = Business(name="Company A", slug=f"biz-a-{uuid.uuid4().hex[:8]}")
    biz_b = Business(name="Company B", slug=f"biz-b-{uuid.uuid4().hex[:8]}")

    db_session.add_all([user, biz_a, biz_b])
    await db_session.commit()

    member_a = BusinessMember(
        business_id=biz_a.id,
        user_id=user.id,
        role=MemberRole.OWNER.value,
    )
    member_b = BusinessMember(
        business_id=biz_b.id,
        user_id=user.id,
        role=MemberRole.MEMBER.value,
    )
    db_session.add_all([member_a, member_b])
    await db_session.commit()

    # Query memberships for this user
    stmt = (
        select(BusinessMember)
        .where(BusinessMember.user_id == user.id)
        .order_by(BusinessMember.created_at)
    )
    res = await db_session.execute(stmt)
    memberships = res.scalars().all()

    assert len(memberships) == 2
    roles = {m.role for m in memberships}
    biz_ids = {m.business_id for m in memberships}
    assert roles == {"owner", "member"}
    assert biz_ids == {biz_a.id, biz_b.id}

    # Clean up
    await db_session.delete(biz_a)
    await db_session.delete(biz_b)
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_business_has_multiple_users(db_session):
    """Verifies a single business can have multiple users with distinct roles."""
    business = Business(name="Team Corp", slug=f"team-{uuid.uuid4().hex[:8]}")
    user_owner = User(email=f"owner_{uuid.uuid4().hex[:8]}@example.com", full_name="Owner User")
    user_admin = User(email=f"admin_{uuid.uuid4().hex[:8]}@example.com", full_name="Admin User")
    user_member = User(email=f"mem_{uuid.uuid4().hex[:8]}@example.com", full_name="Staff User")

    db_session.add_all([business, user_owner, user_admin, user_member])
    await db_session.commit()

    db_session.add_all([
        BusinessMember(business_id=business.id, user_id=user_owner.id, role=MemberRole.OWNER.value),
        BusinessMember(business_id=business.id, user_id=user_admin.id, role=MemberRole.ADMIN.value),
        BusinessMember(business_id=business.id, user_id=user_member.id, role=MemberRole.MEMBER.value),
    ])
    await db_session.commit()

    # Query members for the business
    stmt = select(BusinessMember).where(BusinessMember.business_id == business.id)
    res = await db_session.execute(stmt)
    members = res.scalars().all()

    assert len(members) == 3
    member_roles = {m.role for m in members}
    assert member_roles == {"owner", "admin", "member"}

    # Clean up
    await db_session.delete(business)
    await db_session.delete(user_owner)
    await db_session.delete(user_admin)
    await db_session.delete(user_member)
    await db_session.commit()


# =====================================================================
# 4. Constraint & Integrity Tests
# =====================================================================

@pytest.mark.asyncio
async def test_duplicate_membership_rejected(db_session):
    """Verifies unique constraint on (business_id, user_id) rejects duplicate membership."""
    user = User(email=f"dup_mem_{uuid.uuid4().hex[:8]}@example.com")
    business = Business(name="Solo Biz", slug=f"solo-{uuid.uuid4().hex[:8]}")
    db_session.add_all([user, business])
    await db_session.commit()

    # First membership succeeds
    mem1 = BusinessMember(business_id=business.id, user_id=user.id, role=MemberRole.OWNER.value)
    db_session.add(mem1)
    await db_session.commit()

    # Duplicate membership for identical (business_id, user_id) must fail
    mem2 = BusinessMember(business_id=business.id, user_id=user.id, role=MemberRole.ADMIN.value)
    db_session.add(mem2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()

    # Clean up
    await db_session.delete(business)
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_invalid_role_rejected_by_check_constraint(db_session):
    """Verifies that check constraint ck_business_members_role rejects unapproved role values."""
    user = User(email=f"role_test_{uuid.uuid4().hex[:8]}@example.com")
    business = Business(name="Role Biz", slug=f"role-biz-{uuid.uuid4().hex[:8]}")
    db_session.add_all([user, business])
    await db_session.commit()

    invalid_member = BusinessMember(
        business_id=business.id,
        user_id=user.id,
        role="super_admin",  # Not in ('owner', 'admin', 'member')
    )
    db_session.add(invalid_member)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()

    # Clean up
    await db_session.delete(business)
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_invalid_foreign_keys_rejected(db_session):
    """Verifies that non-existent foreign keys are rejected by the database."""
    random_biz_id = uuid.uuid4()
    random_user_id = uuid.uuid4()

    # 1. Non-existent business_id and user_id
    invalid_mem = BusinessMember(
        business_id=random_biz_id,
        user_id=random_user_id,
        role=MemberRole.MEMBER.value,
    )
    db_session.add(invalid_mem)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # 2. Valid user, non-existent business
    valid_user = User(email=f"fk_user_{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(valid_user)
    await db_session.commit()

    invalid_biz_mem = BusinessMember(
        business_id=random_biz_id,
        user_id=valid_user.id,
        role=MemberRole.MEMBER.value,
    )
    db_session.add(invalid_biz_mem)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Clean up
    await db_session.delete(valid_user)
    await db_session.commit()


# =====================================================================
# 5. Cascading Deletion Tests
# =====================================================================

@pytest.mark.asyncio
async def test_cascade_delete_on_business_deletion(db_session):
    """Verifies deleting a business cascades to automatically delete its memberships."""
    user = User(email=f"cascade_biz_{uuid.uuid4().hex[:8]}@example.com")
    business = Business(name="Deletable Biz", slug=f"del-biz-{uuid.uuid4().hex[:8]}")
    db_session.add_all([user, business])
    await db_session.commit()

    member = BusinessMember(business_id=business.id, user_id=user.id, role=MemberRole.OWNER.value)
    db_session.add(member)
    await db_session.commit()
    member_id = member.id

    # Delete business
    await db_session.delete(business)
    await db_session.commit()

    # Verify membership was deleted
    res = await db_session.execute(
        select(BusinessMember).where(BusinessMember.id == member_id)
    )
    assert res.scalar_one_or_none() is None

    # User remains intact
    user_res = await db_session.execute(select(User).where(User.id == user.id))
    assert user_res.scalar_one_or_none() is not None

    # Clean up user
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_cascade_delete_on_user_deletion(db_session):
    """Verifies deleting a user cascades to automatically delete their memberships."""
    user = User(email=f"cascade_usr_{uuid.uuid4().hex[:8]}@example.com")
    business = Business(name="Persistent Biz", slug=f"keep-biz-{uuid.uuid4().hex[:8]}")
    db_session.add_all([user, business])
    await db_session.commit()

    member = BusinessMember(business_id=business.id, user_id=user.id, role=MemberRole.MEMBER.value)
    db_session.add(member)
    await db_session.commit()
    member_id = member.id

    # Delete user
    await db_session.delete(user)
    await db_session.commit()

    # Verify membership was deleted
    res = await db_session.execute(
        select(BusinessMember).where(BusinessMember.id == member_id)
    )
    assert res.scalar_one_or_none() is None

    # Business remains intact
    biz_res = await db_session.execute(select(Business).where(Business.id == business.id))
    assert biz_res.scalar_one_or_none() is not None

    # Clean up business
    await db_session.delete(business)
    await db_session.commit()


# =====================================================================
# 6. Tenant-Isolation Foundation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_business_id_tenant_isolation(db_session):
    """
    Demonstrates that business_id relationships provide strict logical isolation:
    Queries scoped by business_id strictly return only the records of that tenant.
    """
    biz_alpha = Business(name="Tenant Alpha", slug=f"tenant-alpha-{uuid.uuid4().hex[:8]}")
    biz_beta = Business(name="Tenant Beta", slug=f"tenant-beta-{uuid.uuid4().hex[:8]}")
    user_alpha = User(email=f"alpha_{uuid.uuid4().hex[:8]}@example.com", full_name="Alpha Staff")
    user_beta = User(email=f"beta_{uuid.uuid4().hex[:8]}@example.com", full_name="Beta Staff")

    db_session.add_all([biz_alpha, biz_beta, user_alpha, user_beta])
    await db_session.commit()

    mem_alpha = BusinessMember(
        business_id=biz_alpha.id,
        user_id=user_alpha.id,
        role=MemberRole.OWNER.value,
    )
    mem_beta = BusinessMember(
        business_id=biz_beta.id,
        user_id=user_beta.id,
        role=MemberRole.OWNER.value,
    )
    db_session.add_all([mem_alpha, mem_beta])
    await db_session.commit()

    # Query tenant Alpha's members
    alpha_query = select(BusinessMember).where(BusinessMember.business_id == biz_alpha.id)
    alpha_results = (await db_session.execute(alpha_query)).scalars().all()

    assert len(alpha_results) == 1
    assert alpha_results[0].user_id == user_alpha.id
    assert alpha_results[0].user_id != user_beta.id

    # Query tenant Beta's members
    beta_query = select(BusinessMember).where(BusinessMember.business_id == biz_beta.id)
    beta_results = (await db_session.execute(beta_query)).scalars().all()

    assert len(beta_results) == 1
    assert beta_results[0].user_id == user_beta.id
    assert beta_results[0].user_id != user_alpha.id

    # Clean up
    await db_session.delete(biz_alpha)
    await db_session.delete(biz_beta)
    await db_session.delete(user_alpha)
    await db_session.delete(user_beta)
    await db_session.commit()
