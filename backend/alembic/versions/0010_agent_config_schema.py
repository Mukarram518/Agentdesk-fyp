"""agent config schema for business tenant AI agent preferences

Revision ID: 0010_agent_config_schema
Revises: 0009_web_chat_hardening
Create Date: 2026-11-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0010_agent_config_schema"
down_revision: Union[str, None] = "0009_web_chat_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create agent_configs table
    op.create_table(
        "agent_configs",
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "voice_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "chat_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "lead_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "voice_id",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "tone",
            sa.String(length=50),
            server_default=sa.text("'helpful'"),
            nullable=False,
        ),
        sa.Column(
            "greeting",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "language_priority",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[\"en\", \"ur\"]'::jsonb"),
            nullable=False,
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
            name="fk_agent_configs_business_id_businesses",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "business_id",
            name="pk_agent_configs",
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_configs")

