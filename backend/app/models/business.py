"""Business domain model representing tenant entities."""

import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.business_member import BusinessMember
    from app.models.knowledge_file import KnowledgeFile
    from app.models.knowledge import KnowledgeBaseEntry
    from app.models.conversation import Conversation


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
    allowed_origins: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
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
    knowledge_files: Mapped[List["KnowledgeFile"]] = relationship(
        "KnowledgeFile",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    knowledge_entries: Mapped[List["KnowledgeBaseEntry"]] = relationship(
        "KnowledgeBaseEntry",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="business",
        cascade="all, delete-orphan",
    )

    @property
    def allowed_website_origins(self) -> List[str]:
        """Alias property for allowed_origins."""
        return self.allowed_origins if self.allowed_origins is not None else []

    @allowed_website_origins.setter
    def allowed_website_origins(self, value: List[str]) -> None:
        self.allowed_origins = value

    def is_origin_allowed(self, origin: Optional[str]) -> bool:
        """Determines if a candidate website origin is explicitly permitted.

        Security guarantees:
        - Rejects empty, whitespace, or None origins.
        - Rejects arbitrary origins by default (empty allowed_origins matches nothing).
        - RFC 6454-compliant origin normalization and exact equality comparison.
        - Prevents wildcard origins and unsafe substring/suffix matching.
        """
        from app.core.widget_auth import validate_business_origin

        return validate_business_origin(origin, self.allowed_origins)

    def __repr__(self) -> str:
        return (
            f"<Business id={self.id} name={self.name} slug={self.slug} "
            f"is_active={self.is_active} allowed_origins={self.allowed_origins}>"
        )
