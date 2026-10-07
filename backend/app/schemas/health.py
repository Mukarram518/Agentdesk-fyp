"""Health Check Response Schemas."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for health endpoint response."""

    status: str = Field(default="healthy", description="Overall service status")
    app: str = Field(default="AgentDesk", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Current running environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check",
    )
    database: Optional[Dict[str, Any]] = Field(
        default=None, description="Database and pgvector status"
    )
    redis: Optional[Dict[str, Any]] = Field(
        default=None, description="Redis connectivity status"
    )
