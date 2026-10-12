"""AgentDesk Redis Connection and Client Utilities."""

import asyncio
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

# Store clients keyed by running event loop id to ensure event loop safety across async tasks and tests
_redis_clients: Dict[int, aioredis.Redis] = {}


def get_redis_client() -> aioredis.Redis:
    """Returns the Redis client instance associated with the active event loop."""
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        loop_id = 0

    if loop_id not in _redis_clients:
        _redis_clients[loop_id] = aioredis.from_url(
            settings.redis_connection_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
    return _redis_clients[loop_id]


async def check_redis_health() -> Dict[str, Any]:
    """Checks Redis connectivity and returns health dict."""
    try:
        client = get_redis_client()
        pong = await client.ping()
        if pong:
            return {"status": "healthy"}
        return {"status": "unhealthy", "error": "Ping failed"}
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def close_redis() -> None:
    """Closes all Redis client connections."""
    for client in list(_redis_clients.values()):
        try:
            await client.close()
        except Exception:
            pass
    _redis_clients.clear()
