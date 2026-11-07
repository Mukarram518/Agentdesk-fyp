"""Unit tests for AgentDesk ARQ Worker Foundation (Phase 5.4E.1).

Verifies:
1. ARQ RedisSettings extraction from application configuration.
2. create_arq_pool and close_arq_pool lifecycle.
3. close_arq_pool graceful error handling and None safety.
4. WorkerSettings default configuration (max_jobs=2, job_timeout=300).
5. Worker lifecycle hooks (startup and shutdown).
6. FastAPI lifespan integration for app.state.arq_pool.
7. Preservation of existing app.core.redis functionality.
"""

from unittest.mock import AsyncMock, patch
import pytest
from arq.connections import ArqRedis, RedisSettings
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.arq import close_arq_pool, create_arq_pool, get_arq_redis_settings
from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.main import app
from app.worker.settings import WorkerSettings, shutdown, startup
from app.worker.tasks import process_knowledge_file


def test_arq_redis_settings_configuration():
    """Verifies that get_arq_redis_settings builds RedisSettings from app configuration."""
    settings = get_settings()
    redis_settings = get_arq_redis_settings()

    assert isinstance(redis_settings, RedisSettings)
    assert redis_settings.host == settings.REDIS_HOST
    assert redis_settings.port == settings.REDIS_PORT
    assert redis_settings.database == 0


@pytest.mark.asyncio
async def test_create_and_close_arq_pool_with_mock():
    """Verifies that create_arq_pool and close_arq_pool invoke underlying pool methods."""
    mock_pool = AsyncMock(spec=ArqRedis)

    with patch("app.core.arq.create_pool", return_value=mock_pool) as mock_create:
        pool = await create_arq_pool()
        assert pool == mock_pool
        mock_create.assert_awaited_once()

    await close_arq_pool(mock_pool)
    mock_pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_arq_pool_handles_none_and_exceptions():
    """Verifies that close_arq_pool is safe against None and suppresses exceptions."""
    # Should not raise for None
    await close_arq_pool(None)

    # Should catch and suppress exceptions from pool.close()
    failing_pool = AsyncMock(spec=ArqRedis)
    failing_pool.close.side_effect = RuntimeError("Connection already closed")
    await close_arq_pool(failing_pool)
    failing_pool.close.assert_awaited_once()


def test_worker_settings_defaults():
    """Verifies conservative default settings for the ARQ worker process."""
    settings = get_settings()

    assert WorkerSettings.max_jobs == 2
    assert WorkerSettings.job_timeout == 300
    assert WorkerSettings.functions == [process_knowledge_file]
    assert WorkerSettings.redis_settings.host == settings.REDIS_HOST
    assert WorkerSettings.redis_settings.port == settings.REDIS_PORT
    assert WorkerSettings.on_startup == startup
    assert WorkerSettings.on_shutdown == shutdown


@pytest.mark.asyncio
async def test_worker_lifecycle_hooks():
    """Verifies that worker startup and shutdown hooks execute cleanly."""
    ctx = {}
    await startup(ctx)
    await shutdown(ctx)


def test_fastapi_lifespan_arq_pool_lifecycle():
    """Verifies that FastAPI lifespan initializes and closes app.state.arq_pool."""
    mock_pool = AsyncMock(spec=ArqRedis)

    with patch("app.main.create_arq_pool", new_callable=AsyncMock) as mock_create, \
         patch("app.main.close_arq_pool", new_callable=AsyncMock) as mock_close, \
         patch("app.main.close_database", new_callable=AsyncMock), \
         patch("app.main.close_redis", new_callable=AsyncMock):

        mock_create.return_value = mock_pool

        with TestClient(app) as client:
            # During active client context, lifespan has run startup
            assert app.state.arq_pool == mock_pool
            mock_create.assert_awaited_once()
            res = client.get("/health")
            assert res.status_code == 200

        # After exiting context, lifespan has run shutdown
        mock_close.assert_awaited_once_with(mock_pool)


def test_existing_redis_client_remains_functional():
    """Confirms that app.core.redis.get_redis_client() remains fully operational."""
    settings = get_settings()
    client = get_redis_client()
    assert client is not None
    # Verify client connection kwargs correspond to application settings
    conn_kwargs = client.connection_pool.connection_kwargs
    assert conn_kwargs.get("host") == settings.REDIS_HOST
    assert conn_kwargs.get("port") == settings.REDIS_PORT

