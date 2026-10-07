"""Tests for FastAPI Health Check and Root Endpoints."""

import pytest
from httpx import AsyncClient
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_health_endpoint_basic(async_client: AsyncClient):
    """Verifies that GET /health returns 200 OK and expected structure."""
    response = await async_client.get("/health?full=false")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "AgentDesk"
    assert data["version"] == "0.1.0"
    assert "environment" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_endpoint_api_prefix(async_client: AsyncClient):
    """Verifies that GET /api/v1/health is also reachable and returns 200."""
    response = await async_client.get("/api/v1/health?full=false")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "AgentDesk"


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verifies that GET / returns service information."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "AgentDesk"
    assert data["status"] == "online"
    assert data["health_url"] == "/health"


def test_settings_load():
    """Verifies settings object loads with expected defaults."""
    settings = get_settings()
    assert settings.APP_NAME == "AgentDesk"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert isinstance(settings.CORS_ORIGINS, list)


@pytest.mark.asyncio
async def test_health_endpoint_full(async_client: AsyncClient):
    """Verifies that GET /health returns full database and redis status."""
    response = await async_client.get("/health?full=true")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] is not None
    assert data["database"]["status"] == "healthy"
    assert "pgvector" in data["database"]
    assert data["redis"] is not None
    assert data["redis"]["status"] == "healthy"

