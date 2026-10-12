"""Pydantic schemas for authentication and user accounts."""

import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for registering a new user account."""

    email: EmailStr = Field(..., description="Valid user email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name of user")


class LoginRequest(BaseModel):
    """Payload for user email and password authentication."""

    email: EmailStr = Field(..., description="Registered user email address")
    password: str = Field(..., min_length=1, max_length=128, description="User password")


class UserResponse(BaseModel):
    """Public user account details returned in API responses."""

    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    verified: bool = Field(default=False)
    is_active: bool = True

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    @classmethod
    def from_orm_user(cls, user) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            verified=getattr(user, "is_verified", False),
            is_active=user.is_active,
        )


class AuthResponse(BaseModel):
    """Response returned upon successful registration or login."""

    user: UserResponse


class LogoutResponse(BaseModel):
    """Response returned upon successful logout."""

    success: bool = True


class GoogleAuthUrlResponse(BaseModel):
    """Response containing Google OAuth authorization redirection URL."""

    authorization_url: str
