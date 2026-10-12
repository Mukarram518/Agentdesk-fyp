"""AgentDesk Schemas Package."""

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    AuthResponse,
    LogoutResponse,
    GoogleAuthUrlResponse,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "UserResponse",
    "AuthResponse",
    "LogoutResponse",
    "GoogleAuthUrlResponse",
]
