"""add embedding_model column and legacy quarantine index

Revision ID: 0007_embedding_model_versioning
Revises: 0006_knowledge_claim_fields
Create Date: 2026-11-04 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_embedding_model_versioning"
down_revision: Union[str, None] = "0006_knowledge_claim_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable embedding_model column to knowledge_base_entries
    op.add_column(
        "knowledge_base_entries",
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
    )

    # 2. Add individual index on embedding_model
    op.create_index(
        "ix_knowledge_base_entries_embedding_model",
        "knowledge_base_entries",
        ["embedding_model"],
        unique=False,
    )

    # 3. Add composite index for tenant/model/stale filtering
    op.create_index(
        "ix_kbe_business_model_stale",
        "knowledge_base_entries",
        ["business_id", "embedding_model", "embedding_stale"],
        unique=False,
    )

    # 4. Safely classify all existing non-null embeddings as 'legacy-unknown'
    op.execute(
        """
        UPDATE knowledge_base_entries
        SET embedding_model = 'legacy-unknown'
        WHERE embedding IS NOT NULL;
        """
    )


def downgrade() -> None:
    # 1. Drop composite index
    op.drop_index("ix_kbe_business_model_stale", table_name="knowledge_base_entries")

    # 2. Drop individual index
    op.drop_index("ix_knowledge_base_entries_embedding_model", table_name="knowledge_base_entries")

    # 3. Drop embedding_model column
    op.drop_column("knowledge_base_entries", "embedding_model")

