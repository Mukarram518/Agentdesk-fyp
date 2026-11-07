"""AgentDesk ARQ Worker Settings and Lifecycle Configuration (Phase 5.4E.3)."""

from typing import Any, Dict

from app.core.arq import get_arq_redis_settings
from app.core.database import async_session_factory, check_database_health, close_database
from app.core.logging import logger
from app.providers.embeddings import get_embedding_provider
from app.providers.storage import get_storage_provider
from app.worker.tasks import process_knowledge_file


async def startup(ctx: Dict[str, Any]) -> None:
    """Worker startup hook initializing long-lived background resources and dependencies.

    Fails explicitly if any critical runtime dependency (Database, Storage, Embedding) is unreachable.
    """
    logger.info("Initializing AgentDesk ARQ worker process...")

    # 1. Verify Database connectivity
    try:
        db_health = await check_database_health()
        if db_health.get("status") != "healthy":
            raise RuntimeError(f"Database health check failed: {db_health.get('error', 'unhealthy')}")
    except Exception as exc:
        logger.critical(f"ARQ worker startup aborted: Database connection unavailable: {exc}")
        raise RuntimeError(f"Database is unavailable for ARQ worker: {exc}") from exc

    ctx["session_factory"] = async_session_factory

    # 2. Verify Storage provider initialization
    try:
        storage = get_storage_provider()
        ctx["storage_provider"] = storage
    except Exception as exc:
        logger.critical(f"ARQ worker startup aborted: Storage provider initialization failed: {exc}")
        raise RuntimeError(f"Storage provider is unavailable for ARQ worker: {exc}") from exc

    # 3. Verify Embedding provider initialization
    try:
        embedding = get_embedding_provider()
        ctx["embedding_provider"] = embedding
    except Exception as exc:
        logger.critical(f"ARQ worker startup aborted: Embedding provider initialization failed: {exc}")
        raise RuntimeError(f"Embedding provider is unavailable for ARQ worker: {exc}") from exc

    logger.info("AgentDesk ARQ worker process initialized successfully with all dependencies.")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """Worker shutdown hook releasing shared resources."""
    logger.info("Shutting down AgentDesk ARQ worker process...")
    await close_database()
    ctx.clear()
    logger.info("ARQ worker resources released successfully.")


class WorkerSettings:
    """Configuration class for the ARQ worker process.

    Guarantees:
    - Conservative concurrency: max_jobs = 2 to avoid memory pressure.
    - Safe execution window: job_timeout = 300 seconds (5 minutes).
    - Maximum automatic retry attempts: max_tries = 3.
    - Registered functions: process_knowledge_file.
    - Uses approved application Redis connection settings.
    """

    functions = [process_knowledge_file]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = get_arq_redis_settings()
    max_jobs: int = 2
    job_timeout: int = 300
    max_tries: int = 3
