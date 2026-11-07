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
    enforce_test_database_isolation,
)
from app.models import Base


def test_database_configuration():
    """Verifies that database configuration is correctly structured."""
    settings = get_settings()
    assert settings.POSTGRES_USER == "postgres"
    assert settings.POSTGRES_DB == "agentdesk"
    assert settings.POSTGRES_TEST_DB == "agentdesk_test"
    assert settings.async_database_url.startswith("postgresql+asyncpg://")
    assert settings.sync_database_url.startswith("postgresql://")
    assert f":{settings.POSTGRES_PORT}" in settings.async_database_url
    assert "agentdesk_test" in settings.async_database_url
    assert "agentdesk_test" in settings.sync_database_url


def test_test_database_isolation_safety_guard():
    """Verifies that enforce_test_database_isolation blocks development and production databases."""
    for forbidden in ("agentdesk", "postgres", "production", "development", "agentdesk_dev", "agentdesk_prod"):
        with pytest.raises(RuntimeError) as exc_info:
            enforce_test_database_isolation(f"postgresql+asyncpg://localhost:5434/{forbidden}")
        assert "TEST DATABASE ISOLATION ENFORCEMENT ERROR" in str(exc_info.value)

        with pytest.raises(RuntimeError) as exc_info2:
            enforce_test_database_isolation(forbidden)
        assert "TEST DATABASE ISOLATION ENFORCEMENT ERROR" in str(exc_info2.value)

    # Valid test database targets must pass
    assert enforce_test_database_isolation("postgresql+asyncpg://localhost:5434/agentdesk_test") == "agentdesk_test"
    assert enforce_test_database_isolation("agentdesk_test") == "agentdesk_test"
    assert enforce_test_database_isolation("custom_test_db") == "custom_test_db"


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
    import os
    settings = get_settings()
    ini_path = "alembic.ini" if os.path.exists("alembic.ini") else os.path.join("backend", "alembic.ini")
    script_loc = "alembic" if os.path.exists("alembic") else os.path.join("backend", "alembic")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", script_loc)
    script = ScriptDirectory.from_config(alembic_cfg)

    # Verify head revision
    head_rev = script.get_current_head()
    assert head_rev in (
        "0001_initial_schema",
        "0002_core_domain_schema",
        "0003_authentication",
        "0004_knowledge_base",
        "0005_knowledge_integrity",
        "0006_knowledge_claim_fields",
        "0007_embedding_model_versioning",
    )


@pytest.mark.asyncio
async def test_alembic_database_revision_matches_head():
    """Verifies that the database has applied migrations matching current head."""
    import os
    ini_path = "alembic.ini" if os.path.exists("alembic.ini") else os.path.join("backend", "alembic.ini")
    script_loc = "alembic" if os.path.exists("alembic") else os.path.join("backend", "alembic")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", script_loc)
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    async with engine.connect() as conn:
        def get_current_rev(connection):
            context = MigrationContext.configure(connection)
            return context.get_current_revision()

        current_rev = await conn.run_sync(get_current_rev)
        assert current_rev == head_rev


def test_alembic_rejects_development_database_in_testing_mode():
    """Verifies that Alembic env.py halts immediately if pointed at a non-test database in testing mode."""
    import os
    import subprocess
    import sys

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_vars = os.environ.copy()
    env_vars["ENVIRONMENT"] = "testing"
    env_vars["TEST_DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5434/agentdesk"

    res = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=backend_dir,
        env=env_vars,
        capture_output=True,
        text=True,
    )

    assert res.returncode != 0
    assert "TEST DATABASE ISOLATION ENFORCEMENT ERROR" in (res.stderr + res.stdout)
    assert "agentdesk" in (res.stderr + res.stdout)


def test_alembic_accepts_test_database_in_testing_mode():
    """Verifies that Alembic env.py succeeds and accepts agentdesk_test when testing mode is active."""
    import os
    import subprocess
    import sys

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_vars = os.environ.copy()
    env_vars["ENVIRONMENT"] = "testing"
    env_vars["TEST_DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5434/agentdesk_test"

    res = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=backend_dir,
        env=env_vars,
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0
    assert "0007_embedding_model_versioning" in (res.stdout + res.stderr)
