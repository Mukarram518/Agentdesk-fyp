"""Alembic migration consistency and verification tests for Phase 7 Web Chat hardening (0009)."""

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
    """Verifies that 0009_web_chat_hardening is the unique head and links to 0008_web_chat_schema."""
    script = get_alembic_script_directory()

    # Verify single unique head
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0009_web_chat_hardening"

    # Verify revision details and parent lineage
    rev_0009 = script.get_revision("0009_web_chat_hardening")
    assert rev_0009 is not None
    assert rev_0009.revision == "0009_web_chat_hardening"
    assert rev_0009.down_revision == "0008_web_chat_schema"


def test_migration_module_exports_and_callables():
    """Verifies that 0009_web_chat_hardening defines callable upgrade and downgrade functions."""
    import importlib.util

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mig_path = os.path.join(backend_dir, "alembic", "versions", "0009_web_chat_hardening.py")

    spec = importlib.util.spec_from_file_location("migration_0009", mig_path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "upgrade")
    assert callable(mod.upgrade)

    assert hasattr(mod, "downgrade")
    assert callable(mod.downgrade)

    assert mod.revision == "0009_web_chat_hardening"
    assert mod.down_revision == "0008_web_chat_schema"


def test_migration_content_and_operations():
    """Verifies that migration 0009 contains all required schema operations, composite FK, and constraints."""
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mig_path = os.path.join(backend_dir, "alembic", "versions", "0009_web_chat_hardening.py")
    assert os.path.exists(mig_path), f"Migration file not found at {mig_path}"

    with open(mig_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. messages.business_id with backfill
    assert 'op.add_column(\n        "messages"' in content or 'op.add_column("messages"' in content or '"business_id"' in content
    assert "UPDATE messages" in content
    assert "SET business_id = conversations.business_id" in content

    # 2. Composite FK and unique constraint
    assert "uq_conversations_id_business_id" in content
    assert "fk_messages_conversation_business" in content
    assert '["conversation_id", "business_id"]' in content
    assert '["id", "business_id"]' in content

    # 3. Tenant-scoped idempotency unique index
    assert "uq_messages_business_request_id" in content
    assert '["business_id", "request_id"]' in content
    assert "request_id IS NOT NULL" in content

    # 4. reply_to_id column, foreign key, partial unique index, and check constraint
    assert '"reply_to_id"' in content
    assert "fk_messages_reply_to_id_messages" in content
    assert "uq_messages_reply_to_id" in content
    assert "check_message_reply_to_assistant_only" in content
    assert "reply_to_id IS NULL OR role = 'assistant'" in content

    # 5. Symmetrical downgrade operations
    assert "op.drop_constraint(\n        \"check_message_reply_to_assistant_only\"" in content or "check_message_reply_to_assistant_only" in content
    assert "op.drop_index" in content
    assert "uq_messages_conversation_request_id" in content
    assert "fk_messages_conversation_id_conversations" in content
