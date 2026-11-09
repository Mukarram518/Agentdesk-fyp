"""Message domain model representing individual conversation turns."""

from datetime import datetime
import enum
from typing import Optional, TYPE_CHECKING
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class MessageRole(str, enum.Enum):
    """Supported roles for conversation messages."""

    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    """Message entity representing an individual chat message in a conversation.

    Multi-tenancy and referential integrity guarantees:
    - Scoped strictly to one conversation and one business via composite foreign key.
    - Cascading deletion: deleting a conversation deletes all associated messages.
    - Role is restricted to 'user' or 'assistant'.
    - Content must be non-empty text (enforced by check constraint).
    - Tenant-scoped idempotency: (business_id, request_id) is unique when request_id is not null.
    - Deterministic 1-to-1 reply threading: reply_to_id references the parent user message.
    - Check constraint: reply_to_id can only be non-null for assistant messages.
    - Partial unique index on reply_to_id: ensures at most one assistant reply per user message.
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE", name="fk_messages_business_id_businesses"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    reply_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL", name="fk_messages_reply_to_id_messages"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
        foreign_keys="[Message.conversation_id, Message.business_id]",
    )
    reply_to: Mapped[Optional["Message"]] = relationship(
        "Message",
        remote_side="Message.id",
        foreign_keys="[Message.reply_to_id]",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "business_id"],
            ["conversations.id", "conversations.business_id"],
            ondelete="CASCADE",
            name="fk_messages_conversation_business",
        ),
        CheckConstraint("role IN ('user', 'assistant')", name="check_message_role"),
        CheckConstraint("length(trim(content)) > 0", name="check_message_content_not_empty"),
        CheckConstraint(
            "reply_to_id IS NULL OR role = 'assistant'",
            name="check_message_reply_to_assistant_only",
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_business_id", "business_id"),
        Index(
            "uq_messages_business_request_id",
            "business_id",
            "request_id",
            unique=True,
            postgresql_where=text("request_id IS NOT NULL"),
        ),
        Index(
            "uq_messages_reply_to_id",
            "reply_to_id",
            unique=True,
            postgresql_where=text("reply_to_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} conversation_id={self.conversation_id} "
            f"business_id={self.business_id} role={self.role} "
            f"request_id={self.request_id} reply_to_id={self.reply_to_id}>"
        )
