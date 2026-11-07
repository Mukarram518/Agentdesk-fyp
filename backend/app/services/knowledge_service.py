"""Knowledge service coordinating FAQ management, vector embeddings, and semantic search."""

import asyncio
from dataclasses import dataclass
import logging
import math
import uuid
from typing import Any, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.knowledge import (
    ACTIVE_EMBEDDING_MODEL,
    EMBEDDING_VECTOR_DIMENSION,
    KnowledgeBaseEntry,
    KnowledgeSourceType,
    KnowledgeLanguage,
)
from app.providers.embeddings import (
    EmbeddingProvider,
    PREFIX_PASSAGE,
    PREFIX_QUERY,
    get_embedding_provider,
)
from app.repositories.knowledge_repository import (
    KnowledgeRepository,
    knowledge_repository,
)

_UNSET = object()


@dataclass(frozen=True)
class ReembedBatchResult:
    """Outcome summary for an FAQ re-embedding batch."""

    scanned: int
    reembedded: int
    failed: int
    remaining: int
    dry_run: bool
    entry_ids: List[uuid.UUID]


class KnowledgeService:
    """Service encapsulating FAQ lifecycle, vector embedding generation, and semantic retrieval."""

    def __init__(
        self,
        knowledge_repo: KnowledgeRepository = knowledge_repository,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.knowledge_repo = knowledge_repo
        self._embedding_provider = embedding_provider

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        """Returns the configured embedding provider, lazily resolving from factory if not injected."""
        if self._embedding_provider is None:
            self._embedding_provider = get_embedding_provider()
        return self._embedding_provider

    async def create_faq(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        question: Optional[str] = None,
        answer: str = "",
        tags: Optional[List[str]] = None,
        language: str = KnowledgeLanguage.EN.value,
    ) -> KnowledgeBaseEntry:
        """Creates an FAQ entry and generates its vector embedding from the answer text.

        Guarantees:
        - Validates that business_id is a valid UUID.
        - Validates that answer is non-empty.
        - Question is optional according to the database model.
        - Validates language against approved KnowledgeLanguage values.
        - Attempts to generate 384-dimensional embedding vector from answer text.
        - Graceful fallback: If embedding generation fails, saves entry with embedding=None
          and embedding_stale=True, logging the failure without raising an exception.
        - Strictly flushes without committing (leaving transaction commit to get_db dependency).
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("Valid business_id is required.")

        if answer is None or not isinstance(answer, str) or not answer.strip():
            raise ValueError("Answer cannot be empty or whitespace-only.")
        cleaned_answer = answer.strip()

        cleaned_question: Optional[str] = None
        if question is not None:
            if not isinstance(question, str):
                raise ValueError("Question must be a string if provided.")
            if question.strip():
                cleaned_question = question.strip()

        supported_languages = {l.value for l in KnowledgeLanguage}
        if language not in supported_languages:
            raise ValueError(
                f"Invalid language '{language}'. Supported languages are: {sorted(supported_languages)}."
            )

        if tags is not None and not isinstance(tags, list):
            raise ValueError("Tags must be a list of strings if provided.")

        embedding: Optional[List[float]] = None
        embedding_stale: bool = False
        embedding_model: Optional[str] = None

        try:
            embedding = await self.embedding_provider.embed_text(
                cleaned_answer,
                prefix=PREFIX_PASSAGE,
                is_query=False,
            )
            embedding_model = getattr(self.embedding_provider, "model_name", ACTIVE_EMBEDDING_MODEL)
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            logger.warning(
                f"Embedding generation failed for FAQ in business '{business_id}': {exc}. "
                "Saving FAQ with embedding=None and embedding_stale=True."
            )
            embedding = None
            embedding_stale = True
            embedding_model = None

        return await self.knowledge_repo.create_faq(
            db=db,
            business_id=business_id,
            question=cleaned_question,
            answer=cleaned_answer,
            tags=tags if tags is not None else [],
            language=language,
            embedding=embedding,
            embedding_stale=embedding_stale,
            embedding_model=embedding_model,
        )

    async def get_faq(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> Optional[KnowledgeBaseEntry]:
        """Retrieves a single FAQ entry strictly scoped to the tenant.

        Returns None if not found or if the entry is not an FAQ.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("Valid business_id is required.")
        if not entry_id or not isinstance(entry_id, uuid.UUID):
            raise ValueError("Valid entry_id is required.")

        entry = await self.knowledge_repo.get_by_id(db, business_id=business_id, entry_id=entry_id)
        if not entry or entry.source_type != KnowledgeSourceType.FAQ.value:
            return None
        return entry

    async def list_faqs(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        language: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[KnowledgeBaseEntry]:
        """Lists paginated FAQ entries for a business, ordered newest first."""
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("Valid business_id is required.")

        if language is not None:
            supported_languages = {l.value for l in KnowledgeLanguage}
            if language not in supported_languages:
                raise ValueError(
                    f"Invalid language '{language}'. Supported languages are: {sorted(supported_languages)}."
                )

        bounded_limit = min(max(1, limit), 100)
        bounded_offset = max(0, offset)

        return await self.knowledge_repo.list_by_business(
            db=db,
            business_id=business_id,
            source_type=KnowledgeSourceType.FAQ.value,
            language=language,
            limit=bounded_limit,
            offset=bounded_offset,
        )

    async def update_faq(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        entry_id: uuid.UUID,
        question: Any = _UNSET,
        answer: Optional[str] = None,
        tags: Optional[List[str]] = None,
        language: Optional[str] = None,
    ) -> Optional[KnowledgeBaseEntry]:
        """Updates FAQ fields. Content changes regenerate vector embeddings from the answer text.

        Guarantees:
        - Rejects update if entry does not exist or belongs to another business.
        - Tags-only or language-only updates do not regenerate embeddings.
        - If question or answer text changes:
          - Recomputes vector embedding using the target answer text.
          - If embedding succeeds: saves new vector and sets embedding_stale=False.
          - If embedding fails: saves updated text and marks embedding_stale=True.
        - Flushes without committing.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("Valid business_id is required.")
        if not entry_id or not isinstance(entry_id, uuid.UUID):
            raise ValueError("Valid entry_id is required.")

        entry = await self.get_faq(db, business_id=business_id, entry_id=entry_id)
        if not entry:
            return None

        update_data: dict[str, Any] = {}

        if question is not _UNSET:
            if question is not None and not isinstance(question, str):
                raise ValueError("Question must be a string or None if provided.")
            update_data["question"] = question.strip() if question and question.strip() else None

        if answer is not None:
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Answer cannot be empty or whitespace-only.")
            update_data["answer"] = answer.strip()

        if tags is not None:
            if not isinstance(tags, list):
                raise ValueError("Tags must be a list of strings if provided.")
            update_data["tags"] = tags

        if language is not None:
            supported_languages = {l.value for l in KnowledgeLanguage}
            if language not in supported_languages:
                raise ValueError(
                    f"Invalid language '{language}'. Supported languages are: {sorted(supported_languages)}."
                )
            update_data["language"] = language

        # Check if content (question or answer) changed
        content_changed = ("answer" in update_data) or ("question" in update_data)
        if content_changed:
            target_answer = update_data.get("answer", entry.answer)
            try:
                new_embedding = await self.embedding_provider.embed_text(
                    target_answer,
                    prefix=PREFIX_PASSAGE,
                    is_query=False,
                )
                update_data["embedding"] = new_embedding
                update_data["embedding_stale"] = False
                update_data["embedding_model"] = getattr(
                    self.embedding_provider, "model_name", ACTIVE_EMBEDDING_MODEL
                )
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                logger.warning(
                    f"Embedding regeneration failed for FAQ '{entry_id}' in business '{business_id}': {exc}. "
                    "Marking entry stale."
                )
                update_data["embedding_stale"] = True
                update_data["embedding_model"] = None

        return await self.knowledge_repo.update_entry(
            db=db,
            business_id=business_id,
            entry_id=entry_id,
            **update_data,
        )

    async def delete_faq(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> bool:
        """Deletes an FAQ entry strictly within tenant scope.

        Returns True if deleted, False if entry does not exist or is not an FAQ for the tenant.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("Valid business_id is required.")
        if not entry_id or not isinstance(entry_id, uuid.UUID):
            raise ValueError("Valid entry_id is required.")

        entry = await self.get_faq(db, business_id=business_id, entry_id=entry_id)
        if not entry:
            return False

        return await self.knowledge_repo.delete_entry(
            db=db,
            business_id=business_id,
            entry_id=entry_id,
        )

    async def search_knowledge(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        source_type: Optional[str] = None,
    ) -> List[Tuple[KnowledgeBaseEntry, float]]:
        """Performs tenant-scoped semantic vector search using pgvector cosine distance.

        Guarantees:
        - Strictly scoped to business_id (zero cross-tenant leakage).
        - Encodes query using the configured embedding provider.
        - Excludes entries where embedding is NULL or embedding_stale is True.
        - Orders results by cosine distance ascending (closest first).
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("Valid business_id is required.")
        if query is None or not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty or whitespace-only.")
        if top_k < 1 or top_k > 100:
            raise ValueError(f"top_k must be between 1 and 100 (received {top_k}).")

        cleaned_query = query.strip()
        query_vector = await self.embedding_provider.embed_text(
            cleaned_query,
            prefix=PREFIX_QUERY,
            is_query=True,
        )

        active_model = getattr(self.embedding_provider, "model_name", ACTIVE_EMBEDDING_MODEL)
        return await self.knowledge_repo.search_similar(
            db=db,
            business_id=business_id,
            query_vector=query_vector,
            top_k=top_k,
            source_type=source_type,
            score_threshold=score_threshold,
            embedding_model=active_model,
        )

    async def reembed_stale_entries(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        limit: int = 50,
    ) -> int:
        """Finds stale FAQ entries for the business and regenerates their vector embeddings.

        Guarantees:
        - Only processes FAQ entries (source_type='FAQ'). Never touches document chunks.
        - Strictly tenant-scoped to business_id.
        - On success, updates embedding and sets embedding_stale=False with active embedding_model.
        - On failure for an individual entry, logs warning and proceeds with remaining entries.
        - Returns count of successfully re-embedded entries.
        """
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("Valid business_id is required.")

        bounded_limit = min(max(1, limit), 100)
        stale_faqs = await self.knowledge_repo.list_by_business(
            db=db,
            business_id=business_id,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding_stale=True,
            limit=bounded_limit,
        )

        success_count = 0
        active_model = getattr(self.embedding_provider, "model_name", ACTIVE_EMBEDDING_MODEL)
        for entry in stale_faqs:
            try:
                new_vector = await self.embedding_provider.embed_text(
                    entry.answer,
                    prefix=PREFIX_PASSAGE,
                    is_query=False,
                )
                await self.knowledge_repo.update_entry(
                    db=db,
                    business_id=business_id,
                    entry_id=entry.id,
                    embedding=new_vector,
                    embedding_stale=False,
                    embedding_model=active_model,
                )
                success_count += 1
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                logger.warning(
                    f"Failed to re-embed stale FAQ entry '{entry.id}' for business '{business_id}': {exc}"
                )

        return success_count

    async def reembed_faq_batch(
        self,
        db: AsyncSession,
        business_id: Optional[uuid.UUID] = None,
        batch_size: int = 50,
        dry_run: bool = False,
    ) -> ReembedBatchResult:
        """Processes a bounded batch of FAQ entries requiring E5 embeddings.

        Guarantees:
        - Maximum batch size of 50.
        - Supports dry-run inspection without database writes.
        - Uses FOR UPDATE SKIP LOCKED to prevent duplicate processing by concurrent workers.
        - Encodes answers using active embedding provider with 'passage: ' prefix.
        - Validates 384 dimensions, finite numeric values, and unit normalization.
        - Updates only embedding, embedding_model, embedding_stale, and updated_at.
        - Preserves all FAQ text content, tags, language, and tenant ownership.
        - Rolls back failed batches and never labels failed vectors as E5.
        - Explicitly flags entries with invalid/empty answers as stale without halting batch.
        """
        bounded_batch_size = min(max(1, batch_size), 50)
        active_model = getattr(self.embedding_provider, "model_name", ACTIVE_EMBEDDING_MODEL)

        # 1. Dry Run Mode
        if dry_run:
            entries = await self.knowledge_repo.list_faqs_needing_reembed(
                db=db,
                business_id=business_id,
                limit=bounded_batch_size,
                target_model=active_model,
                for_update=False,
            )
            total_remaining = await self.knowledge_repo.count_faqs_needing_reembed(
                db=db,
                business_id=business_id,
                target_model=active_model,
            )
            return ReembedBatchResult(
                scanned=len(entries),
                reembedded=0,
                failed=0,
                remaining=total_remaining,
                dry_run=True,
                entry_ids=[e.id for e in entries],
            )

        # 2. Live Execution Mode with Skip Locking
        entries = await self.knowledge_repo.list_faqs_needing_reembed(
            db=db,
            business_id=business_id,
            limit=bounded_batch_size,
            target_model=active_model,
            for_update=True,
        )

        if not entries:
            total_remaining = await self.knowledge_repo.count_faqs_needing_reembed(
                db=db,
                business_id=business_id,
                target_model=active_model,
            )
            return ReembedBatchResult(
                scanned=0,
                reembedded=0,
                failed=0,
                remaining=total_remaining,
                dry_run=False,
                entry_ids=[],
            )

        # Separate entries with valid answer strings vs empty/invalid answers
        valid_entries: List[KnowledgeBaseEntry] = []
        invalid_entries: List[KnowledgeBaseEntry] = []

        for entry in entries:
            if entry.answer and entry.answer.strip():
                valid_entries.append(entry)
            else:
                invalid_entries.append(entry)

        # Handle invalid entries: isolate as stale without labeling as E5
        for inv in invalid_entries:
            inv.embedding = None
            inv.embedding_stale = True
            inv.embedding_model = None
            inv.updated_at = func.now()

        # Generate embeddings for valid entries
        reembedded_ids: List[uuid.UUID] = []
        if valid_entries:
            answers = [e.answer.strip() for e in valid_entries]
            try:
                embeddings = await self.embedding_provider.embed_batch(
                    answers,
                    prefix=PREFIX_PASSAGE,
                    is_query=False,
                )
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                logger.error(f"Batch embedding generation failed for {len(valid_entries)} FAQs: {exc}")
                raise

            if len(embeddings) != len(valid_entries):
                raise ValueError(
                    f"Generated embeddings count ({len(embeddings)}) mismatch with valid FAQs ({len(valid_entries)})."
                )

            # Strict validation
            for idx, vec in enumerate(embeddings):
                if not isinstance(vec, (list, tuple)) or len(vec) != EMBEDDING_VECTOR_DIMENSION:
                    raise ValueError(
                        f"Vector at index {idx} has invalid dimension {len(vec) if isinstance(vec, (list, tuple)) else 'non-sequence'}; "
                        f"expected {EMBEDDING_VECTOR_DIMENSION}."
                    )
                if not all(math.isfinite(x) for x in vec):
                    raise ValueError(f"Vector at index {idx} contains non-finite values (NaN or Inf).")
                norm = math.sqrt(sum(x * x for x in vec))
                if not (0.95 <= norm <= 1.05):
                    raise ValueError(f"Vector at index {idx} is not unit-normalized (norm={norm:.4f}).")

            for entry, vec in zip(valid_entries, embeddings):
                entry.embedding = list(vec)
                entry.embedding_model = active_model
                entry.embedding_stale = False
                entry.updated_at = func.now()
                reembedded_ids.append(entry.id)

        await db.flush()

        total_remaining = await self.knowledge_repo.count_faqs_needing_reembed(
            db=db,
            business_id=business_id,
            target_model=active_model,
        )

        return ReembedBatchResult(
            scanned=len(entries),
            reembedded=len(reembedded_ids),
            failed=len(invalid_entries),
            remaining=total_remaining,
            dry_run=False,
            entry_ids=reembedded_ids,
        )


knowledge_service = KnowledgeService()

