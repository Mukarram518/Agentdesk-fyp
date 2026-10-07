"""AgentDesk Redis Connection and Client Utilities."""

from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    """Returns the global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_connection_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
    return _redis_client


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
    """Closes Redis client connections."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
