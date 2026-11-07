"""KnowledgeFile domain model representing uploaded documents for the business knowledge base."""

import enum
import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String,
    Text,
    BigInteger,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from app.models import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.knowledge import KnowledgeBaseEntry


class KnowledgeFileStatus(str, enum.Enum):
    """Lifecycle processing statuses for uploaded knowledge files."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeFile(Base):
    """KnowledgeFile entity storing metadata for uploaded PDF and DOCX documents.

    Multi-tenancy and referential integrity guarantees:
    - Scoped strictly to one business via business_id foreign key.
    - Foreign key cascade delete from businesses (deleting a business deletes all files).
    - Cascades deletion to all derived chunks in knowledge_base_entries.
    - Status restricted to valid processing states via check constraint.
    """

    __tablename__ = "knowledge_files"

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
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default=KnowledgeFileStatus.PENDING.value,
        server_default=text(f"'{KnowledgeFileStatus.PENDING.value}'"),
        nullable=False,
    )
    processing_token: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
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
    business: Mapped["Business"] = relationship("Business", back_populates="knowledge_files")
    entries: Mapped[List["KnowledgeBaseEntry"]] = relationship(
        "KnowledgeBaseEntry",
        back_populates="source_file",
        cascade="all, delete-orphan",
        primaryjoin="and_(KnowledgeFile.id == foreign(KnowledgeBaseEntry.source_file_id), KnowledgeFile.business_id == KnowledgeBaseEntry.business_id)",
    )

    __table_args__ = (
        UniqueConstraint("id", "business_id", name="uq_knowledge_files_id_business"),
        CheckConstraint(
            "processing_status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_knowledge_files_status",
        ),
        Index("ix_knowledge_files_business_status", "business_id", "processing_status"),
        Index("ix_knowledge_files_business_created", "business_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeFile id={self.id} business_id={self.business_id} "
            f"filename='{self.filename}' status='{self.processing_status}'>"
        )

