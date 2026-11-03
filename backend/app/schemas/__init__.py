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
from app.schemas.knowledge import (
    FAQCreate,
    FAQUpdate,
    FAQResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResultItem,
    KnowledgeSearchResponse,
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
    "FAQCreate",
    "FAQUpdate",
    "FAQResponse",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResultItem",
    "KnowledgeSearchResponse",
]

