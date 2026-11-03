"""Pydantic schemas for Knowledge Base FAQs, updates, responses, and semantic search."""

from datetime import datetime
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator

from app.models.knowledge import KnowledgeLanguage, KnowledgeBaseEntry

VALID_LANGUAGES = frozenset({l.value for l in KnowledgeLanguage})


class FAQCreate(BaseModel):
    """Payload for creating a new FAQ entry."""

    question: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional FAQ question",
        examples=["What are your business hours?"],
    )
    answer: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Knowledge answer content to be embedded and retrieved",
        examples=["We are open Monday to Saturday from 9 AM to 8 PM."],
    )
    tags: Optional[List[str]] = Field(
        default_factory=list,
        description="Categorization tags",
        examples=[["hours", "timing"]],
    )
    language: str = Field(
        default=KnowledgeLanguage.EN.value,
        description="Content language ('en', 'ur', 'mixed')",
        examples=["en"],
    )

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, v: str) -> str:
        """Trims whitespace and ensures answer is not empty."""
        if not v or not v.strip():
            raise ValueError("Answer cannot be empty or whitespace-only.")
        return v.strip()

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: Optional[str]) -> Optional[str]:
        """Normalizes optional question string."""
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validates that language is supported."""
        cleaned = v.strip().lower() if v else ""
        if cleaned not in VALID_LANGUAGES:
            raise ValueError(
                f"Invalid language '{v}'. Supported languages are: {sorted(VALID_LANGUAGES)}."
            )
        return cleaned

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> List[str]:
        """Normalizes tags as list of stripped strings."""
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("Tags must be a list of strings.")
        return [str(t).strip() for t in v if str(t).strip()]


class FAQUpdate(BaseModel):
    """Payload for updating an existing FAQ entry."""

    question: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated FAQ question (set to null or non-empty string)",
    )
    answer: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10000,
        description="Updated knowledge answer content",
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Updated categorization tags",
    )
    language: Optional[str] = Field(
        None,
        description="Updated language ('en', 'ur', 'mixed')",
    )

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, v: Optional[str]) -> Optional[str]:
        """Ensures updated answer is not empty or whitespace-only if provided."""
        if v is not None:
            if not v.strip():
                raise ValueError("Answer cannot be empty or whitespace-only.")
            return v.strip()
        return None

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: Optional[str]) -> Optional[str]:
        """Normalizes optional question."""
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """Validates language if provided."""
        if v is not None:
            cleaned = v.strip().lower()
            if cleaned not in VALID_LANGUAGES:
                raise ValueError(
                    f"Invalid language '{v}'. Supported languages are: {sorted(VALID_LANGUAGES)}."
                )
            return cleaned
        return None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Normalizes tags if provided."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("Tags must be a list of strings.")
            return [str(t).strip() for t in v if str(t).strip()]
        return None


class FAQResponse(BaseModel):
    """Public representation of an FAQ entry.

    Security & Payload Guarantees:
    - Never exposes raw vector embedding arrays.
    - Exposes embedding status metadata (`has_embedding`, `embedding_stale`).
    - Strictly maps to authenticated tenant.
    """

    id: uuid.UUID
    business_id: uuid.UUID
    question: Optional[str] = None
    answer: str
    tags: List[str] = Field(default_factory=list)
    language: str
    source_type: str = "FAQ"
    has_embedding: bool = Field(
        ...,
        description="Whether a vector embedding exists for this entry",
    )
    embedding_stale: bool = Field(
        ...,
        description="Whether the vector embedding is outdated or pending regeneration",
    )
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    @classmethod
    def from_orm_entry(cls, entry: KnowledgeBaseEntry) -> "FAQResponse":
        """Factory constructing FAQResponse from an ORM KnowledgeBaseEntry."""
        return cls(
            id=entry.id,
            business_id=entry.business_id,
            question=entry.question,
            answer=entry.answer,
            tags=entry.tags if entry.tags is not None else [],
            language=entry.language,
            source_type=entry.source_type,
            has_embedding=entry.embedding is not None,
            embedding_stale=bool(entry.embedding_stale),
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


class KnowledgeSearchRequest(BaseModel):
    """Payload for executing a semantic vector search query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Semantic search query string",
        examples=["What time are you open?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum number of matches to return (1 to 100)",
        examples=[5],
    )
    score_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional maximum cosine distance threshold (0.0 is identical)",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Trims whitespace and ensures query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace-only.")
        return v.strip()


class KnowledgeSearchResultItem(BaseModel):
    """An individual semantic search result with similarity score."""

    entry: FAQResponse
    score: float = Field(
        ...,
        description="Cosine distance from query vector (0.0 = identical; lower is closer)",
    )
    score_metric: str = Field(
        default="cosine_distance",
        description="Metric used for similarity evaluation",
    )


class KnowledgeSearchResponse(BaseModel):
    """Response containing matched knowledge entries for a query."""

    query: str
    results: List[KnowledgeSearchResultItem]
    total_results: int

