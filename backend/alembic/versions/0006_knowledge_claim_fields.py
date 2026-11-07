"""add processing_token and processing_started_at to knowledge_files

Revision ID: 0006_knowledge_claim_fields
Revises: 0005_knowledge_integrity
Create Date: 2026-11-03 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_knowledge_claim_fields"
down_revision: Union[str, None] = "0005_knowledge_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add dedicated processing claim token column
    op.add_column(
        "knowledge_files",
        sa.Column("processing_token", sa.String(length=64), nullable=True),
    )

    # 2. Add dedicated processing started timestamp column
    op.add_column(
        "knowledge_files",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Create index on processing_token for fast claim lookups
    op.create_index(
        "ix_knowledge_files_processing_token",
        "knowledge_files",
        ["processing_token"],
        unique=False,
    )


def downgrade() -> None:
    # 1. Drop index on processing_token
    op.drop_index("ix_knowledge_files_processing_token", table_name="knowledge_files")

    # 2. Drop processing_started_at column
    op.drop_column("knowledge_files", "processing_started_at")

    # 3. Drop processing_token column
    op.drop_column("knowledge_files", "processing_token")

