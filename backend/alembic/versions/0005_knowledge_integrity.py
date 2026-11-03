"""enforce cross-business ownership and source-type integrity for knowledge base

Revision ID: 0005_knowledge_integrity
Revises: 0004_knowledge_base
Create Date: 2026-11-03 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_knowledge_integrity"
down_revision: Union[str, None] = "0004_knowledge_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enforce unique (id, business_id) on knowledge_files
    op.create_unique_constraint(
        "uq_knowledge_files_id_business",
        "knowledge_files",
        ["id", "business_id"],
    )

    # 2. Replace single-column FK with composite FK on knowledge_base_entries
    op.drop_constraint(
        "fk_knowledge_base_entries_source_file_id",
        "knowledge_base_entries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_knowledge_base_entries_source_file_business",
        "knowledge_base_entries",
        "knowledge_files",
        ["source_file_id", "business_id"],
        ["id", "business_id"],
        ondelete="CASCADE",
    )

    # 3. Add CHECK constraint enforcing source-type integrity
    op.create_check_constraint(
        "ck_kbe_source_type_integrity",
        "knowledge_base_entries",
        "(source_type = 'FAQ' AND source_file_id IS NULL AND chunk_index IS NULL) "
        "OR (source_type = 'document_chunk' AND source_file_id IS NOT NULL AND chunk_index IS NOT NULL AND chunk_index >= 0)",
    )


def downgrade() -> None:
    # 1. Drop source-type integrity CHECK constraint
    op.drop_constraint(
        "ck_kbe_source_type_integrity",
        "knowledge_base_entries",
        type_="check",
    )

    # 2. Revert composite FK to single-column FK
    op.drop_constraint(
        "fk_knowledge_base_entries_source_file_business",
        "knowledge_base_entries",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_knowledge_base_entries_source_file_id",
        "knowledge_base_entries",
        "knowledge_files",
        ["source_file_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Drop unique constraint on knowledge_files
    op.drop_constraint(
        "uq_knowledge_files_id_business",
        "knowledge_files",
        type_="unique",
    )

