"""KnowledgeBaseEntry repository for FAQs, document chunks, and pgvector similarity search."""

import uuid
from typing import Any, List, Optional, Tuple
from sqlalchemy import select, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    ACTIVE_EMBEDDING_MODEL,
    KnowledgeBaseEntry,
    KnowledgeSourceType,
    KnowledgeLanguage,
    EMBEDDING_VECTOR_DIMENSION,
)
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus

# Immutable fields that must never be altered via update_entry to protect tenant integrity
IMMUTABLE_FIELDS = frozenset({"id", "entry_id", "business_id", "source_file_id", "source_type", "chunk_index"})

# Allow-list of updateable fields
ALLOWED_UPDATE_FIELDS = frozenset({
    "question",
    "answer",
    "tags",
    "language",
    "page_number",
    "section_title",
    "embedding",
    "embedding_stale",
    "embedding_model",
})

# Content fields that invalidate vector embeddings when modified
CONTENT_FIELDS = frozenset({"question", "answer"})


class KnowledgeRepository:
    """Repository handling persistence and vector search for KnowledgeBaseEntry entities."""

    async def create_faq(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        question: Optional[str] = None,
        answer: str = "",
        tags: Optional[List[Any]] = None,
        language: str = KnowledgeLanguage.EN.value,
        embedding: Optional[List[float]] = None,
        embedding_stale: bool = False,
        embedding_model: Optional[str] = None,
    ) -> KnowledgeBaseEntry:
        """Creates and flushes a new FAQ entry without committing.

        Guarantees:
        - source_type is set to 'FAQ'.
        - source_file_id and chunk_index are strictly None (enforced by DB check constraint).
        """
        actual_model = embedding_model or (ACTIVE_EMBEDDING_MODEL if embedding is not None else None)
        entry = KnowledgeBaseEntry(
            business_id=business_id,
            question=question.strip() if question else None,
            answer=answer.strip(),
            tags=tags if tags is not None else [],
            language=language,
            source_type=KnowledgeSourceType.FAQ.value,
            source_file_id=None,
            chunk_index=None,
            embedding=embedding,
            embedding_stale=embedding_stale,
            embedding_model=actual_model,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def create_chunk(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        source_file_id: uuid.UUID,
        chunk_index: int,
        answer: str,
        question: Optional[str] = None,
        page_number: Optional[int] = None,
        section_title: Optional[str] = None,
        tags: Optional[List[Any]] = None,
        language: str = KnowledgeLanguage.EN.value,
        embedding: Optional[List[float]] = None,
        embedding_model: Optional[str] = None,
    ) -> KnowledgeBaseEntry:
        """Creates and flushes a new document chunk entry without committing.

        Guarantees:
        - source_type is set to 'document_chunk'.
        - source_file_id is non-null and must match the owning business.
        - chunk_index is non-null and >= 0.
        """
        actual_model = embedding_model or (ACTIVE_EMBEDDING_MODEL if embedding is not None else None)
        entry = KnowledgeBaseEntry(
            business_id=business_id,
            source_file_id=source_file_id,
            chunk_index=chunk_index,
            answer=answer.strip(),
            question=question.strip() if question else None,
            page_number=page_number,
            section_title=section_title.strip() if section_title else None,
            tags=tags if tags is not None else [],
            language=language,
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            embedding=embedding,
            embedding_stale=False,
            embedding_model=actual_model,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def create_chunks_batch(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        chunks_data: List[dict],
    ) -> List[KnowledgeBaseEntry]:
        """Batch-persists chunks for a document while preserving input ordering."""
        entries: List[KnowledgeBaseEntry] = []
        for item in chunks_data:
            item_embedding = item.get("embedding")
            actual_model = item.get("embedding_model") or (
                ACTIVE_EMBEDDING_MODEL if item_embedding is not None else None
            )
            entry = KnowledgeBaseEntry(
                business_id=business_id,
                source_file_id=item["source_file_id"],
                chunk_index=item["chunk_index"],
                answer=item["answer"].strip(),
                question=item.get("question", "").strip() if item.get("question") else None,
                page_number=item.get("page_number"),
                section_title=item.get("section_title", "").strip() if item.get("section_title") else None,
                tags=item.get("tags") if item.get("tags") is not None else [],
                language=item.get("language", KnowledgeLanguage.EN.value),
                source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
                embedding=item_embedding,
                embedding_stale=item.get("embedding_stale", False),
                embedding_model=actual_model,
            )
            entries.append(entry)

        db.add_all(entries)
        await db.flush()
        return entries

    async def get_by_id(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> Optional[KnowledgeBaseEntry]:
        """Fetches a knowledge entry by primary key strictly scoped to the tenant."""
        stmt = select(KnowledgeBaseEntry).where(
            KnowledgeBaseEntry.id == entry_id,
            KnowledgeBaseEntry.business_id == business_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_business(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        source_type: Optional[str] = None,
        source_file_id: Optional[uuid.UUID] = None,
        language: Optional[str] = None,
        embedding_stale: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[KnowledgeBaseEntry]:
        """Retrieves paginated knowledge entries for a business, ordered newest first."""
        stmt = (
            select(KnowledgeBaseEntry)
            .where(KnowledgeBaseEntry.business_id == business_id)
            .order_by(KnowledgeBaseEntry.created_at.desc())
        )
        if source_type:
            stmt = stmt.where(KnowledgeBaseEntry.source_type == source_type)
        if source_file_id:
            stmt = stmt.where(KnowledgeBaseEntry.source_file_id == source_file_id)
        if language:
            stmt = stmt.where(KnowledgeBaseEntry.language == language)
        if embedding_stale is not None:
            stmt = stmt.where(KnowledgeBaseEntry.embedding_stale == embedding_stale)
        if limit > 0:
            stmt = stmt.limit(limit)
        if offset > 0:
            stmt = stmt.offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_faqs_needing_reembed(
        self,
        db: AsyncSession,
        business_id: Optional[uuid.UUID] = None,
        target_model: str = ACTIVE_EMBEDDING_MODEL,
    ) -> int:
        """Counts FAQ entries that do not have an active, non-stale embedding."""
        conditions = [
            KnowledgeBaseEntry.source_type == KnowledgeSourceType.FAQ.value,
            func.trim(func.coalesce(KnowledgeBaseEntry.answer, "")) != "",
            or_(
                KnowledgeBaseEntry.embedding_model != target_model,
                KnowledgeBaseEntry.embedding_model.is_(None),
                KnowledgeBaseEntry.embedding_stale == True,  # noqa: E712
                KnowledgeBaseEntry.embedding.is_(None),
            ),
        ]
        if business_id is not None:
            conditions.append(KnowledgeBaseEntry.business_id == business_id)

        stmt = select(func.count(KnowledgeBaseEntry.id)).where(*conditions)
        return (await db.scalar(stmt)) or 0

    async def count_faqs_with_blank_answer(
        self,
        db: AsyncSession,
        business_id: Optional[uuid.UUID] = None,
    ) -> int:
        """Counts FAQ entries that have a blank or whitespace-only answer."""
        conditions = [
            KnowledgeBaseEntry.source_type == KnowledgeSourceType.FAQ.value,
            func.trim(func.coalesce(KnowledgeBaseEntry.answer, "")) == "",
        ]
        if business_id is not None:
            conditions.append(KnowledgeBaseEntry.business_id == business_id)

        stmt = select(func.count(KnowledgeBaseEntry.id)).where(*conditions)
        return (await db.scalar(stmt)) or 0

    async def list_faqs_needing_reembed(
        self,
        db: AsyncSession,
        business_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        target_model: str = ACTIVE_EMBEDDING_MODEL,
        for_update: bool = True,
    ) -> List[KnowledgeBaseEntry]:
        """Lists FAQ entries requiring re-embedding with row-level skip locking.

        Guarantees:
        - Bounded batch size of at most 50.
        - Excludes entries with blank or whitespace-only answers.
        - Supports tenant scoping (if business_id is provided) or platform-wide (if None).
        - with_for_update(skip_locked=True) prevents race conditions and duplicate worker execution.
        """
        bounded_limit = min(max(1, limit), 50)
        conditions = [
            KnowledgeBaseEntry.source_type == KnowledgeSourceType.FAQ.value,
            func.trim(func.coalesce(KnowledgeBaseEntry.answer, "")) != "",
            or_(
                KnowledgeBaseEntry.embedding_model != target_model,
                KnowledgeBaseEntry.embedding_model.is_(None),
                KnowledgeBaseEntry.embedding_stale == True,  # noqa: E712
                KnowledgeBaseEntry.embedding.is_(None),
            ),
        ]
        if business_id is not None:
            conditions.append(KnowledgeBaseEntry.business_id == business_id)

        stmt = (
            select(KnowledgeBaseEntry)
            .where(*conditions)
            .order_by(KnowledgeBaseEntry.created_at.asc())
            .limit(bounded_limit)
        )
        if for_update:
            stmt = stmt.with_for_update(skip_locked=True)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_entry(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        entry_id: uuid.UUID,
        **kwargs: Any,
    ) -> Optional[KnowledgeBaseEntry]:
        """Updates entry fields strictly scoped to business_id.

        Guarantees:
        - Rejects changes to immutable structural fields (id, business_id, source_file_id, source_type, chunk_index).
        - Validates fields against an allow-list.
        - Automatically marks embedding_stale=True if content (question, answer) changes,
          unless caller explicitly supplies a new embedding or specifies embedding_stale.
        - Returns None if the entry does not belong to the supplied business.
        """
        # Validate against immutable fields
        for field in kwargs:
            if field in IMMUTABLE_FIELDS:
                raise ValueError(f"Field '{field}' cannot be modified through update_entry.")
            if field not in ALLOWED_UPDATE_FIELDS:
                raise ValueError(f"Field '{field}' is not in the allowed update fields.")

        entry = await self.get_by_id(db, business_id=business_id, entry_id=entry_id)
        if not entry:
            return None

        # Check if text content is being modified
        content_changed = any(f in kwargs for f in CONTENT_FIELDS)
        if content_changed and "embedding_stale" not in kwargs and "embedding" not in kwargs:
            entry.embedding_stale = True

        for field, value in kwargs.items():
            if field in ("question", "answer") and isinstance(value, str):
                setattr(entry, field, value.strip())
            elif field == "section_title" and isinstance(value, str):
                setattr(entry, field, value.strip() if value else None)
            else:
                setattr(entry, field, value)

        await db.flush()
        await db.refresh(entry)
        return entry

    async def delete_entry(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> bool:
        """Deletes an entry strictly within tenant scope.

        Returns True if deleted, False if entry was not found for the business.
        """
        entry = await self.get_by_id(db, business_id=business_id, entry_id=entry_id)
        if not entry:
            return False

        await db.delete(entry)
        await db.flush()
        return True

    async def delete_by_source_file(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        source_file_id: uuid.UUID,
    ) -> int:
        """Deletes all chunks belonging to a specific source file strictly within tenant scope.

        Returns the number of deleted chunk entries.
        """
        stmt = delete(KnowledgeBaseEntry).where(
            KnowledgeBaseEntry.business_id == business_id,
            KnowledgeBaseEntry.source_file_id == source_file_id,
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount

    async def search_similar(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        query_vector: List[float],
        top_k: int = 5,
        source_type: Optional[str] = None,
        score_threshold: Optional[float] = None,
        embedding_model: Optional[str] = ACTIVE_EMBEDDING_MODEL,
    ) -> List[Tuple[KnowledgeBaseEntry, float]]:
        """Tenant-scoped vector similarity search using pgvector cosine distance (<=>).

        Parameters:
        - query_vector: 384-dimensional query embedding vector.
        - top_k: Maximum number of results to return (1 <= top_k <= 100).
        - source_type: Optional filter ('FAQ' or 'document_chunk').
        - score_threshold: Maximum allowable cosine distance (0.0 = identical, lower is closer).
          When provided, only entries with cosine distance <= score_threshold are returned.
        - embedding_model: Model identifier filter (defaults to ACTIVE_EMBEDDING_MODEL).
          Ensures search only retrieves vectors generated by the active model and quarantines legacy vectors.

        Guarantees:
        - Strictly scoped by business_id (zero cross-tenant leakage).
        - Excludes entries where embedding is NULL.
        - Excludes entries where embedding_stale is True.
        - Excludes legacy or incompatible embedding models (quarantine).
        - Returns results ordered by cosine distance ascending (closest first).
        - Returns pairs of (KnowledgeBaseEntry, distance_float).
        """
        if not query_vector or len(query_vector) != EMBEDDING_VECTOR_DIMENSION:
            raise ValueError(
                f"Query vector must contain exactly {EMBEDDING_VECTOR_DIMENSION} dimensions "
                f"(received {len(query_vector) if query_vector else 0})."
            )
        if top_k < 1 or top_k > 100:
            raise ValueError(f"top_k must be between 1 and 100 (received {top_k}).")

        target_model = embedding_model or ACTIVE_EMBEDDING_MODEL
        distance_expr = KnowledgeBaseEntry.embedding.cosine_distance(query_vector)

        stmt = (
            select(KnowledgeBaseEntry, distance_expr.label("distance"))
            .outerjoin(
                KnowledgeFile,
                and_(
                    KnowledgeBaseEntry.source_file_id == KnowledgeFile.id,
                    KnowledgeBaseEntry.business_id == KnowledgeFile.business_id,
                ),
            )
            .where(
                KnowledgeBaseEntry.business_id == business_id,
                KnowledgeBaseEntry.embedding.is_not(None),
                KnowledgeBaseEntry.embedding_stale == False,  # noqa: E712
                KnowledgeBaseEntry.embedding_model == target_model,
                or_(
                    KnowledgeBaseEntry.source_file_id.is_(None),
                    KnowledgeFile.processing_status == KnowledgeFileStatus.READY.value,
                ),
            )
        )

        if source_type:
            stmt = stmt.where(KnowledgeBaseEntry.source_type == source_type)

        if score_threshold is not None:
            stmt = stmt.where(distance_expr <= score_threshold)

        stmt = stmt.order_by(distance_expr.asc()).limit(top_k)

        result = await db.execute(stmt)
        rows = result.all()
        return [(row[0], float(row[1])) for row in rows]


knowledge_repository = KnowledgeRepository()
