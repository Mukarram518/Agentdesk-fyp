"""AgentDesk API v1 Consolidated Router."""

from fastapi import APIRouter
from app.api.health import router as health_router

api_v1_router = APIRouter()

# Mount health routes under v1 (/api/v1/health)
api_v1_router.include_router(health_router)
