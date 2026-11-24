"""Tests for Phase 4A AgentConfig model and repository.

Verifies:
1. AgentConfig model metadata registration in app.models and Base.metadata.
2. Column attributes, types, defaults, and primary/foreign keys.
3. Business one-to-one relationship with cascade delete.
4. JSONB language priority persistence and update.
5. Repository create_default with defaults and custom parameters.
6. Repository get_by_business_id.
7. Repository get_or_create_default idempotency.
8. Repository update with field whitelist and whitespace stripping.
9. Tenant isolation (Business A cannot access or overwrite Business B's configuration).
10. Database CASCADE deletion: deleting Business deletes its associated AgentConfig.
"""

import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import inspect, select
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import async_session_factory
from app.models import (
    Base,
    Business,
    AgentConfig,
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_TONE,
)
from app.repositories.agent_config import agent_config_repository, AgentConfigRepository


# =====================================================================
# 1. Model Registration & Schema Introspection Tests
# =====================================================================

def test_agent_config_model_registered_in_metadata():
    """Verifies that agent_configs table is registered in Base.metadata."""
    table_names = Base.metadata.tables.keys()
    assert "agent_configs" in table_names
    assert "businesses" in table_names


def test_agent_config_public_exports():
    """Verifies that AgentConfig and constants are publicly exported from app.models."""
    from app import models

    assert hasattr(models, "AgentConfig")
    assert hasattr(models, "DEFAULT_LANGUAGE_PRIORITY")
    assert hasattr(models, "DEFAULT_TONE")


def test_agent_config_table_columns_and_constraints():
    """Verifies column definitions, types, constraints, and foreign keys on agent_configs."""
    table = Base.metadata.tables["agent_configs"]

    # Check columns exist
    expected_columns = {
        "business_id",
        "voice_enabled",
        "chat_enabled",
        "lead_enabled",
        "voice_id",
        "tone",
        "greeting",
        "language_priority",
        "created_at",
        "updated_at",
    }
    assert expected_columns.issubset(set(table.columns.keys()))

    # Primary key check
    assert table.c.business_id.primary_key is True

    # Foreign key check
    fks = list(table.c.business_id.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "businesses.id"
    assert fk.ondelete == "CASCADE"

    # Nullable constraints
    assert table.c.business_id.nullable is False
    assert table.c.voice_enabled.nullable is False
    assert table.c.chat_enabled.nullable is False
    assert table.c.lead_enabled.nullable is False
    assert table.c.tone.nullable is False
    assert table.c.language_priority.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False
    assert table.c.voice_id.nullable is True
    assert table.c.greeting.nullable is True


def test_agent_config_business_relationship_configuration():
    """Verifies the one-to-one relationship between Business and AgentConfig."""
    biz_mapper = inspect(Business)
    assert "agent_config" in biz_mapper.relationships
    rel = biz_mapper.relationships["agent_config"]
    assert rel.uselist is False
    assert rel.back_populates == "business"

    config_mapper = inspect(AgentConfig)
    assert "business" in config_mapper.relationships
    config_rel = config_mapper.relationships["business"]
    assert config_rel.uselist is False
    assert config_rel.back_populates == "agent_config"


# =====================================================================
# 2. Database & Repository Functional Tests
# =====================================================================

async def create_test_business(db, name: str = "AgentConfig Test Biz") -> Business:
    """Helper to persist a test business tenant."""
    biz = Business(
        name=name,
        slug=f"agent-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


@pytest.mark.asyncio
async def test_repository_create_default_config():
    """Verifies creating an AgentConfig with official default values."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Default Config Biz")

        config = await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
        )
        await db.commit()
        await db.refresh(config)

        assert config.business_id == biz.id
        assert config.voice_enabled is True
        assert config.chat_enabled is True
        assert config.lead_enabled is True
        assert config.voice_id is None
        assert config.tone == "helpful"
        assert config.greeting is None
        assert config.language_priority == ["en", "ur"]
        assert config.created_at is not None
        assert config.updated_at is not None


@pytest.mark.asyncio
async def test_repository_create_custom_config():
    """Verifies creating an AgentConfig with custom specified values."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Custom Config Biz")

        config = await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            voice_enabled=False,
            chat_enabled=True,
            lead_enabled=False,
            voice_id="custom-voice-123",
            tone="professional",
            greeting="Welcome to our clinic! How can we assist you?",
            language_priority=["ur", "en"],
        )
        await db.commit()
        await db.refresh(config)

        assert config.business_id == biz.id
        assert config.voice_enabled is False
        assert config.chat_enabled is True
        assert config.lead_enabled is False
        assert config.voice_id == "custom-voice-123"
        assert config.tone == "professional"
        assert config.greeting == "Welcome to our clinic! How can we assist you?"
        assert config.language_priority == ["ur", "en"]


@pytest.mark.asyncio
async def test_repository_get_by_business_id():
    """Verifies fetching an existing AgentConfig strictly by business_id."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Get Config Biz")
        await agent_config_repository.create_default(db, biz.id, tone="friendly")
        await db.commit()

        fetched = await agent_config_repository.get_by_business_id(db, biz.id)
        assert fetched is not None
        assert fetched.business_id == biz.id
        assert fetched.tone == "friendly"

        # Non-existent business returns None
        non_existent = await agent_config_repository.get_by_business_id(db, uuid.uuid4())
        assert non_existent is None


@pytest.mark.asyncio
async def test_repository_get_or_create_default_idempotence():
    """Verifies get_or_create_default creates when absent and returns existing when present."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Get or Create Biz")

        # 1. When absent, it creates default
        config1 = await agent_config_repository.get_or_create_default(db, biz.id)
        await db.commit()
        assert config1.business_id == biz.id
        assert config1.tone == "helpful"

        # 2. Update a field
        await agent_config_repository.update(db, biz.id, tone="professional")
        await db.commit()

        # 3. Calling get_or_create_default again retrieves the existing updated record
        config2 = await agent_config_repository.get_or_create_default(db, biz.id)
        assert config2.business_id == biz.id
        assert config2.tone == "professional"


@pytest.mark.asyncio
async def test_repository_update_fields():
    """Verifies updating various configuration fields with whitespace normalization."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Update Config Biz")
        await agent_config_repository.create_default(db, biz.id)
        await db.commit()

        updated = await agent_config_repository.update(
            db=db,
            business_id=biz.id,
            chat_enabled=False,
            voice_enabled=True,
            lead_enabled=False,
            tone="  friendly  ",
            greeting="  Hello and welcome!  ",
            language_priority=["ur", "en", "ar"],
        )
        await db.commit()
        await db.refresh(updated)

        assert updated.chat_enabled is False
        assert updated.voice_enabled is True
        assert updated.lead_enabled is False
        assert updated.tone == "friendly"
        assert updated.greeting == "Hello and welcome!"
        assert updated.language_priority == ["ur", "en", "ar"]


@pytest.mark.asyncio
async def test_repository_update_non_existent_returns_none():
    """Verifies update returns None when the business_id has no config."""
    async with async_session_factory() as db:
        res = await agent_config_repository.update(db, uuid.uuid4(), tone="friendly")
        assert res is None


@pytest.mark.asyncio
async def test_jsonb_language_priority_mutation_and_retrieval():
    """Verifies that language_priority JSONB stores complex lists correctly."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "JSONB Priority Biz")
        custom_priority = ["ur", "en", "ps", "pa"]
        await agent_config_repository.create_default(
            db, biz.id, language_priority=custom_priority
        )
        await db.commit()

        fetched = await agent_config_repository.get_by_business_id(db, biz.id)
        assert fetched.language_priority == custom_priority
        assert isinstance(fetched.language_priority, list)


@pytest.mark.asyncio
async def test_tenant_isolation_between_businesses():
    """Verifies that Business A and Business B configurations are strictly isolated."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, "Tenant Biz A")
        biz_b = await create_test_business(db, "Tenant Biz B")

        # Business A config
        await agent_config_repository.create_default(
            db=db,
            business_id=biz_a.id,
            tone="professional",
            chat_enabled=True,
            greeting="Greeting from Tenant A",
        )

        # Business B config
        await agent_config_repository.create_default(
            db=db,
            business_id=biz_b.id,
            tone="friendly",
            chat_enabled=False,
            greeting="Greeting from Tenant B",
        )
        await db.commit()

        # Querying with Business A ID returns Business A data only
        fetch_a = await agent_config_repository.get_by_business_id(db, biz_a.id)
        assert fetch_a.business_id == biz_a.id
        assert fetch_a.tone == "professional"
        assert fetch_a.chat_enabled is True
        assert fetch_a.greeting == "Greeting from Tenant A"

        # Querying with Business B ID returns Business B data only
        fetch_b = await agent_config_repository.get_by_business_id(db, biz_b.id)
        assert fetch_b.business_id == biz_b.id
        assert fetch_b.tone == "friendly"
        assert fetch_b.chat_enabled is False
        assert fetch_b.greeting == "Greeting from Tenant B"

        # Updating Business A does NOT alter Business B
        await agent_config_repository.update(db, biz_a.id, tone="casual", chat_enabled=False)
        await db.commit()

        fetch_b_after = await agent_config_repository.get_by_business_id(db, biz_b.id)
        assert fetch_b_after.tone == "friendly"
        assert fetch_b_after.chat_enabled is False


@pytest.mark.asyncio
async def test_cascade_deletion_on_business_removal():
    """Verifies that deleting a Business cascades and removes its AgentConfig."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, "Cascade Test Biz")
        await agent_config_repository.create_default(db, biz.id)
        await db.commit()

        # Verify config exists
        assert (await agent_config_repository.get_by_business_id(db, biz.id)) is not None

        # Delete the Business directly
        await db.delete(biz)
        await db.commit()

        # Config should be automatically deleted via foreign key ON DELETE CASCADE
        assert (await agent_config_repository.get_by_business_id(db, biz.id)) is None

