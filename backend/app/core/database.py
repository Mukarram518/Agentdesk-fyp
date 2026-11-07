"""AgentDesk Database Core (SQLAlchemy 2.x & Asyncpg)."""

import os
from typing import AsyncGenerator, Dict, Any
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

FORBIDDEN_TEST_DATABASES = frozenset({
    "agentdesk",
    "postgres",
    "production",
    "agentdesk_dev",
    "agentdesk_prod",
    "development",
})


def enforce_test_database_isolation(target: str) -> str:
    """
    Validates that a database URL or database name targets an isolated test database.
    Raises RuntimeError if it points to a production or development database.
    """
    if "://" in target:
        parsed = urlparse(target)
        db_name = parsed.path.lstrip("/").lower()
    else:
        db_name = target.strip().lower()

    if db_name in FORBIDDEN_TEST_DATABASES or ("test" not in db_name):
        raise RuntimeError(
            f"TEST DATABASE ISOLATION ENFORCEMENT ERROR: Tests are strictly forbidden from connecting "
            f"to database '{db_name}'. "
            f"Expected dedicated test database (e.g. 'agentdesk_test'). "
            f"Refusing to connect to protect development/production data."
        )
    return db_name


# Use NullPool during testing to avoid cross-event-loop connection reuse issues with asyncpg
is_testing = os.getenv("ENVIRONMENT") == "testing" or settings.ENVIRONMENT == "testing"
pool_class = NullPool if is_testing else AsyncAdaptedQueuePool

if is_testing:
    enforce_test_database_isolation(settings.async_database_url)

engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG and settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,
    poolclass=pool_class,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an asynchronous database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def verify_pgvector_available() -> bool:
    """Verifies that the vector extension is available in PostgreSQL."""
    try:
        async with engine.connect() as conn:
            res = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            return res.first() is not None
    except Exception as e:
        logger.warning(f"Error checking pgvector availability: {e}")
        return False


async def check_database_health() -> Dict[str, Any]:
    """
    Checks PostgreSQL connectivity and verifies pgvector extension status.
    Returns a health status dict.
    """
    try:
        async with engine.connect() as conn:
            # Check basic query execution
            await conn.execute(text("SELECT 1"))

            # Check if pgvector extension is present
            res = await conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
            )
            row = res.first()
            if row:
                return {
                    "status": "healthy",
                    "pgvector": f"enabled (v{row[1]})",
                }
            return {
                "status": "healthy",
                "pgvector": "not_installed",
            }
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def close_database() -> None:
    """Closes all database engine connections."""
    await engine.dispose()
