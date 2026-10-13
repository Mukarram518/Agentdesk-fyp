"""Pydantic schemas for business entities and onboarding."""

import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class BusinessCreate(BaseModel):
    """Payload for creating a new business during onboarding."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Business display name",
        examples=["Acme Dental Care"],
    )
    slug: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Optional custom URL-friendly identifier",
        examples=["acme-dental-care"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Trims whitespace and ensures name is not empty."""
        if not v or not v.strip():
            raise ValueError("Business name cannot be empty.")
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Business name must be at least 2 characters.")
        if len(cleaned) > 255:
            raise ValueError("Business name cannot exceed 255 characters.")
        return cleaned

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        """Normalizes and validates user-supplied slug if provided."""
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not cleaned:
            return None
        if len(cleaned) < 2:
            raise ValueError("Business slug must be at least 2 characters.")
        if len(cleaned) > 100:
            raise ValueError("Business slug cannot exceed 100 characters.")
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", cleaned):
            raise ValueError(
                "Business slug must contain only lowercase alphanumeric characters and hyphens."
            )
        return cleaned


# Backward-compatible alias matching project request conventions
BusinessCreateRequest = BusinessCreate


class BusinessResponse(BaseModel):
    """Public business representation returned to authenticated users."""

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool = True
    role: Optional[str] = Field(
        None,
        description="The authenticated user's role in this business ('owner', 'admin', 'member')",
    )
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    @classmethod
    def from_orm_business(
        cls, business, role: Optional[str] = None
    ) -> "BusinessResponse":
        """Factory method constructing BusinessResponse from an ORM Business model."""
        return cls(
            id=business.id,
            name=business.name,
            slug=business.slug,
            is_active=business.is_active,
            role=role,
            created_at=business.created_at,
            updated_at=business.updated_at,
        )
