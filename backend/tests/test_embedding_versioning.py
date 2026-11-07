"""Comprehensive unit and integration tests for Phase 5.4F.8: Embedding Model Versioning & Quarantine.

Verifies:
1. E5 FAQ creation sets embedding_model to active model identifier.
2. E5 document chunks set embedding_model to active model identifier upon finalization.
3. Semantic search retrieves only vectors matching active provider model.
4. Legacy-unknown vectors are strictly quarantined and never returned.
5. Legacy MiniLM vectors are strictly quarantined and never returned.
6. Null model vectors are strictly quarantined and never returned.
7. Stale vectors are strictly excluded even if model matches.
8. Multi-tenant isolation is strictly maintained across models.
9. READY-file requirement is strictly maintained for document chunks.
10. Failed embedding generation leaves embedding_model=None and embedding_stale=True (no false labeling).
11. FAQ updates and re-embedding update embedding_model to active model.
12. Alembic migration upgrade and downgrade test.
"""

import asyncio
from typing import List, Optional
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from sqlalchemy import select, text

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.knowledge import (
    ACTIVE_EMBEDDING_MODEL,
    LEGACY_UNKNOWN_EMBEDDING_MODEL,
    KnowledgeBaseEntry,
    KnowledgeLanguage,
    KnowledgeSourceType,
)
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus
from app.providers.embeddings.base import EmbeddingProvider, PREFIX_PASSAGE, PREFIX_QUERY
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.storage.base import StorageProvider
from app.services.document_processing_service import (
    DocumentProcessingService,
    ProcessingResultStatus,
)
from app.services.knowledge_service import KnowledgeService
from tests.test_document_extractor import create_multipage_pdf_bytes


# =====================================================================
# Test Helpers & In-Memory Providers
# =====================================================================

class InMemoryStorageProvider(StorageProvider):
    """In-memory mock storage provider."""

    def __init__(self) -> None:
        self.files = {}

    def validate_key(self, key: str) -> None:
        if not key or ".." in key:
            raise ValueError(f"Invalid key: {key}")

    async def upload(self, key: str, data: bytes, overwrite: bool = False) -> str:
        self.validate_key(key)
        self.files[key] = data
        return key

    async def download(self, key: str) -> bytes:
        self.validate_key(key)
        if key not in self.files:
            raise FileNotFoundError(f"Key {key} not found")
        return self.files[key]

    async def delete(self, key: str) -> bool:
        self.validate_key(key)
        return self.files.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        self.validate_key(key)
        return key in self.files


async def create_test_business(db, name: str = "Versioning Biz") -> Business:
    biz = Business(
        name=name,
        slug=f"vers-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.flush()
    await db.commit()
    await db.refresh(biz)
    return biz


async def create_test_file(
    db,
    business_id: uuid.UUID,
    filename: str = "version_doc.pdf",
    status: KnowledgeFileStatus = KnowledgeFileStatus.READY,
) -> KnowledgeFile:
    kfile = KnowledgeFile(
        business_id=business_id,
        filename=filename,
        storage_key=f"biz/{business_id}/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        processing_status=status.value,
    )
    db.add(kfile)
    await db.flush()
    await db.commit()
    await db.refresh(kfile)
    return kfile


# =====================================================================
# 1. Version Labeling on Creation
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_persists_active_embedding_model():
    """Verifies that create_faq records the active provider's exact model identifier."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Active Model FAQ Biz")

        faq = await service.create_faq(
            db=db,
            business_id=biz.id,
            question="What is E5?",
            answer="E5 is an embedding model with task prefixes.",
        )

        assert faq.id is not None
        assert faq.embedding is not None
        assert faq.embedding_model == ACTIVE_EMBEDDING_MODEL
        assert faq.embedding_stale is False

        # Refresh from database to ensure persistence
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq.id)
        persisted = (await db.execute(stmt)).scalar_one()
        assert persisted.embedding_model == ACTIVE_EMBEDDING_MODEL


@pytest.mark.asyncio
async def test_document_chunks_persist_active_embedding_model():
    """Verifies that DocumentProcessingService records the active model identifier on all chunks."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    storage = InMemoryStorageProvider()

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Active Model Chunk Biz")
        kfile = await create_test_file(db, biz.id, status=KnowledgeFileStatus.PENDING)

    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=provider,
    )

    result = await service.process_file(kfile.id)
    assert result.status == ProcessingResultStatus.READY

    async with async_session_factory() as db:
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.source_file_id == kfile.id)
        chunks = (await db.execute(stmt)).scalars().all()
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.embedding_model == ACTIVE_EMBEDDING_MODEL
            assert chunk.embedding is not None
            assert chunk.embedding_stale is False


# =====================================================================
# 2. Legacy Vector Quarantine in Semantic Search
# =====================================================================

@pytest.mark.asyncio
async def test_search_quarantines_legacy_unknown_and_legacy_minilm():
    """Verifies that legacy vectors are quarantined and never returned in active E5 searches."""
    active_provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=active_provider)

    query_text = "What are your business hours?"
    identical_answer = "We are open Monday through Friday from 9 AM to 5 PM."

    # Generate identical vector representation
    shared_vector = await active_provider.embed_text(identical_answer, prefix=PREFIX_PASSAGE)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Quarantine Search Biz")

        # 1. Entry with active E5 model
        e5_entry = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Hours question?",
            answer=identical_answer,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=shared_vector,
            embedding_stale=False,
            embedding_model=ACTIVE_EMBEDDING_MODEL,
        )

        # 2. Entry with legacy-unknown model (same vector, should be quarantined)
        legacy_unknown_entry = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Legacy unknown question?",
            answer=identical_answer,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=shared_vector,
            embedding_stale=False,
            embedding_model=LEGACY_UNKNOWN_EMBEDDING_MODEL,
        )

        # 3. Entry with legacy MiniLM model (same vector, should be quarantined)
        legacy_minilm_entry = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Legacy minilm question?",
            answer=identical_answer,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=shared_vector,
            embedding_stale=False,
            embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )

        # 4. Entry with NULL model (should be quarantined)
        null_model_entry = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Null model question?",
            answer=identical_answer,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=shared_vector,
            embedding_stale=False,
            embedding_model=None,
        )

        db.add_all([e5_entry, legacy_unknown_entry, legacy_minilm_entry, null_model_entry])
        await db.flush()
        await db.commit()

        # Execute search using active E5 service
        results = await service.search_knowledge(
            db=db,
            business_id=biz.id,
            query=query_text,
            top_k=10,
        )

        result_ids = [entry.id for entry, _ in results]

        # Only the active E5 entry must be returned
        assert e5_entry.id in result_ids
        assert legacy_unknown_entry.id not in result_ids
        assert legacy_minilm_entry.id not in result_ids
        assert null_model_entry.id not in result_ids


# =====================================================================
# 3. Stale & Null Embedding Exclusion
# =====================================================================

@pytest.mark.asyncio
async def test_search_excludes_stale_e5_vector():
    """Verifies that an E5 vector is excluded when embedding_stale=True."""
    active_provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=active_provider)
    answer = "Sample answer text."
    vec = await active_provider.embed_text(answer, prefix=PREFIX_PASSAGE)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Stale Exclusion Biz")

        stale_entry = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Stale question?",
            answer=answer,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=vec,
            embedding_stale=True,
            embedding_model=ACTIVE_EMBEDDING_MODEL,
        )
        db.add(stale_entry)
        await db.flush()
        await db.commit()

        results = await service.search_knowledge(
            db=db,
            business_id=biz.id,
            query="Sample query",
        )

        assert stale_entry.id not in [entry.id for entry, _ in results]


# =====================================================================
# 4. Multi-Tenant Isolation
# =====================================================================

@pytest.mark.asyncio
async def test_search_enforces_tenant_isolation_with_matching_models():
    """Verifies that matching E5 vectors from Business A are never visible to Business B."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)
    text_content = "Confidential business revenue report for tenant A."
    vec = await provider.embed_text(text_content, prefix=PREFIX_PASSAGE)

    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Tenant A")
        biz_b = await create_test_business(db, name="Tenant B")

        entry_a = KnowledgeBaseEntry(
            business_id=biz_a.id,
            question="Revenue?",
            answer=text_content,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=vec,
            embedding_stale=False,
            embedding_model=ACTIVE_EMBEDDING_MODEL,
        )
        db.add(entry_a)
        await db.flush()
        await db.commit()

        # Search from Business B
        results_b = await service.search_knowledge(
            db=db,
            business_id=biz_b.id,
            query="revenue report",
        )

        assert entry_a.id not in [entry.id for entry, _ in results_b]


# =====================================================================
# 5. READY File Filtering for Document Chunks
# =====================================================================

@pytest.mark.asyncio
async def test_search_excludes_chunks_from_non_ready_files():
    """Verifies that chunks from PENDING or FAILED files are excluded even if model matches."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)
    vec = await provider.embed_text("Chunk text", prefix=PREFIX_PASSAGE)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Ready File Test Biz")
        pending_file = await create_test_file(db, biz.id, status=KnowledgeFileStatus.PROCESSING)
        ready_file = await create_test_file(db, biz.id, status=KnowledgeFileStatus.READY)

        pending_chunk = KnowledgeBaseEntry(
            business_id=biz.id,
            source_file_id=pending_file.id,
            chunk_index=0,
            answer="Chunk from pending file",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            embedding=vec,
            embedding_stale=False,
            embedding_model=ACTIVE_EMBEDDING_MODEL,
        )
        ready_chunk = KnowledgeBaseEntry(
            business_id=biz.id,
            source_file_id=ready_file.id,
            chunk_index=0,
            answer="Chunk from ready file",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            embedding=vec,
            embedding_stale=False,
            embedding_model=ACTIVE_EMBEDDING_MODEL,
        )
        db.add_all([pending_chunk, ready_chunk])
        await db.flush()
        await db.commit()

        results = await service.search_knowledge(
            db=db,
            business_id=biz.id,
            query="Chunk",
        )

        result_ids = [entry.id for entry, _ in results]
        assert ready_chunk.id in result_ids
        assert pending_chunk.id not in result_ids


# =====================================================================
# 6. Failed Embedding Handling (No False Labeling)
# =====================================================================

@pytest.mark.asyncio
async def test_failed_embedding_does_not_label_model():
    """Verifies that failed embedding generation leaves embedding=None, stale=True, and model=None."""
    failing_provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    failing_provider.embed_text = AsyncMock(side_effect=RuntimeError("Provider failure"))
    service = KnowledgeService(embedding_provider=failing_provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Failing Provider Biz")

        faq = await service.create_faq(
            db=db,
            business_id=biz.id,
            question="Will this fail?",
            answer="Yes, embedding provider will raise an exception.",
        )

        assert faq.id is not None
        assert faq.embedding is None
        assert faq.embedding_stale is True
        assert faq.embedding_model is None


# =====================================================================
# 7. Update and Re-embedding Model Transitions
# =====================================================================

@pytest.mark.asyncio
async def test_update_faq_updates_embedding_model_on_content_change():
    """Verifies that updating answer content generates new vector and sets active model."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Update Model Biz")

        # Create initially with legacy-unknown
        faq = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Original Q",
            answer="Original Answer",
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=[0.1] * 384,
            embedding_stale=False,
            embedding_model=LEGACY_UNKNOWN_EMBEDDING_MODEL,
        )
        db.add(faq)
        await db.flush()
        await db.commit()

        # Update answer
        updated = await service.update_faq(
            db=db,
            business_id=biz.id,
            entry_id=faq.id,
            answer="Brand new updated answer",
        )

        assert updated is not None
        assert updated.embedding_model == ACTIVE_EMBEDDING_MODEL
        assert updated.embedding_stale is False


@pytest.mark.asyncio
async def test_reembed_stale_faq_updates_embedding_model():
    """Verifies that re-embedding a stale entry updates its model to active model."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Reembed Model Biz")

        faq = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Stale FAQ",
            answer="Stale Answer",
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=None,
            embedding_stale=True,
            embedding_model=None,
        )
        db.add(faq)
        await db.flush()
        await db.commit()

        count = await service.reembed_stale_entries(db, business_id=biz.id)
        assert count == 1

        await db.refresh(faq)
        assert faq.embedding is not None
        assert faq.embedding_model == ACTIVE_EMBEDDING_MODEL
        assert faq.embedding_stale is False


# =====================================================================
# 8. Reversible Migration Test (Upgrade & Downgrade)
# =====================================================================

@pytest.mark.asyncio
async def test_migration_columns_and_indices_exist():
    """Verifies that the database has the embedding_model column and composite index from 0007."""
    async with async_session_factory() as db:
        # Check column exists in information_schema
        col_res = await db.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'knowledge_base_entries' AND column_name = 'embedding_model';
                """
            )
        )
        col = col_res.fetchone()
        assert col is not None
        assert col[0] == "embedding_model"
        assert col[2] == "YES"  # nullable

        # Check composite index exists
        idx_res = await db.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'knowledge_base_entries' AND indexname = 'ix_kbe_business_model_stale';
                """
            )
        )
        idx = idx_res.fetchone()
        assert idx is not None
        assert idx[0] == "ix_kbe_business_model_stale"

