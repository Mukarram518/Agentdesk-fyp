"""Unit and integration tests for AgentDesk ARQ Document Processing Worker (Phase 5.4E.3).

Verifies:
1. Successful background task execution (status='ready', chunks created).
2. Already-ready file handling (idempotent no-op, no retry).
3. Non-existent file handling (status='not_found', no retry).
4. Actively claimed file handling (status='already_claimed', duplicate prevention, no retry).
5. Lost ownership handling (status='claim_lost', no retry).
6. Retryable transient errors trigger ARQ Retry with exponential backoff (attempt 1, attempt 2).
7. Exhausted retry attempts (attempt 3) terminate without further Retry.
8. Permanent document errors finish without Retry.
9. Unexpected unhandled exceptions trigger Retry until max attempts.
10. Worker lifecycle hooks (startup dependency injection and shutdown resource release).
11. Worker startup failure when database is unreachable.
12. WorkerSettings registration, concurrency, and timeout defaults.
"""

from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, patch
import uuid

from arq.worker import Retry, create_worker
import pytest
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.storage.base import StorageProvider
from app.repositories.knowledge_repository import knowledge_repository
from app.services.document_processing_service import (
    DocumentProcessingResult,
    DocumentProcessingService,
    ProcessingResultStatus,
)
from app.worker.settings import WorkerSettings, shutdown, startup
from app.worker.tasks import (
    BASE_BACKOFF_SECONDS,
    MAX_JOB_TRIES,
    process_knowledge_file,
)
from tests.test_document_extractor import create_multipage_pdf_bytes


# =====================================================================
# In-Memory Storage Helper
# =====================================================================

class InMemoryStorage(StorageProvider):
    def __init__(self) -> None:
        self.files: Dict[str, bytes] = {}

    def validate_key(self, key: str) -> None:
        if not key or ".." in key:
            raise ValueError(f"Invalid key {key}")

    async def upload(self, key: str, data: bytes, overwrite: bool = False) -> str:
        self.files[key] = data
        return key

    async def download(self, key: str) -> bytes:
        if key not in self.files:
            raise FileNotFoundError(f"Key {key} not found")
        return self.files[key]

    async def delete(self, key: str) -> bool:
        return self.files.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        return key in self.files


async def create_test_business(db) -> Business:
    biz = Business(
        name="ARQ Test Business",
        slug=f"arq-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


async def create_test_file(
    db,
    business_id: uuid.UUID,
    filename: str = "doc.pdf",
    processing_status: str = KnowledgeFileStatus.PENDING.value,
    error_message: Optional[str] = None,
    processing_token: Optional[str] = None,
) -> KnowledgeFile:
    kfile = KnowledgeFile(
        business_id=business_id,
        filename=filename,
        storage_key=f"business/{business_id}/knowledge/{uuid.uuid4()}/{filename}",
        mime_type="application/pdf",
        size_bytes=1024,
        processing_status=processing_status,
        error_message=error_message,
        processing_token=processing_token,
    )
    db.add(kfile)
    await db.commit()
    await db.refresh(kfile)
    return kfile


# =====================================================================
# Tests: Task Execution and Status Outcomes
# =====================================================================

@pytest.mark.asyncio
async def test_process_knowledge_file_success():
    """1. Verifies successful background task processing via ARQ task handler."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

    storage = InMemoryStorage()
    await storage.upload(kfile.storage_key, create_multipage_pdf_bytes())

    ctx = {
        "job_id": "test_job_1",
        "job_try": 1,
        "storage_provider": storage,
        "embedding_provider": MockEmbeddingProvider(),
        "session_factory": async_session_factory,
    }

    result = await process_knowledge_file(ctx, kfile.id)

    assert result["status"] == "ready"
    assert result["file_id"] == str(kfile.id)
    assert result["business_id"] == str(biz.id)
    assert result["chunks_created"] > 0

    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.id == kfile.id)
        refreshed = (await db.execute(stmt)).scalar_one()
        assert refreshed.processing_status == KnowledgeFileStatus.READY.value
        assert refreshed.processing_token is None


@pytest.mark.asyncio
async def test_process_knowledge_file_already_ready():
    """2. Verifies already-ready files return already_ready without re-processing or retry."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(
            db, biz.id, processing_status=KnowledgeFileStatus.READY.value
        )

    ctx = {"job_id": "test_job_2", "job_try": 1}
    result = await process_knowledge_file(ctx, kfile.id)

    assert result["status"] == "already_ready"
    assert result["file_id"] == str(kfile.id)


@pytest.mark.asyncio
async def test_process_knowledge_file_not_found():
    """3. Verifies non-existent file IDs terminate with not_found without retry."""
    missing_id = uuid.uuid4()
    ctx = {"job_id": "test_job_3", "job_try": 1}

    result = await process_knowledge_file(ctx, missing_id)

    assert result["status"] == "not_found"
    assert result["file_id"] == str(missing_id)


@pytest.mark.asyncio
async def test_process_knowledge_file_already_claimed():
    """4. Verifies actively claimed files terminate with already_claimed without retry."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(
            db,
            biz.id,
            processing_status=KnowledgeFileStatus.PROCESSING.value,
            processing_token="other_active_token",
        )

    ctx = {"job_id": "test_job_4", "job_try": 1}
    result = await process_knowledge_file(ctx, kfile.id)

    assert result["status"] == "already_claimed"
    assert result["file_id"] == str(kfile.id)


@pytest.mark.asyncio
async def test_process_knowledge_file_claim_lost():
    """5. Verifies claim loss terminates with claim_lost without retrying."""
    dummy_file_id = uuid.uuid4()
    ctx = {"job_id": "test_job_5", "job_try": 1}

    with patch.object(
        DocumentProcessingService,
        "process_file",
        return_value=DocumentProcessingResult(
            status=ProcessingResultStatus.CLAIM_LOST,
            file_id=dummy_file_id,
            error_message="Worker lost processing lease.",
        ),
    ):
        result = await process_knowledge_file(ctx, dummy_file_id)
        assert result["status"] == "claim_lost"
        assert result["file_id"] == str(dummy_file_id)


# =====================================================================
# Tests: Retry Policy & Failure Handling
# =====================================================================

@pytest.mark.asyncio
async def test_process_knowledge_file_transient_error_triggers_retry():
    """6. Verifies transient infrastructure errors trigger ARQ Retry with exponential backoff."""
    dummy_file_id = uuid.uuid4()

    with patch.object(
        DocumentProcessingService,
        "process_file",
        return_value=DocumentProcessingResult(
            status=ProcessingResultStatus.FAILED_TRANSIENT,
            file_id=dummy_file_id,
            error_message="Temporary network timeout",
            is_retryable=True,
        ),
    ):
        # Attempt 1: backoff = 5 * 2^0 = 5s (5000 ms)
        ctx_try_1 = {"job_id": "test_retry_1", "job_try": 1}
        with pytest.raises(Retry) as exc_info_1:
            await process_knowledge_file(ctx_try_1, dummy_file_id)
        assert exc_info_1.value.defer_score == 5000

        # Attempt 2: backoff = 5 * 2^1 = 10s (10000 ms)
        ctx_try_2 = {"job_id": "test_retry_2", "job_try": 2}
        with pytest.raises(Retry) as exc_info_2:
            await process_knowledge_file(ctx_try_2, dummy_file_id)
        assert exc_info_2.value.defer_score == 10000


@pytest.mark.asyncio
async def test_process_knowledge_file_exhausted_retries():
    """7. Verifies that reaching MAX_JOB_TRIES terminates without raising Retry."""
    dummy_file_id = uuid.uuid4()

    with patch.object(
        DocumentProcessingService,
        "process_file",
        return_value=DocumentProcessingResult(
            status=ProcessingResultStatus.FAILED_TRANSIENT,
            file_id=dummy_file_id,
            error_message="Repeated timeout",
            is_retryable=True,
        ),
    ):
        ctx_max = {"job_id": "test_retry_max", "job_try": MAX_JOB_TRIES}
        result = await process_knowledge_file(ctx_max, dummy_file_id)

        assert result["status"] == "failed_transient_max_retries"
        assert result["file_id"] == str(dummy_file_id)
        assert result["error"] == "Repeated timeout"


@pytest.mark.asyncio
async def test_process_knowledge_file_permanent_error_no_retry():
    """8. Verifies permanent document errors terminate without raising Retry."""
    dummy_file_id = uuid.uuid4()

    with patch.object(
        DocumentProcessingService,
        "process_file",
        return_value=DocumentProcessingResult(
            status=ProcessingResultStatus.FAILED_PERMANENT,
            file_id=dummy_file_id,
            error_message="Unsupported document format.",
            is_retryable=False,
        ),
    ):
        ctx = {"job_id": "test_perm", "job_try": 1}
        result = await process_knowledge_file(ctx, dummy_file_id)

        assert result["status"] == "failed_permanent"
        assert result["file_id"] == str(dummy_file_id)
        assert result["error"] == "Unsupported document format."


@pytest.mark.asyncio
async def test_process_knowledge_file_unexpected_exception_triggers_retry():
    """9. Verifies unexpected system exceptions are caught and retried if job_try < max."""
    dummy_file_id = uuid.uuid4()

    with patch.object(
        DocumentProcessingService,
        "process_file",
        side_effect=RuntimeError("Unexpected unhandled crash"),
    ):
        # Attempt 1 -> triggers Retry
        ctx_try_1 = {"job_id": "crash_1", "job_try": 1}
        with pytest.raises(Retry) as exc_info:
            await process_knowledge_file(ctx_try_1, dummy_file_id)
        assert exc_info.value.defer_score == 5000

        # Attempt 3 (max) -> terminates cleanly without raising
        ctx_try_3 = {"job_id": "crash_3", "job_try": 3}
        result = await process_knowledge_file(ctx_try_3, dummy_file_id)
        assert result["status"] == "failed_unexpected"


# =====================================================================
# Tests: Worker Lifecycle and Settings
# =====================================================================

@pytest.mark.asyncio
async def test_worker_startup_and_shutdown_lifecycle():
    """10. Verifies worker startup initializes dependencies and shutdown cleans them up."""
    ctx: Dict[str, Any] = {}

    await startup(ctx)

    assert "session_factory" in ctx
    assert "storage_provider" in ctx
    assert "embedding_provider" in ctx
    assert ctx["session_factory"] == async_session_factory

    await shutdown(ctx)
    assert len(ctx) == 0


@pytest.mark.asyncio
async def test_worker_startup_fails_when_database_unhealthy():
    """11. Verifies that worker startup aborts explicitly if database check fails."""
    ctx: Dict[str, Any] = {}

    with patch(
        "app.worker.settings.check_database_health",
        return_value={"status": "unhealthy", "error": "Connection refused"},
    ):
        with pytest.raises(RuntimeError, match="Database is unavailable for ARQ worker"):
            await startup(ctx)


def test_workersettings_configuration_and_instantiation():
    """12. Verifies WorkerSettings exports correct parameters and instantiates ARQ Worker."""
    assert WorkerSettings.functions == [process_knowledge_file]
    assert WorkerSettings.max_jobs == 2
    assert WorkerSettings.job_timeout == 300
    assert WorkerSettings.max_tries == 3
    assert WorkerSettings.on_startup == startup
    assert WorkerSettings.on_shutdown == shutdown

    # Test full ARQ Worker instantiation
    worker = create_worker(WorkerSettings)
    assert worker is not None
    assert "process_knowledge_file" in worker.functions
    assert worker.functions["process_knowledge_file"].coroutine == process_knowledge_file
