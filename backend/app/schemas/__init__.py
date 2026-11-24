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
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageItem,
    ChatMessageResponse,
)
from app.schemas.agent_config import (
    AgentConfigResponse,
    AgentConfigUpdate,
    VALID_TONES,
    SUPPORTED_LANGUAGES,
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
    "ChatMessageRequest",
    "ChatMessageItem",
    "ChatMessageResponse",
    "AgentConfigResponse",
    "AgentConfigUpdate",
    "VALID_TONES",
    "SUPPORTED_LANGUAGES",
]

