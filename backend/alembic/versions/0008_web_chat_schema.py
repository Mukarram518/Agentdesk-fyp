"""web chat schema for conversations, messages, and business allowed_origins

Revision ID: 0008_web_chat_schema
Revises: 0007_embedding_model_versioning
Create Date: 2026-11-09 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0008_web_chat_schema"
down_revision: Union[str, None] = "0007_embedding_model_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add allowed_origins JSONB column to businesses
    op.add_column(
        "businesses",
        sa.Column(
            "allowed_origins",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    # 2. Create conversations table
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.String(length=50),
            server_default=sa.text("'web'"),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(length=20),
            server_default=sa.text("'en'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "outcome",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "summary",
            sa.Text(),
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
            name=op.f("fk_conversations_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )

    # 3. Create indexes on conversations
    op.create_index(
        op.f("ix_conversations_business_id"),
        "conversations",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversations_business_created",
        "conversations",
        ["business_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_conversations_business_status",
        "conversations",
        ["business_id", "status"],
        unique=False,
    )

    # 4. Create messages table
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="check_message_role",
        ),
        sa.CheckConstraint(
            "length(trim(content)) > 0",
            name="check_message_content_not_empty",
        ),
    )

    # 5. Create indexes on messages
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_messages_request_id"),
        "messages",
        ["request_id"],
        unique=False,
    )

    # 6. Create partial unique index on (conversation_id, request_id) for non-null request_id idempotency
    op.create_index(
        "uq_messages_conversation_request_id",
        "messages",
        ["conversation_id", "request_id"],
        unique=True,
        postgresql_where=sa.text("request_id IS NOT NULL"),
    )


def downgrade() -> None:
    # 1. Drop partial unique index on messages
    op.drop_index(
        "uq_messages_conversation_request_id",
        table_name="messages",
        postgresql_where=sa.text("request_id IS NOT NULL"),
    )

    # 2. Drop standard indexes on messages
    op.drop_index(op.f("ix_messages_request_id"), table_name="messages")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")

    # 3. Drop messages table
    op.drop_table("messages")

    # 4. Drop indexes on conversations
    op.drop_index("ix_conversations_business_status", table_name="conversations")
    op.drop_index("ix_conversations_business_created", table_name="conversations")
    op.drop_index(op.f("ix_conversations_business_id"), table_name="conversations")

    # 5. Drop conversations table
    op.drop_table("conversations")

    # 6. Drop allowed_origins column on businesses
    op.drop_column("businesses", "allowed_origins")
