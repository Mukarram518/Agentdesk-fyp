"""Unit tests for AgentDesk Document Processing Service (Phase 5.4E.2).

Verifies:
1. Successful PDF processing end-to-end.
2. Successful DOCX processing end-to-end.
3. Deleted / non-existent file handling.
4. Already-ready file handling (idempotent no-op).
5. Duplicate concurrent claim prevention.
6. Stale claim / expired lease recovery after timeout.
7. Active lease cannot be stolen.
8. Heartbeat refresh extends lease and rejects invalid tokens.
9. Claim ownership lost prior to finalization (chunks not persisted).
10. Lost ownership during failure handling (chunks never deleted).
11. Existing error messages not overwritten by claim tokens.
12. Extraction failure (sanitization & permanent error).
13. Embedding failure (transient error classification).
14. Invalid vector dimension rejection (strict 384 dimensions).
15. Atomic rollback during finalization failure preserves consistency.
16. Multi-tenant isolation during processing.
17. Search visibility of non-ready files (pending, processing, failed).
18. Real PostgreSQL concurrency using asyncio.gather().
"""

import asyncio
from datetime import datetime, timedelta, timezone
import io
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from sqlalchemy import select, update

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.knowledge import (
    EMBEDDING_VECTOR_DIMENSION,
    KnowledgeBaseEntry,
    KnowledgeLanguage,
    KnowledgeSourceType,
)
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus
from app.providers.embeddings.base import EmbeddingProvider, PREFIX_PASSAGE
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.storage.base import StorageProvider
from app.repositories.knowledge_file_repository import knowledge_file_repository
from app.repositories.knowledge_repository import knowledge_repository
from app.services.document_chunker import E5TokenizerAdapter, MockTokenizer
from app.services.document_processing_service import (
    DocumentProcessingResult,
    DocumentProcessingService,
    ProcessingResultStatus,
    classify_processing_error,
)
from tests.test_document_extractor import (
    create_docx_with_blocks,
    create_multipage_pdf_bytes,
)


# =====================================================================
# In-Memory Test Infrastructure
# =====================================================================

class InMemoryStorageProvider(StorageProvider):
    """In-memory mock storage provider with zero disk I/O."""

    def __init__(self) -> None:
        self.files: Dict[str, bytes] = {}

    def validate_key(self, key: str) -> None:
        if not key or ".." in key:
            raise ValueError(f"Invalid key: {key}")

    async def upload(self, key: str, data: bytes, overwrite: bool = False) -> str:
        self.validate_key(key)
        if not overwrite and key in self.files:
            raise FileExistsError(f"Key {key} exists")
        self.files[key] = data
        return key

    async def download(self, key: str) -> bytes:
        self.validate_key(key)
        if key not in self.files:
            raise FileNotFoundError(f"Storage key '{key}' not found.")
        return self.files[key]

    async def delete(self, key: str) -> bool:
        self.validate_key(key)
        return self.files.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        self.validate_key(key)
        return key in self.files


class BadDimensionEmbeddingProvider(EmbeddingProvider):
    """Embedding provider returning 128-dimensional vectors instead of 384."""

    @property
    def dimension(self) -> int:
        return 128

    async def embed_text(
        self,
        text: str,
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[float]:
        return [0.1] * 128

    async def embed_batch(
        self,
        texts: List[str],
        prefix: Optional[str] = None,
        is_query: bool = False,
    ) -> List[List[float]]:
        return [[0.1] * 128 for _ in texts]


# =====================================================================
# Database Helpers
# =====================================================================

async def create_test_business(db, name: str = "Doc Processing Biz") -> Business:
    """Helper to persist a test business tenant."""
    biz = Business(
        name=name,
        slug=f"dp-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


async def create_test_file(
    db,
    business_id: uuid.UUID,
    filename: str = "document.pdf",
    storage_key: Optional[str] = None,
    processing_status: str = KnowledgeFileStatus.PENDING.value,
    error_message: Optional[str] = None,
    processing_token: Optional[str] = None,
    processing_started_at: Optional[datetime] = None,
) -> KnowledgeFile:
    """Helper to persist a test KnowledgeFile."""
    kfile = KnowledgeFile(
        business_id=business_id,
        filename=filename,
        storage_key=storage_key or f"business/{business_id}/knowledge/{uuid.uuid4()}/{filename}",
        mime_type=(
            "application/pdf"
            if filename.endswith(".pdf")
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        size_bytes=1024,
        processing_status=processing_status,
        error_message=error_message,
        processing_token=processing_token,
        processing_started_at=processing_started_at,
    )
    db.add(kfile)
    await db.commit()
    await db.refresh(kfile)
    return kfile


def create_unit_vector(active_index: int = 0) -> List[float]:
    """Creates a 384-dimensional unit vector."""
    vec = [0.0] * EMBEDDING_VECTOR_DIMENSION
    vec[active_index % EMBEDDING_VECTOR_DIMENSION] = 1.0
    return vec


# =====================================================================
# Tests
# =====================================================================

@pytest.mark.asyncio
async def test_successful_pdf_processing():
    """1. Verifies end-to-end successful PDF processing, chunking, and ready status."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="PDF Test Biz")
        kfile = await create_test_file(db, biz.id, filename="sample.pdf")

    storage = InMemoryStorageProvider()
    pdf_bytes = create_multipage_pdf_bytes()
    await storage.upload(kfile.storage_key, pdf_bytes)

    embedding_provider = MockEmbeddingProvider()
    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=embedding_provider,
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.READY
    assert result.chunks_created > 0
    assert result.file_id == kfile.id
    assert result.business_id == biz.id

    # Verify database state
    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status == KnowledgeFileStatus.READY.value
        assert refreshed.processing_token is None
        assert refreshed.processing_started_at is None
        assert refreshed.error_message is None

        chunks = await knowledge_repository.list_by_business(
            db, business_id=biz.id, source_file_id=kfile.id
        )
        assert len(chunks) == result.chunks_created
        for chunk in chunks:
            assert chunk.source_type == KnowledgeSourceType.DOCUMENT_CHUNK.value
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 384
            assert chunk.embedding_stale is False
            assert chunk.page_number is not None  # Preserves PDF page numbers


@pytest.mark.asyncio
async def test_successful_docx_processing():
    """2. Verifies end-to-end successful DOCX processing with page_number=None."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="DOCX Test Biz")
        kfile = await create_test_file(db, biz.id, filename="document.docx")

    storage = InMemoryStorageProvider()
    docx_bytes = create_docx_with_blocks([
        ("p", "This is the first paragraph of business information."),
        ("h", "Business Overview"),
        ("p", "This section provides essential details about our company services."),
    ])
    await storage.upload(kfile.storage_key, docx_bytes)

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=MockEmbeddingProvider(),
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.READY
    assert result.chunks_created > 0

    async with async_session_factory() as db:
        chunks = await knowledge_repository.list_by_business(
            db, business_id=biz.id, source_file_id=kfile.id
        )
        assert len(chunks) == result.chunks_created
        for chunk in chunks:
            assert chunk.page_number is None  # DOCX page numbers remain None per requirements


@pytest.mark.asyncio
async def test_deleted_or_nonexistent_file_handling():
    """3. Verifies non-existent file handling returns NOT_FOUND without throwing."""
    service = DocumentProcessingService(
        storage_provider=InMemoryStorageProvider(),
        embedding_provider=MockEmbeddingProvider(),
    )

    non_existent_id = uuid.uuid4()
    result = await service.process_file(non_existent_id)

    assert result.status == ProcessingResultStatus.NOT_FOUND
    assert result.file_id == non_existent_id


@pytest.mark.asyncio
async def test_already_ready_file_handling():
    """4. Verifies already-ready files are treated as idempotent no-ops."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(
            db, biz.id, processing_status=KnowledgeFileStatus.READY.value
        )

    service = DocumentProcessingService(
        storage_provider=InMemoryStorageProvider(),
        embedding_provider=MockEmbeddingProvider(),
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.ALREADY_READY
    assert result.chunks_created == 0


@pytest.mark.asyncio
async def test_duplicate_concurrent_claims():
    """5. Verifies that an actively claimed file cannot be claimed by a concurrent worker."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        # File is already in processing status within the active window (fresh updated_at)
        kfile = await create_test_file(
            db,
            biz.id,
            processing_status=KnowledgeFileStatus.PROCESSING.value,
            processing_token="active_worker_token",
        )

    service = DocumentProcessingService(
        storage_provider=InMemoryStorageProvider(),
        embedding_provider=MockEmbeddingProvider(),
        stale_claim_timeout_seconds=300,
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.ALREADY_CLAIMED


@pytest.mark.asyncio
async def test_stale_claim_and_expired_lease_recovery():
    """6. Verifies that a stale processing claim (> timeout) is safely reclaimed and processed."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=600)
        kfile = await create_test_file(
            db,
            biz.id,
            processing_status=KnowledgeFileStatus.PROCESSING.value,
            processing_token="dead_worker_token",
        )
        # Set old updated_at
        await db.execute(
            update(KnowledgeFile)
            .where(KnowledgeFile.id == kfile.id)
            .values(updated_at=old_time)
        )
        await db.commit()

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=MockEmbeddingProvider(),
        stale_claim_timeout_seconds=300,
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.READY
    assert result.chunks_created > 0

    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status == KnowledgeFileStatus.READY.value
        assert refreshed.processing_token is None


@pytest.mark.asyncio
async def test_active_lease_cannot_be_stolen():
    """7. Verifies that an actively progressing worker within timeout cannot have its lease stolen."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        kfile = await create_test_file(
            db,
            biz.id,
            processing_status=KnowledgeFileStatus.PROCESSING.value,
            processing_token="active_token_123",
        )
        await db.execute(
            update(KnowledgeFile)
            .where(KnowledgeFile.id == kfile.id)
            .values(updated_at=recent_time)
        )
        await db.commit()

    service = DocumentProcessingService(
        storage_provider=InMemoryStorageProvider(),
        embedding_provider=MockEmbeddingProvider(),
        stale_claim_timeout_seconds=300,
    )

    result = await service.process_file(kfile.id)
    assert result.status == ProcessingResultStatus.ALREADY_CLAIMED


@pytest.mark.asyncio
async def test_heartbeat_refresh():
    """8. Verifies that refresh_lease conditionally touches updated_at and rejects wrong token."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        token = "valid_heartbeat_token"
        old_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        kfile = await create_test_file(
            db,
            biz.id,
            processing_status=KnowledgeFileStatus.PROCESSING.value,
            processing_token=token,
        )
        await db.execute(
            update(KnowledgeFile)
            .where(KnowledgeFile.id == kfile.id)
            .values(updated_at=old_time)
        )
        await db.commit()

    service = DocumentProcessingService()

    # Refresh with wrong token -> fails
    refreshed_wrong = await service.refresh_lease(kfile.id, "wrong_token")
    assert refreshed_wrong is False

    # Refresh with valid token -> succeeds
    refreshed_ok = await service.refresh_lease(kfile.id, token)
    assert refreshed_ok is True

    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed_row = (await db.execute(stmt)).scalar_one()
        assert (datetime.now(timezone.utc) - refreshed_row.updated_at.replace(tzinfo=timezone.utc)).total_seconds() < 5


@pytest.mark.asyncio
async def test_claim_ownership_lost_before_finalization():
    """9. Verifies that losing claim ownership aborts finalization without persisting chunks."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=MockEmbeddingProvider(),
    )

    original_claim = service._claim_file

    async def claim_and_steal(file_id):
        status, claim_data = await original_claim(file_id)
        # Another worker steals the token
        async with async_session_factory() as s:
            await s.execute(
                update(KnowledgeFile)
                .where(KnowledgeFile.id == file_id)
                .values(processing_token="stolen_by_another_worker")
            )
            await s.commit()
        return status, claim_data

    service._claim_file = claim_and_steal

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.CLAIM_LOST

    # Ensure zero chunks were persisted
    async with async_session_factory() as db:
        chunks = await knowledge_repository.list_by_business(
            db, business_id=biz.id, source_file_id=kfile.id
        )
        assert len(chunks) == 0


@pytest.mark.asyncio
async def test_lost_ownership_during_failure_handling_never_deletes_chunks():
    """10. Verifies that if ownership is lost, _handle_failure rolls back and NEVER deletes chunks."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        vec = create_unit_vector(5)
        # Create file with an existing valid chunk
        kfile = await create_test_file(
            db, biz.id, processing_status=KnowledgeFileStatus.PROCESSING.value, processing_token="worker_token_1"
        )
        chunk = await knowledge_repository.create_chunk(
            db=db,
            business_id=biz.id,
            source_file_id=kfile.id,
            chunk_index=0,
            answer="Original preserved chunk",
            embedding=vec,
        )
        await db.commit()

    service = DocumentProcessingService()

    # Simulate another worker stealing the token before failure handling runs
    async with async_session_factory() as db:
        await db.execute(
            update(KnowledgeFile)
            .where(KnowledgeFile.id == kfile.id)
            .values(processing_token="worker_token_2_stole_this")
        )
        await db.commit()

    from app.services.document_processing_service import ClaimData
    stale_claim_data = ClaimData(
        file_id=kfile.id,
        business_id=biz.id,
        storage_key=kfile.storage_key,
        filename=kfile.filename,
        mime_type=kfile.mime_type,
        claim_token="worker_token_1",  # Old token
    )

    # Worker 1 attempts failure handling with old token
    result = await service._handle_failure(stale_claim_data, RuntimeError("Simulated failure"))

    assert result.status == ProcessingResultStatus.CLAIM_LOST

    # CRITICAL CHECK: Chunk must NOT be deleted!
    async with async_session_factory() as db:
        chunks = await knowledge_repository.list_by_business(
            db, business_id=biz.id, source_file_id=kfile.id
        )
        assert len(chunks) == 1
        assert chunks[0].answer == "Original preserved chunk"


@pytest.mark.asyncio
async def test_existing_error_message_not_overwritten_by_claim_token():
    """11. Verifies that claiming a failed file does not overwrite its error_message with a token."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(
            db,
            biz.id,
            processing_status=KnowledgeFileStatus.FAILED.value,
            error_message="Human-readable previous failure reason",
        )

    service = DocumentProcessingService()
    status, claim_data = await service._claim_file(kfile.id)

    assert status == ProcessingResultStatus.READY
    assert claim_data is not None

    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status == KnowledgeFileStatus.PROCESSING.value
        assert refreshed.processing_token == claim_data.claim_token
        # Token is in processing_token, NOT error_message
        assert claim_data.claim_token not in (refreshed.error_message or "")


@pytest.mark.asyncio
async def test_extraction_failure_sanitization_and_status():
    """12. Verifies extraction failures are classified as permanent, sanitized, and non-retryable."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id, filename="corrupt.pdf")

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, b"NOT_A_VALID_PDF_STREAM_MALFORMED")

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=MockEmbeddingProvider(),
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.FAILED_PERMANENT
    assert result.is_retryable is False
    assert result.error_message is not None
    assert "corrupt" in result.error_message.lower() or "malformed" in result.error_message.lower()
    assert "Traceback" not in result.error_message
    assert "File \"" not in result.error_message

    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status == KnowledgeFileStatus.FAILED.value
        assert refreshed.processing_token is None
        assert refreshed.error_message == result.error_message


@pytest.mark.asyncio
async def test_embedding_failure_transient_classification():
    """13. Verifies embedding timeouts are classified as transient and retryable."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    failing_embedding = MockEmbeddingProvider()
    failing_embedding.embed_batch = AsyncMock(
        side_effect=TimeoutError("Connection to embedding service timed out")
    )

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=failing_embedding,
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.FAILED_TRANSIENT
    assert result.is_retryable is True
    assert result.error_message is not None
    assert "timeout" in result.error_message.lower() or "temporary" in result.error_message.lower()

    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status == KnowledgeFileStatus.FAILED.value
        assert refreshed.processing_token is None


@pytest.mark.asyncio
async def test_invalid_vector_dimensions_rejection():
    """14. Verifies rejection when embedding vectors do not match 384 dimensions."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    bad_dimension_embedding_provider = BadDimensionEmbeddingProvider()
    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=bad_dimension_embedding_provider,
    )

    result = await service.process_file(kfile.id)

    assert result.status == ProcessingResultStatus.FAILED_PERMANENT
    assert result.is_retryable is False
    assert "invalid dimension" in result.error_message.lower()

    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status == KnowledgeFileStatus.FAILED.value
        # Ensure no partial chunks were saved
        chunks = await knowledge_repository.list_by_business(
            db, business_id=biz.id, source_file_id=kfile.id
        )
        assert len(chunks) == 0


@pytest.mark.asyncio
async def test_atomic_rollback_during_finalization():
    """15. Verifies that a failure during batch persistence rolls back the entire transaction."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=MockEmbeddingProvider(),
    )

    # Simulate database batch failure during create_chunks_batch
    with patch.object(
        service._knowledge_repo,
        "create_chunks_batch",
        side_effect=RuntimeError("Simulated database failure"),
    ):
        result = await service.process_file(kfile.id)
        assert result.status in (
            ProcessingResultStatus.FAILED_PERMANENT,
            ProcessingResultStatus.FAILED_TRANSIENT,
        )

    # Verify atomic rollback
    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status != KnowledgeFileStatus.READY.value

        # Zero chunks persisted
        chunks = await knowledge_repository.list_by_business(
            db, business_id=biz.id, source_file_id=kfile.id
        )
        assert len(chunks) == 0


@pytest.mark.asyncio
async def test_tenant_isolation_during_processing():
    """16. Verifies that document processing strictly scopes data to the owning tenant."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Tenant A")
        biz_b = await create_test_business(db, name="Tenant B")
        file_a = await create_test_file(db, biz_a.id, filename="tenant_a.pdf")

    storage = InMemoryStorageProvider()
    await storage.upload(file_a.storage_key, create_multipage_pdf_bytes())

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=MockEmbeddingProvider(),
    )

    result = await service.process_file(file_a.id)
    assert result.status == ProcessingResultStatus.READY

    async with async_session_factory() as db:
        # All chunks belong to Tenant A
        chunks_a = await knowledge_repository.list_by_business(
            db, business_id=biz_a.id, source_file_id=file_a.id
        )
        assert len(chunks_a) > 0
        assert all(c.business_id == biz_a.id for c in chunks_a)

        # Tenant B has zero chunks from Tenant A's file
        chunks_b = await knowledge_repository.list_by_business(
            db, business_id=biz_b.id, source_file_id=file_a.id
        )
        assert len(chunks_b) == 0


@pytest.mark.asyncio
async def test_search_visibility_of_non_ready_files():
    """17. Verifies that search_similar excludes chunks belonging to non-ready files."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Search Visibility Biz")
        vec = create_unit_vector(0)

        # 1. Ready file with chunk
        ready_file = await create_test_file(
            db, biz.id, filename="ready.pdf", processing_status=KnowledgeFileStatus.READY.value
        )
        ready_chunk = await knowledge_repository.create_chunk(
            db=db,
            business_id=biz.id,
            source_file_id=ready_file.id,
            chunk_index=0,
            answer="Ready chunk content",
            embedding=vec,
        )

        # 2. Pending file with chunk
        pending_file = await create_test_file(
            db, biz.id, filename="pending.pdf", processing_status=KnowledgeFileStatus.PENDING.value
        )
        pending_chunk = await knowledge_repository.create_chunk(
            db=db,
            business_id=biz.id,
            source_file_id=pending_file.id,
            chunk_index=0,
            answer="Pending chunk content",
            embedding=vec,
        )

        # 3. Processing file with chunk
        processing_file = await create_test_file(
            db, biz.id, filename="processing.pdf", processing_status=KnowledgeFileStatus.PROCESSING.value
        )
        processing_chunk = await knowledge_repository.create_chunk(
            db=db,
            business_id=biz.id,
            source_file_id=processing_file.id,
            chunk_index=0,
            answer="Processing chunk content",
            embedding=vec,
        )

        # 4. Failed file with chunk
        failed_file = await create_test_file(
            db, biz.id, filename="failed.pdf", processing_status=KnowledgeFileStatus.FAILED.value
        )
        failed_chunk = await knowledge_repository.create_chunk(
            db=db,
            business_id=biz.id,
            source_file_id=failed_file.id,
            chunk_index=0,
            answer="Failed chunk content",
            embedding=vec,
        )

        # 5. Standalone FAQ (source_file_id=None)
        faq = await knowledge_repository.create_faq(
            db=db,
            business_id=biz.id,
            question="FAQ Question",
            answer="FAQ Answer",
            embedding=vec,
        )

        # Execute search_similar
        results = await knowledge_repository.search_similar(
            db=db,
            business_id=biz.id,
            query_vector=vec,
            top_k=10,
        )

        matched_ids = {entry.id for entry, _ in results}

        # Ready chunk and FAQ MUST be visible
        assert ready_chunk.id in matched_ids
        assert faq.id in matched_ids

        # Non-ready chunks MUST NOT be visible
        assert pending_chunk.id not in matched_ids
        assert processing_chunk.id not in matched_ids
        assert failed_chunk.id not in matched_ids


@pytest.mark.asyncio
async def test_real_postgresql_concurrent_claims():
    """18. True PostgreSQL concurrency test: 2 workers claim the same pending file simultaneously."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Postgres Concurrency Biz")
        kfile = await create_test_file(db, biz.id, filename="race.pdf")

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    service1 = DocumentProcessingService(storage_provider=storage, embedding_provider=MockEmbeddingProvider())
    service2 = DocumentProcessingService(storage_provider=storage, embedding_provider=MockEmbeddingProvider())

    # Execute both claims in parallel using asyncio.gather
    results = await asyncio.gather(
        service1.process_file(kfile.id),
        service2.process_file(kfile.id),
    )

    statuses = [r.status for r in results]

    # Exactly one worker must succeed (READY) and exactly one must be rejected (ALREADY_CLAIMED or ALREADY_READY)
    assert statuses.count(ProcessingResultStatus.READY) == 1
    assert statuses.count(ProcessingResultStatus.ALREADY_CLAIMED) + statuses.count(ProcessingResultStatus.ALREADY_READY) == 1


@pytest.mark.asyncio
async def test_document_chunk_batches_use_passage_prefix():
    """19. Verifies that DocumentProcessingService passes prefix=PREFIX_PASSAGE and is_query=False to embed_batch."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Prefix Verification Biz")
        kfile = await create_test_file(db, biz.id, filename="prefix_test.pdf")

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    mock_embed = MockEmbeddingProvider()
    embed_batch_mock = AsyncMock(wraps=mock_embed.embed_batch)
    mock_embed.embed_batch = embed_batch_mock

    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=mock_embed,
    )

    result = await service.process_file(kfile.id)
    assert result.status == ProcessingResultStatus.READY

    assert embed_batch_mock.called
    for call_args in embed_batch_mock.call_args_list:
        args, kwargs = call_args
        prefix_val = kwargs.get("prefix", args[1] if len(args) > 1 else None)
        is_query_val = kwargs.get("is_query", args[2] if len(args) > 2 else False)
        assert prefix_val == PREFIX_PASSAGE
        assert is_query_val is False


@pytest.mark.asyncio
async def test_document_processing_uses_real_e5_tokenizer():
    """20. Verifies that DocumentProcessingService defaults to real E5TokenizerAdapter."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="E5 Tokenizer Default Biz")
        kfile = await create_test_file(db, biz.id, filename="e5_tok_test.pdf")

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    mock_embed = MockEmbeddingProvider()
    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=mock_embed,
    )

    # Verifies lazy resolution gives real E5TokenizerAdapter
    assert isinstance(service.tokenizer, E5TokenizerAdapter)

    result = await service.process_file(kfile.id)
    assert result.status == ProcessingResultStatus.READY
    assert result.chunks_created > 0


@pytest.mark.asyncio
async def test_document_processing_respects_injected_tokenizer():
    """21. Verifies that DocumentProcessingService respects an explicitly injected tokenizer (e.g. MockTokenizer)."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Injected Tokenizer Biz")
        kfile = await create_test_file(db, biz.id, filename="mock_tok_test.pdf")

    storage = InMemoryStorageProvider()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    mock_tok = MockTokenizer()
    mock_embed = MockEmbeddingProvider()
    service = DocumentProcessingService(
        storage_provider=storage,
        embedding_provider=mock_embed,
        tokenizer=mock_tok,
    )

    assert service.tokenizer is mock_tok

    result = await service.process_file(kfile.id)
    assert result.status == ProcessingResultStatus.READY
    assert result.chunks_created > 0

