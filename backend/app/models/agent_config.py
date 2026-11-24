"""AgentConfig domain model representing tenant agent configurations."""

import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.business import Business


DEFAULT_LANGUAGE_PRIORITY: List[str] = ["en", "ur"]
DEFAULT_TONE: str = "helpful"


class AgentConfig(Base):
    """Agent configuration entity for a business tenant.

    One-to-one relationship with Business where business_id is both
    the primary key and foreign key referencing businesses.id.
    """

    __tablename__ = "agent_configs"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    voice_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=func.true(),
        nullable=False,
    )
    chat_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=func.true(),
        nullable=False,
    )
    lead_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=func.true(),
        nullable=False,
    )
    voice_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    tone: Mapped[str] = mapped_column(
        String(50),
        default=DEFAULT_TONE,
        server_default=text(f"'{DEFAULT_TONE}'"),
        nullable=False,
    )
    greeting: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    language_priority: Mapped[List[str]] = mapped_column(
        JSONB,
        default=lambda: list(DEFAULT_LANGUAGE_PRIORITY),
        server_default=text("'[\"en\", \"ur\"]'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # One-to-one relationship to Business
    business: Mapped["Business"] = relationship(
        "Business",
        back_populates="agent_config",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentConfig business_id={self.business_id} "
            f"chat_enabled={self.chat_enabled} "
            f"lead_enabled={self.lead_enabled} "
            f"voice_enabled={self.voice_enabled} "
            f"tone='{self.tone}'>"
        )

