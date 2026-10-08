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

__all__ = [
    "Base",
    "User",
    "Business",
    "BusinessMember",
    "MemberRole",
]
