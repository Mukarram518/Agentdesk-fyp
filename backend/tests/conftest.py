"""Pytest configuration and shared test fixtures."""

import os

# Ensure testing environment variables are set before any app imports
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ.setdefault("POSTGRES_TEST_DB", "agentdesk_test")

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.core.config import get_settings

get_settings.cache_clear()

from app.core.database import engine, enforce_test_database_isolation
from app.main import app
from app.core.rate_limit import reset_rate_limits


@pytest.fixture(scope="session", autouse=True)
async def verify_test_database_isolation():
    """
    Enforce strict test database isolation across the entire test suite.
    Fails immediately before any test executes if the target database is not a dedicated test database.
    Verifies both configuration URL and the active server-side database name.
    """
    settings = get_settings()
    enforce_test_database_isolation(settings.async_database_url)

    # Server-side verification: query PostgreSQL directly
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT current_database()"))
        current_db = res.scalar()
        enforce_test_database_isolation(current_db)
        assert "test" in current_db, f"Active database '{current_db}' is not a test database"

    yield


@pytest.fixture(autouse=True)
async def auto_reset_rate_limits():
    """Ensures each test starts with clean rate limits."""
    await reset_rate_limits()
    yield
    await reset_rate_limits()


@pytest.fixture
async def async_client():
    """Provides an AsyncClient for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
