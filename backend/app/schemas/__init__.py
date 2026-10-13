"""AgentDesk Schemas Package."""

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    AuthResponse,
    LogoutResponse,
    GoogleAuthUrlResponse,
)
from app.schemas.business import (
    BusinessCreate,
    BusinessCreateRequest,
    BusinessResponse,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "UserResponse",
    "AuthResponse",
    "LogoutResponse",
    "GoogleAuthUrlResponse",
    "BusinessCreate",
    "BusinessCreateRequest",
    "BusinessResponse",
]

