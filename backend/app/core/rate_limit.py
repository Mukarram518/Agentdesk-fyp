"""Rate limiting protection for authentication endpoints."""

import time
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status
from app.core.config import get_settings
from app.core.logging import logger
from app.core.redis import get_redis_client

settings = get_settings()

# In-memory sliding window cache for fallback or testing
_IN_MEMORY_RATE_LIMITS: Dict[str, List[float]] = {}


async def reset_rate_limits() -> None:
    """Clears in-memory and Redis rate limits (primarily for testing)."""
    _IN_MEMORY_RATE_LIMITS.clear()
    try:
        redis_client = get_redis_client()
        if redis_client:
            keys = await redis_client.keys("rate_limit:*")
            if keys:
                await redis_client.delete(*keys)
    except Exception:
        pass


async def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int = 60,
) -> None:
    """Checks rate limit for a given key.

    Uses Redis if available; falls back to an in-memory sliding window.
    Raises HTTPException 429 if the limit is exceeded.
    """
    now = time.time()
    redis_client = get_redis_client()

    if redis_client:
        try:
            redis_key = f"rate_limit:{key}"
            current_count = await redis_client.incr(redis_key)
            if current_count == 1:
                await redis_client.expire(redis_key, window_seconds)
            if current_count > max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please try again later.",
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Redis rate limiter failed, falling back to memory: {e}")

    # In-memory fallback
    timestamps = _IN_MEMORY_RATE_LIMITS.get(key, [])
    cutoff = now - window_seconds
    # Prune outdated timestamps
    valid_timestamps = [t for t in timestamps if t > cutoff]

    if len(valid_timestamps) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )

    valid_timestamps.append(now)
    _IN_MEMORY_RATE_LIMITS[key] = valid_timestamps


def get_client_ip(request: Request) -> str:
    """Extracts client IP safely considering proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def rate_limit_login(request: Request) -> None:
    """Rate limit dependency for login endpoint."""
    ip = get_client_ip(request)
    await check_rate_limit(
        f"login:{ip}",
        max_requests=settings.AUTH_RATE_LIMIT_LOGIN,
        window_seconds=60,
    )


async def rate_limit_register(request: Request) -> None:
    """Rate limit dependency for register endpoint."""
    ip = get_client_ip(request)
    await check_rate_limit(
        f"register:{ip}",
        max_requests=settings.AUTH_RATE_LIMIT_REGISTER,
        window_seconds=60,
    )
