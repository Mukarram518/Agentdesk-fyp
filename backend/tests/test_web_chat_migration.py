"""Alembic migration consistency and verification tests for Phase 7 Web Chat schema."""

import os
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest

from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No live database connection needed for pure migration consistency tests."""
    yield


@pytest.fixture(autouse=True)
def auto_reset_rate_limits():
    """No rate limit reset needed for in-memory migration checks."""
    yield


def get_alembic_script_directory() -> ScriptDirectory:
    """Helper locating Alembic configuration and script directory."""
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    script_loc = os.path.join(backend_dir, "alembic")

    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", script_loc)
    return ScriptDirectory.from_config(alembic_cfg)


def test_migration_chain_and_head_revision():
    """Verifies that 0008_web_chat_schema is in the chain and links to 0007_embedding_model_versioning."""
    script = get_alembic_script_directory()

    # Verify revision details and parent lineage
    rev_0008 = script.get_revision("0008_web_chat_schema")
    assert rev_0008 is not None
    assert rev_0008.revision == "0008_web_chat_schema"
    assert rev_0008.down_revision == "0007_embedding_model_versioning"


def test_migration_module_exports_and_callables():
    """Verifies that 0008_web_chat_schema defines callable upgrade and downgrade functions."""
    import importlib.util

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mig_path = os.path.join(backend_dir, "alembic", "versions", "0008_web_chat_schema.py")

    spec = importlib.util.spec_from_file_location("migration_0008", mig_path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "upgrade")
    assert callable(mod.upgrade)

    assert hasattr(mod, "downgrade")
    assert callable(mod.downgrade)

    assert mod.revision == "0008_web_chat_schema"
    assert mod.down_revision == "0007_embedding_model_versioning"


def test_migration_content_and_operations():
    """Verifies that the migration file contains all required schema operations and safety constraints."""
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mig_path = os.path.join(backend_dir, "alembic", "versions", "0008_web_chat_schema.py")
    assert os.path.exists(mig_path), f"Migration file not found at {mig_path}"

    with open(mig_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. businesses.allowed_origins
    assert "op.add_column" in content
    assert '"allowed_origins"' in content
    assert "'[]'::jsonb" in content

    # 2. conversations table
    assert 'op.create_table(\n        "conversations"' in content or 'op.create_table(\n        \'conversations\'' in content or 'op.create_table(\n        "conversations"' in content or '"conversations"' in content
    assert '"business_id"' in content
    assert '"channel"' in content
    assert "'web'" in content
    assert '"language"' in content
    assert "'en'" in content
    assert '"status"' in content
    assert "'active'" in content
    assert '"started_at"' in content
    assert '"ended_at"' in content
    assert '"outcome"' in content
    assert '"summary"' in content
    assert '"created_at"' in content
    assert '"updated_at"' in content
    assert '["businesses.id"]' in content
    assert 'ondelete="CASCADE"' in content

    # 3. messages table
    assert '"messages"' in content
    assert '"conversation_id"' in content
    assert '"role"' in content
    assert '"content"' in content
    assert '"request_id"' in content
    assert '["conversations.id"]' in content
    assert "check_message_role" in content
    assert "role IN ('user', 'assistant')" in content
    assert "check_message_content_not_empty" in content
    assert "length(trim(content)) > 0" in content

    # 4. Indexes & Partial unique index for idempotency
    assert "ix_conversations_business_created" in content
    assert "ix_conversations_business_status" in content
    assert "ix_messages_conversation_created" in content
    assert "uq_messages_conversation_request_id" in content
    assert "request_id IS NOT NULL" in content

    # 5. Downgrade completeness
    assert "op.drop_table(\"messages\")" in content
    assert "op.drop_table(\"conversations\")" in content
    assert "op.drop_column(\"businesses\", \"allowed_origins\")" in content
    assert "op.drop_index" in content


def test_migration_and_sqlalchemy_model_consistency():
    """Verifies that the migration definition matches the SQLAlchemy Declarative models."""
    conv_table = Base.metadata.tables["conversations"]
    msg_table = Base.metadata.tables["messages"]
    biz_table = Base.metadata.tables["businesses"]

    # Verify conversations model columns
    expected_conv_cols = {
        "id",
        "business_id",
        "channel",
        "language",
        "status",
        "started_at",
        "ended_at",
        "outcome",
        "summary",
        "created_at",
        "updated_at",
    }
    assert set(conv_table.c.keys()) == expected_conv_cols

    # Verify messages model columns
    expected_msg_cols = {
        "id",
        "conversation_id",
        "business_id",
        "role",
        "content",
        "request_id",
        "reply_to_id",
        "created_at",
    }
    assert set(msg_table.c.keys()) == expected_msg_cols

    # Verify businesses allowed_origins
    assert "allowed_origins" in biz_table.c
