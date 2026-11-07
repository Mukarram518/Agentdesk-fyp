"""AgentDesk ARQ Redis connection pool and client utilities."""

from typing import Optional
from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()


def get_arq_redis_settings() -> RedisSettings:
    """Creates ARQ RedisSettings from application configuration.

    Guarantees:
    - Reuses settings.redis_connection_url.
    - Zero hardcoded credentials or hostnames.
    - Uses RedisSettings.from_dsn() for robust connection configuration.
    """
    return RedisSettings.from_dsn(settings.redis_connection_url)


async def create_arq_pool() -> ArqRedis:
    """Initializes and returns an asynchronous ARQ Redis client connection pool."""
    redis_settings = get_arq_redis_settings()
    return await create_pool(redis_settings)


async def close_arq_pool(pool: Optional[ArqRedis]) -> None:
    """Gracefully closes the ARQ Redis connection pool if initialized."""
    if pool is not None:
        try:
            await pool.close()
        except Exception as exc:
            logger.warning(f"Error closing ARQ Redis pool: {exc}")

