"""AgentDesk Database Models Package.

Application models are introduced in Phase 2 (Authentication) and subsequent phases
according to the approved AgentDesk development roadmap.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base."""
    pass
