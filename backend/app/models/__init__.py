"""AgentDesk Database Models Package.

Application domain models for multi-tenant business isolation.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base."""
    pass


from app.models.user import User  # noqa: E402
from app.models.business import Business  # noqa: E402
from app.models.business_member import BusinessMember, MemberRole  # noqa: E402
from app.models.session import UserSession  # noqa: E402
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus  # noqa: E402
from app.models.knowledge import (  # noqa: E402
    KnowledgeBaseEntry,
    KnowledgeSourceType,
    KnowledgeLanguage,
    EMBEDDING_VECTOR_DIMENSION,
)
from app.models.conversation import (  # noqa: E402
    Conversation,
    ConversationChannel,
    ConversationStatus,
)
from app.models.message import (  # noqa: E402
    Message,
    MessageRole,
)
from app.models.agent_config import (  # noqa: E402
    AgentConfig,
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_TONE,
)

__all__ = [
    "Base",
    "User",
    "Business",
    "BusinessMember",
    "MemberRole",
    "UserSession",
    "KnowledgeFile",
    "KnowledgeFileStatus",
    "KnowledgeBaseEntry",
    "KnowledgeSourceType",
    "KnowledgeLanguage",
    "EMBEDDING_VECTOR_DIMENSION",
    "Conversation",
    "ConversationChannel",
    "ConversationStatus",
    "Message",
    "MessageRole",
    "AgentConfig",
    "DEFAULT_LANGUAGE_PRIORITY",
    "DEFAULT_TONE",
]
