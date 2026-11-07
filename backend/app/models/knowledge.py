"""Knowledge base entry domain model for FAQs and document chunks."""

import enum
import uuid
from datetime import datetime
from typing import Optional, List, Any, TYPE_CHECKING
from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    CheckConstraint,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from pgvector.sqlalchemy import Vector

from app.models import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.knowledge_file import KnowledgeFile

# Confirmed embedding vector dimension for sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_VECTOR_DIMENSION = 384

# Canonical embedding model identities
ACTIVE_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
LEGACY_UNKNOWN_EMBEDDING_MODEL = "legacy-unknown"


class KnowledgeSourceType(str, enum.Enum):
    """Approved knowledge entry source types."""
    FAQ = "FAQ"
    DOCUMENT_CHUNK = "document_chunk"


class KnowledgeLanguage(str, enum.Enum):
    """Supported content languages."""
    EN = "en"
    UR = "ur"
    MIXED = "mixed"


class KnowledgeBaseEntry(Base):
    """KnowledgeBaseEntry entity representing FAQs or extracted document chunks.

    Multi-tenancy and referential integrity guarantees:
    - Scoped strictly to one business via business_id foreign key.
    - Foreign key cascade delete from businesses (deleting a business deletes all knowledge entries).
    - Foreign key cascade delete from knowledge_files (deleting a file removes all its chunks).
    - Embedding column uses pgvector with confirmed dimension 384.
    - Check constraint restricts language to supported values ('en', 'ur', 'mixed').
    - Compound indexes optimize tenant-isolated retrieval by source type, freshness, and recency.
    """

    __tablename__ = "knowledge_base_entries"

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
    question: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    tags: Mapped[List[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(20),
        default=KnowledgeLanguage.EN.value,
        server_default=text(f"'{KnowledgeLanguage.EN.value}'"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        default=KnowledgeSourceType.FAQ.value,
        server_default=text(f"'{KnowledgeSourceType.FAQ.value}'"),
        nullable=False,
    )
    source_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    chunk_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    section_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    embedding_stale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=func.false(),
        nullable=False,
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    embedding = mapped_column(
        Vector(EMBEDDING_VECTOR_DIMENSION),
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
    business: Mapped["Business"] = relationship("Business", back_populates="knowledge_entries")
    source_file: Mapped[Optional["KnowledgeFile"]] = relationship(
        "KnowledgeFile",
        back_populates="entries",
        primaryjoin="and_(foreign(KnowledgeBaseEntry.source_file_id) == KnowledgeFile.id, KnowledgeBaseEntry.business_id == KnowledgeFile.business_id)",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["source_file_id", "business_id"],
            ["knowledge_files.id", "knowledge_files.business_id"],
            name="fk_knowledge_base_entries_source_file_business",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "language IN ('en', 'ur', 'mixed')",
            name="ck_knowledge_base_entries_language",
        ),
        CheckConstraint(
            "(source_type = 'FAQ' AND source_file_id IS NULL AND chunk_index IS NULL) "
            "OR (source_type = 'document_chunk' AND source_file_id IS NOT NULL AND chunk_index IS NOT NULL AND chunk_index >= 0)",
            name="ck_kbe_source_type_integrity",
        ),
        Index("ix_knowledge_base_entries_business_source", "business_id", "source_type"),
        Index("ix_knowledge_base_entries_business_created", "business_id", "created_at"),
        Index("ix_knowledge_base_entries_business_stale", "business_id", "embedding_stale"),
        Index("ix_kbe_business_model_stale", "business_id", "embedding_model", "embedding_stale"),
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeBaseEntry id={self.id} business_id={self.business_id} "
            f"source_type='{self.source_type}' language='{self.language}'>"
        )

