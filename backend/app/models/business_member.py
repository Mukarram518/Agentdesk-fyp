"""Business member model representing the membership relationship between users and businesses."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User


class MemberRole(str, enum.Enum):
    """Roles supported for business memberships."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class BusinessMember(Base):
    """BusinessMember entity joining users to businesses with an assigned role.

    Guarantees:
    - Unique membership per (business_id, user_id) tuple.
    - Cascading deletion when either the business or user is deleted.
    - Foreign key constraints enforcing referential integrity.
    - Check constraint restricting roles to approved values ('owner', 'admin', 'member').
    """

    __tablename__ = "business_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default=MemberRole.MEMBER.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_members_business_user"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_business_members_role",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BusinessMember id={self.id} business_id={self.business_id} "
            f"user_id={self.user_id} role={self.role}>"
        )
