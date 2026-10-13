"""AgentDesk API v1 Consolidated Router."""

from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.business import router as business_router

api_v1_router = APIRouter()

# Mount health routes under v1 (/api/v1/health)
api_v1_router.include_router(health_router)

# Mount authentication routes under v1 (/api/v1/auth)
api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Mount business routes under v1 (/api/v1/businesses)
api_v1_router.include_router(business_router, prefix="/businesses", tags=["Businesses"])

