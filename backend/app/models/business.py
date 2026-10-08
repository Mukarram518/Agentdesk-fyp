"""Business domain model representing tenant entities."""

import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.business_member import BusinessMember


class Business(Base):
    """Business entity representing the primary tenant in AgentDesk.

    All tenant-scoped resources (conversations, leads, knowledge entries, etc.)
    belong to a Business via business_id foreign key relationships.
    """

    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=func.true(),
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
    members: Mapped[List["BusinessMember"]] = relationship(
        "BusinessMember",
        back_populates="business",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Business id={self.id} name={self.name} slug={self.slug} is_active={self.is_active}>"
