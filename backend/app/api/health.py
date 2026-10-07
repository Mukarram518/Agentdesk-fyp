"""Health check endpoint for AgentDesk backend."""

from fastapi import APIRouter, status
from app.core.config import get_settings
from app.core.database import check_database_health
from app.core.redis import check_redis_health
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns backend availability status, along with PostgreSQL (pgvector) and Redis readiness.",
)
async def get_health(full: bool = True) -> HealthResponse:
    """Returns application health and infrastructure readiness status."""
    db_status = None
    redis_status = None

    if full:
        db_status = await check_database_health()
        redis_status = await check_redis_health()

    return HealthResponse(
        status="healthy",
        app=settings.APP_NAME,
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        database=db_status,
        redis=redis_status,
    )
