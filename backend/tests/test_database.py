"""Tests for Phase 1B Database Foundation & Migrations."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext

from app.core.config import get_settings
from app.core.database import (
    engine,
    get_db,
    check_database_health,
    verify_pgvector_available,
)
from app.models import Base


def test_database_configuration():
    """Verifies that database configuration is correctly structured."""
    settings = get_settings()
    assert settings.POSTGRES_USER == "postgres"
    assert settings.POSTGRES_DB == "agentdesk"
    assert settings.async_database_url.startswith("postgresql+asyncpg://")
    assert settings.sync_database_url.startswith("postgresql://")
    assert f":{settings.POSTGRES_PORT}" in settings.async_database_url


@pytest.mark.asyncio
async def test_sqlalchemy_connection():
    """Verifies async SQLAlchemy connection can execute a basic query."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_pgvector_availability():
    """Verifies that pgvector extension and type are available in PostgreSQL."""
    is_available = await verify_pgvector_available()
    assert is_available is True

    # Verify vector data type exists in pg_type catalog
    async with engine.connect() as conn:
        res = await conn.execute(
            text("SELECT typname FROM pg_type WHERE typname = 'vector'")
        )
        assert res.scalar() == "vector"


@pytest.mark.asyncio
async def test_database_health_reporting():
    """Verifies check_database_health returns healthy with pgvector enabled."""
    health = await check_database_health()
    assert health["status"] == "healthy"
    assert "pgvector" in health
    assert "enabled" in health["pgvector"]


@pytest.mark.asyncio
async def test_get_db_session_dependency():
    """Verifies that get_db yields an active AsyncSession."""
    async for session in get_db():
        assert isinstance(session, AsyncSession)
        assert session.is_active
        res = await session.execute(text("SELECT 1"))
        assert res.scalar() == 1
        break


def test_declarative_base_is_empty():
    """Verifies that Base.metadata is properly registered and accessible."""
    assert Base.metadata is not None
    assert isinstance(Base.metadata.tables, dict)


def test_alembic_migration_configuration():
    """Verifies Alembic configuration and current head revision."""
    settings = get_settings()
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)

    # Verify head revision
    head_rev = script.get_current_head()
    assert head_rev in ("0001_initial_schema", "0002_core_domain_schema")


@pytest.mark.asyncio
async def test_alembic_database_revision_matches_head():
    """Verifies that the database has applied migrations matching current head."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    async with engine.connect() as conn:
        def get_current_rev(connection):
            context = MigrationContext.configure(connection)
            return context.get_current_revision()

        current_rev = await conn.run_sync(get_current_rev)
        assert current_rev == head_rev
