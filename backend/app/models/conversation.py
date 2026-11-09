"""Conversation domain model for customer interaction threads."""

from datetime import datetime
import enum
from typing import List, Optional, TYPE_CHECKING
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.message import Message


class ConversationChannel(str, enum.Enum):
    """Supported communication channels for conversations."""

    WEB = "web"
    WHATSAPP = "whatsapp"
    VOICE = "voice"


class ConversationStatus(str, enum.Enum):
    """Lifecycle states of a conversation."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class Conversation(Base):
    """Conversation entity representing a multi-turn customer interaction thread.

    Multi-tenancy and referential integrity guarantees:
    - Scoped strictly to one business via business_id foreign key.
    - Cascading deletion: deleting a business deletes all associated conversations.
    - Default channel is 'web' for Phase 7 Web Chat.
    - Default status is 'active'.
    - Messages are ordered chronologically by creation timestamp.
    """

    __tablename__ = "conversations"

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
    channel: Mapped[str] = mapped_column(
        String(50),
        default=ConversationChannel.WEB.value,
        server_default=text("'web'"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(20),
        default="en",
        server_default=text("'en'"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=ConversationStatus.ACTIVE.value,
        server_default=text("'active'"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    outcome: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    business: Mapped["Business"] = relationship(
        "Business",
        back_populates="conversations",
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        foreign_keys="[Message.conversation_id, Message.business_id]",
    )

    __table_args__ = (
        UniqueConstraint("id", "business_id", name="uq_conversations_id_business_id"),
        Index("ix_conversations_business_created", "business_id", "created_at"),
        Index("ix_conversations_business_status", "business_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} business_id={self.business_id} "
            f"channel={self.channel} status={self.status} language={self.language}>"
        )
