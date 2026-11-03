"""knowledge base schema for knowledge_files and knowledge_base_entries

Revision ID: 0004_knowledge_base
Revises: 0003_authentication
Create Date: 2026-11-03 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# Confirmed embedding vector dimension for sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_VECTOR_DIMENSION = 384

# revision identifiers, used by Alembic.
revision: str = "0004_knowledge_base"
down_revision: Union[str, None] = "0003_authentication"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create knowledge_files table
    op.create_table(
        "knowledge_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "processing_status",
            sa.String(length=50),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_knowledge_files_business_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_files")),
        sa.CheckConstraint(
            "processing_status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_knowledge_files_status",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_files_business_id"),
        "knowledge_files",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_files_business_status",
        "knowledge_files",
        ["business_id", "processing_status"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_files_business_created",
        "knowledge_files",
        ["business_id", "created_at"],
        unique=False,
    )

    # 2. Create knowledge_base_entries table
    op.create_table(
        "knowledge_base_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(length=20),
            server_default=sa.text("'en'"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.String(length=50),
            server_default=sa.text("'FAQ'"),
            nullable=False,
        ),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column(
            "embedding_stale",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            Vector(EMBEDDING_VECTOR_DIMENSION),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_knowledge_base_entries_business_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["knowledge_files.id"],
            name=op.f("fk_knowledge_base_entries_source_file_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_base_entries")),
        sa.CheckConstraint(
            "language IN ('en', 'ur', 'mixed')",
            name="ck_knowledge_base_entries_language",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_base_entries_business_id"),
        "knowledge_base_entries",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_base_entries_source_file_id"),
        "knowledge_base_entries",
        ["source_file_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_base_entries_business_source",
        "knowledge_base_entries",
        ["business_id", "source_type"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_base_entries_business_created",
        "knowledge_base_entries",
        ["business_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_base_entries_business_stale",
        "knowledge_base_entries",
        ["business_id", "embedding_stale"],
        unique=False,
    )


def downgrade() -> None:
    # 1. Drop knowledge_base_entries table and its indexes
    op.drop_index("ix_knowledge_base_entries_business_stale", table_name="knowledge_base_entries")
    op.drop_index("ix_knowledge_base_entries_business_created", table_name="knowledge_base_entries")
    op.drop_index("ix_knowledge_base_entries_business_source", table_name="knowledge_base_entries")
    op.drop_index(op.f("ix_knowledge_base_entries_source_file_id"), table_name="knowledge_base_entries")
    op.drop_index(op.f("ix_knowledge_base_entries_business_id"), table_name="knowledge_base_entries")
    op.drop_table("knowledge_base_entries")

    # 2. Drop knowledge_files table and its indexes
    op.drop_index("ix_knowledge_files_business_created", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_business_status", table_name="knowledge_files")
    op.drop_index(op.f("ix_knowledge_files_business_id"), table_name="knowledge_files")
    op.drop_table("knowledge_files")

