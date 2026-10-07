"""AgentDesk FastAPI Application Entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.database import close_database
from app.core.redis import close_redis
from app.core.logging import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for startup and shutdown procedures."""
    logger.info(f"Starting {settings.APP_NAME} backend in {settings.ENVIRONMENT} mode...")
    yield
    logger.info(f"Shutting down {settings.APP_NAME} backend...")
    await close_database()
    await close_redis()
    logger.info("Resources released successfully.")


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="Multi-Agent AI Platform for Small Businesses — Backend API",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root level health router (/health) for infrastructure & platform probes
app.include_router(health_router)

# Versioned API routes (/api/v1/...)
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)



@app.get("/", tags=["Root"])
async def root():
    """Root endpoint providing service metadata."""
    return {
        "app": settings.APP_NAME,
        "description": "Multi-Agent AI Platform for Small Businesses",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs" if settings.DEBUG else None,
        "health_url": "/health",
    }
