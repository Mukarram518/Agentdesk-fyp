"""Pytest configuration and shared test fixtures."""

import os

# Ensure testing environment variables are set before any app imports
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"

import pytest
from httpx import AsyncClient, ASGITransport
from app.core.config import get_settings

get_settings.cache_clear()

from app.main import app
from app.core.rate_limit import reset_rate_limits


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
