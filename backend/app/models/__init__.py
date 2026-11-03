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
]
