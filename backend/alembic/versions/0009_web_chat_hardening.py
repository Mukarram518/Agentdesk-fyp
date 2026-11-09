"""web chat hardening with business_id scoping, composite FK, and reply_to

Revision ID: 0009_web_chat_hardening
Revises: 0008_web_chat_schema
Create Date: 2026-11-09 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0009_web_chat_hardening"
down_revision: Union[str, None] = "0008_web_chat_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add business_id column to messages as nullable initially for safe backfill
    op.add_column(
        "messages",
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 2. Backfill business_id from conversations for any existing message rows
    op.execute(
        sa.text(
            """
            UPDATE messages
            SET business_id = conversations.business_id
            FROM conversations
            WHERE messages.conversation_id = conversations.id
            """
        )
    )

    # 3. Alter business_id to NOT NULL
    op.alter_column(
        "messages",
        "business_id",
        nullable=False,
    )

    # 4. Add unique constraint on conversations(id, business_id) to serve as composite FK target
    op.create_unique_constraint(
        "uq_conversations_id_business_id",
        "conversations",
        ["id", "business_id"],
    )

    # 5. Drop original single-column FK on messages.conversation_id
    op.drop_constraint(
        "fk_messages_conversation_id_conversations",
        "messages",
        type_="foreignkey",
    )

    # 6. Add composite foreign key constraint from messages(conversation_id, business_id)
    #    to conversations(id, business_id) with CASCADE deletion
    op.create_foreign_key(
        "fk_messages_conversation_business",
        "messages",
        "conversations",
        ["conversation_id", "business_id"],
        ["id", "business_id"],
        ondelete="CASCADE",
    )

    # 7. Add foreign key from messages.business_id to businesses.id with CASCADE deletion
    op.create_foreign_key(
        "fk_messages_business_id_businesses",
        "messages",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 8. Create index on messages.business_id
    op.create_index(
        op.f("ix_messages_business_id"),
        "messages",
        ["business_id"],
        unique=False,
    )

    # 9. Drop migration 0008's per-conversation unique index
    op.drop_index(
        "uq_messages_conversation_request_id",
        table_name="messages",
        postgresql_where=sa.text("request_id IS NOT NULL"),
    )

    # 10. Create tenant-scoped partial unique index on messages(business_id, request_id)
    op.create_index(
        "uq_messages_business_request_id",
        "messages",
        ["business_id", "request_id"],
        unique=True,
        postgresql_where=sa.text("request_id IS NOT NULL"),
    )

    # 11. Add reply_to_id column to messages (nullable UUID)
    op.add_column(
        "messages",
        sa.Column(
            "reply_to_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 12. Add self-referencing foreign key on messages.reply_to_id referencing messages.id
    op.create_foreign_key(
        "fk_messages_reply_to_id_messages",
        "messages",
        "messages",
        ["reply_to_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 13. Create index on messages.reply_to_id
    op.create_index(
        op.f("ix_messages_reply_to_id"),
        "messages",
        ["reply_to_id"],
        unique=False,
    )

    # 14. Create partial unique index on non-null reply_to_id (ensures at most one reply per message)
    op.create_index(
        "uq_messages_reply_to_id",
        "messages",
        ["reply_to_id"],
        unique=True,
        postgresql_where=sa.text("reply_to_id IS NOT NULL"),
    )

    # 15. Add check constraint restricting reply_to_id to assistant messages
    op.create_check_constraint(
        "check_message_reply_to_assistant_only",
        "messages",
        sa.text("reply_to_id IS NULL OR role = 'assistant'"),
    )


def downgrade() -> None:
    # 1. Drop check constraint on reply_to_id
    op.drop_constraint(
        "check_message_reply_to_assistant_only",
        "messages",
        type_="check",
    )

    # 2. Drop partial unique index on reply_to_id
    op.drop_index(
        "uq_messages_reply_to_id",
        table_name="messages",
        postgresql_where=sa.text("reply_to_id IS NOT NULL"),
    )

    # 3. Drop index on reply_to_id
    op.drop_index(
        op.f("ix_messages_reply_to_id"),
        table_name="messages",
    )

    # 4. Drop self-referencing foreign key on reply_to_id
    op.drop_constraint(
        "fk_messages_reply_to_id_messages",
        "messages",
        type_="foreignkey",
    )

    # 5. Drop column reply_to_id
    op.drop_column("messages", "reply_to_id")

    # 6. Drop tenant-scoped partial unique index on (business_id, request_id)
    op.drop_index(
        "uq_messages_business_request_id",
        table_name="messages",
        postgresql_where=sa.text("request_id IS NOT NULL"),
    )

    # 7. Recreate migration 0008's index on (conversation_id, request_id)
    op.create_index(
        "uq_messages_conversation_request_id",
        "messages",
        ["conversation_id", "request_id"],
        unique=True,
        postgresql_where=sa.text("request_id IS NOT NULL"),
    )

    # 8. Drop index on messages.business_id
    op.drop_index(
        op.f("ix_messages_business_id"),
        table_name="messages",
    )

    # 9. Drop foreign key on messages.business_id
    op.drop_constraint(
        "fk_messages_business_id_businesses",
        "messages",
        type_="foreignkey",
    )

    # 10. Drop composite foreign key on (conversation_id, business_id)
    op.drop_constraint(
        "fk_messages_conversation_business",
        "messages",
        type_="foreignkey",
    )

    # 11. Recreate original single-column foreign key on messages.conversation_id
    op.create_foreign_key(
        "fk_messages_conversation_id_conversations",
        "messages",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 12. Drop unique constraint on conversations(id, business_id)
    op.drop_constraint(
        "uq_conversations_id_business_id",
        "conversations",
        type_="unique",
    )

    # 13. Drop column business_id on messages
    op.drop_column("messages", "business_id")
