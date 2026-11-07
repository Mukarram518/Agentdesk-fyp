"""AgentDesk Document Processing Service (Phase 5.4E.2).

Orchestrates the background processing lifecycle for uploaded knowledge documents:
1. Atomic, database-backed claim ownership using dedicated processing_token and lease timeouts.
2. Background lease heartbeat mechanism preventing active worker lease expiration.
3. Safe out-of-transaction document downloading, text extraction, chunking, and vector embedding.
4. Strict vector dimension validation (384 dimensions for AgentDesk pgvector schema).
5. Row-locked (SELECT FOR UPDATE) atomic finalization and failure handling.
6. Robust error classification separating permanent document failures from transient infrastructure errors.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import enum
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import uuid

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.logging import logger
from app.models.knowledge import ACTIVE_EMBEDDING_MODEL, EMBEDDING_VECTOR_DIMENSION
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus
from app.providers.embeddings import (
    EmbeddingProvider,
    PREFIX_PASSAGE,
    get_embedding_provider,
)
from app.providers.storage import StorageProvider, get_storage_provider
from app.repositories.knowledge_file_repository import (
    KnowledgeFileRepository,
    knowledge_file_repository,
)
from app.repositories.knowledge_repository import (
    KnowledgeRepository,
    knowledge_repository,
)
from app.services.document_chunker import (
    ChunkingError,
    TokenLimitExceededError,
    Tokenizer,
    TokenizerError,
    chunk_document,
    get_e5_tokenizer,
)
from app.services.document_extractor import (
    CorruptedDocumentError,
    DocumentExtractionError,
    EmptyDocumentError,
    NoExtractableTextError,
    UnsupportedDocumentTypeError,
    extract_document_text,
)


class ProcessingResultStatus(str, enum.Enum):
    """Outcome status for a document processing attempt."""
    READY = "ready"
    ALREADY_READY = "already_ready"
    NOT_FOUND = "not_found"
    ALREADY_CLAIMED = "already_claimed"
    CLAIM_LOST = "claim_lost"
    FAILED_PERMANENT = "failed_permanent"
    FAILED_TRANSIENT = "failed_transient"


@dataclass(frozen=True)
class DocumentProcessingResult:
    """Structured result returned by DocumentProcessingService.process_file()."""
    status: ProcessingResultStatus
    file_id: uuid.UUID
    business_id: Optional[uuid.UUID] = None
    chunks_created: int = 0
    error_message: Optional[str] = None
    is_retryable: bool = False


@dataclass(frozen=True)
class ClaimData:
    """Internal ownership token and metadata returned by a successful atomic claim."""
    file_id: uuid.UUID
    business_id: uuid.UUID
    storage_key: str
    filename: str
    mime_type: str
    claim_token: str


class InvalidVectorDimensionError(Exception):
    """Raised when generated embedding vectors do not match EMBEDDING_VECTOR_DIMENSION."""


def classify_processing_error(exc: Exception) -> Tuple[str, bool]:
    """Classifies an exception into a sanitized, user-friendly error message and retry flag.

    Guarantees:
    - Never exposes stack traces, credentials, internal file paths, or raw SQL errors.
    - Categorizes permanent document errors as non-retryable (is_retryable=False).
    - Categorizes transient I/O and network errors as retryable (is_retryable=True).
    """
    # 1. Permanent Document Errors (Non-retryable)
    if isinstance(exc, UnsupportedDocumentTypeError):
        return ("The document format is unsupported. Only PDF and DOCX files are allowed.", False)
    if isinstance(exc, EmptyDocumentError):
        return ("The document file is empty and contains no readable data.", False)
    if isinstance(exc, NoExtractableTextError):
        return ("No readable text could be found in the document.", False)
    if isinstance(exc, CorruptedDocumentError):
        return ("The document is corrupt, malformed, or password-protected.", False)
    if isinstance(exc, TokenLimitExceededError):
        return ("The document contains text units that exceed the allowable length limit.", False)
    if isinstance(exc, DocumentExtractionError):
        return ("Document extraction failed due to invalid content or exceeding the size limit.", False)
    if isinstance(exc, (ChunkingError, TokenizerError)):
        return ("The document could not be segmented into knowledge chunks.", False)
    if isinstance(exc, InvalidVectorDimensionError):
        return ("Vector embeddings produced an invalid dimension.", False)

    # 2. Transient Infrastructure Errors (Retryable)
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return ("A temporary network or storage timeout occurred while processing the document.", True)
    if isinstance(exc, OSError):
        return ("A temporary storage system error occurred while retrieving the document.", True)

    # 3. Generic / Unexpected Errors (Sanitized)
    return ("An unexpected error occurred while processing the document. Please try again or contact support.", False)


class DocumentProcessingService:
    """Service coordinating end-to-end processing of uploaded knowledge documents."""

    def __init__(
        self,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
        storage_provider: Optional[StorageProvider] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        knowledge_file_repo: Optional[KnowledgeFileRepository] = None,
        knowledge_repo: Optional[KnowledgeRepository] = None,
        tokenizer: Optional[Tokenizer] = None,
        stale_claim_timeout_seconds: int = 300,
        heartbeat_interval_seconds: float = 30.0,
    ) -> None:
        self._session_factory = session_factory or async_session_factory
        self._storage_provider = storage_provider or get_storage_provider()
        self._embedding_provider = embedding_provider or get_embedding_provider()
        self._file_repo = knowledge_file_repo or knowledge_file_repository
        self._knowledge_repo = knowledge_repo or knowledge_repository
        self._tokenizer = tokenizer
        self._stale_claim_timeout_seconds = stale_claim_timeout_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds

    @property
    def tokenizer(self) -> Tokenizer:
        """Returns the configured tokenizer, lazily resolving cached E5 tokenizer singleton if not injected."""
        if self._tokenizer is None:
            self._tokenizer = get_e5_tokenizer()
        return self._tokenizer

    async def refresh_lease(self, file_id: uuid.UUID, claim_token: str) -> bool:
        """Heartbeat update extending lease expiration while processing.

        Guarantees:
        - Atomically touches updated_at = func.now().
        - Requires exact match on file_id, processing_token, and processing status.
        - Returns True if refreshed; False if worker lost ownership.
        """
        async with self._session_factory() as session:
            stmt = (
                update(KnowledgeFile)
                .where(
                    KnowledgeFile.id == file_id,
                    KnowledgeFile.processing_status == KnowledgeFileStatus.PROCESSING.value,
                    KnowledgeFile.processing_token == claim_token,
                )
                .values(
                    updated_at=func.now(),
                )
            )
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def _claim_file(self, file_id: uuid.UUID) -> Tuple[ProcessingResultStatus, Optional[ClaimData]]:
        """Transaction A: Atomically attempts to claim a KnowledgeFile for processing.

        Guarantees:
        - Checks file existence and derives business_id strictly from the database record.
        - Returns ALREADY_READY for already-ready files without modifying state.
        - Prevents concurrent workers from claiming the same active file.
        - Permits reclaiming stale processing claims exceeding stale_claim_timeout_seconds.
        - Sets dedicated processing_token and processing_started_at without polluting error_message.
        """
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(seconds=self._stale_claim_timeout_seconds)

        async with self._session_factory() as session:
            # 1. Inspect current file record
            stmt = select(KnowledgeFile).where(KnowledgeFile.id == file_id)
            result = await session.execute(stmt)
            kfile = result.scalar_one_or_none()

            if not kfile:
                return (ProcessingResultStatus.NOT_FOUND, None)

            # Idempotent no-op for already-ready files
            if kfile.processing_status == KnowledgeFileStatus.READY.value:
                return (ProcessingResultStatus.ALREADY_READY, None)

            # Check if actively claimed by another worker (not stale)
            if kfile.processing_status == KnowledgeFileStatus.PROCESSING.value:
                file_updated_at = kfile.updated_at
                if file_updated_at.tzinfo is None:
                    file_updated_at = file_updated_at.replace(tzinfo=timezone.utc)
                if file_updated_at >= stale_cutoff:
                    return (ProcessingResultStatus.ALREADY_CLAIMED, None)

            # 2. Atomic conditional claim using dedicated processing_token
            claim_token = uuid.uuid4().hex
            claim_stmt = (
                update(KnowledgeFile)
                .where(
                    KnowledgeFile.id == file_id,
                    or_(
                        KnowledgeFile.processing_status == KnowledgeFileStatus.PENDING.value,
                        KnowledgeFile.processing_status == KnowledgeFileStatus.FAILED.value,
                        and_(
                            KnowledgeFile.processing_status == KnowledgeFileStatus.PROCESSING.value,
                            KnowledgeFile.updated_at < stale_cutoff,
                        ),
                    ),
                )
                .values(
                    processing_status=KnowledgeFileStatus.PROCESSING.value,
                    processing_token=claim_token,
                    processing_started_at=func.now(),
                    updated_at=func.now(),
                )
                .returning(
                    KnowledgeFile.id,
                    KnowledgeFile.business_id,
                    KnowledgeFile.storage_key,
                    KnowledgeFile.filename,
                    KnowledgeFile.mime_type,
                )
            )

            res = await session.execute(claim_stmt)
            row = res.first()

            if not row:
                # Concurrently claimed by another worker
                await session.rollback()
                return (ProcessingResultStatus.ALREADY_CLAIMED, None)

            await session.commit()
            return (
                ProcessingResultStatus.READY,
                ClaimData(
                    file_id=row.id,
                    business_id=row.business_id,
                    storage_key=row.storage_key,
                    filename=row.filename,
                    mime_type=row.mime_type,
                    claim_token=claim_token,
                ),
            )

    async def _finalize_success(
        self,
        claim_data: ClaimData,
        chunk_result: Any,
        embeddings: List[List[float]],
    ) -> DocumentProcessingResult:
        """Transaction B: Row-locks the file with FOR UPDATE, verifies ownership, replaces chunks, and marks file READY."""
        async with self._session_factory() as session:
            try:
                # 1. Row-level lock and verify claim ownership
                verify_stmt = (
                    select(KnowledgeFile)
                    .where(
                        KnowledgeFile.id == claim_data.file_id,
                        KnowledgeFile.business_id == claim_data.business_id,
                        KnowledgeFile.processing_status == KnowledgeFileStatus.PROCESSING.value,
                        KnowledgeFile.processing_token == claim_data.claim_token,
                    )
                    .with_for_update()
                )
                kfile = (await session.execute(verify_stmt)).scalar_one_or_none()
                if not kfile:
                    await session.rollback()
                    logger.warning(
                        f"Finalization rejected: Worker lost claim for file {claim_data.file_id}."
                    )
                    return DocumentProcessingResult(
                        status=ProcessingResultStatus.CLAIM_LOST,
                        file_id=claim_data.file_id,
                        business_id=claim_data.business_id,
                        error_message="Worker lost processing claim before finalization.",
                    )

                # 2. Replace any existing chunks with tenant-scoped delete
                await self._knowledge_repo.delete_by_source_file(
                    db=session,
                    business_id=claim_data.business_id,
                    source_file_id=claim_data.file_id,
                )

                # 3. Batch insert new chunks with verified embeddings
                active_model = getattr(self._embedding_provider, "model_name", ACTIVE_EMBEDDING_MODEL)
                chunks_data = []
                for chunk, vec in zip(chunk_result.chunks, embeddings):
                    chunk_dict = chunk.to_repository_dict()
                    chunk_dict["embedding"] = vec
                    chunk_dict["embedding_stale"] = False
                    chunk_dict["embedding_model"] = active_model
                    chunks_data.append(chunk_dict)

                await self._knowledge_repo.create_chunks_batch(
                    db=session,
                    business_id=claim_data.business_id,
                    chunks_data=chunks_data,
                )

                # 4. Update file status to READY, clear processing token, and commit
                kfile.processing_status = KnowledgeFileStatus.READY.value
                kfile.processing_token = None
                kfile.processing_started_at = None
                kfile.error_message = None
                kfile.updated_at = func.now()

                await session.commit()
                return DocumentProcessingResult(
                    status=ProcessingResultStatus.READY,
                    file_id=claim_data.file_id,
                    business_id=claim_data.business_id,
                    chunks_created=len(chunks_data),
                )
            except Exception as exc:
                await session.rollback()
                logger.exception(f"Transaction B rollback during finalization for {claim_data.file_id}: {exc}")
                raise

    async def _handle_failure(
        self,
        claim_data: ClaimData,
        exc: Exception,
    ) -> DocumentProcessingResult:
        """Transaction C: Row-locks file, verifies claim, purges chunks, and records FAILED."""
        sanitized_msg, is_retryable = classify_processing_error(exc)
        logger.warning(
            f"Document processing failed for file {claim_data.file_id}: {sanitized_msg} "
            f"(retryable={is_retryable}, exc={type(exc).__name__}: {exc})"
        )

        async with self._session_factory() as session:
            try:
                # 1. Row-level lock and verify worker still owns claim
                verify_stmt = (
                    select(KnowledgeFile)
                    .where(
                        KnowledgeFile.id == claim_data.file_id,
                        KnowledgeFile.business_id == claim_data.business_id,
                        KnowledgeFile.processing_status == KnowledgeFileStatus.PROCESSING.value,
                        KnowledgeFile.processing_token == claim_data.claim_token,
                    )
                    .with_for_update()
                )
                kfile = (await session.execute(verify_stmt)).scalar_one_or_none()
                if not kfile:
                    await session.rollback()
                    logger.warning(
                        f"Cannot record failure for file {claim_data.file_id}: worker lost claim."
                    )
                    return DocumentProcessingResult(
                        status=ProcessingResultStatus.CLAIM_LOST,
                        file_id=claim_data.file_id,
                        business_id=claim_data.business_id,
                        error_message="Worker lost claim before failure status could be recorded.",
                        is_retryable=False,
                    )

                # 2. Purge any old chunks so failed reprocessing never leaves stale chunks visible
                await self._knowledge_repo.delete_by_source_file(
                    db=session,
                    business_id=claim_data.business_id,
                    source_file_id=claim_data.file_id,
                )

                # 3. Mark file FAILED with sanitized message and clear processing_token
                kfile.processing_status = KnowledgeFileStatus.FAILED.value
                kfile.processing_token = None
                kfile.error_message = sanitized_msg
                kfile.updated_at = func.now()

                await session.commit()

                return DocumentProcessingResult(
                    status=(
                        ProcessingResultStatus.FAILED_TRANSIENT
                        if is_retryable
                        else ProcessingResultStatus.FAILED_PERMANENT
                    ),
                    file_id=claim_data.file_id,
                    business_id=claim_data.business_id,
                    error_message=sanitized_msg,
                    is_retryable=is_retryable,
                )
            except Exception as fail_exc:
                await session.rollback()
                logger.exception(
                    f"Failed to record failure status in Transaction C for {claim_data.file_id}: {fail_exc}"
                )
                raise

    async def process_file(
        self,
        file_id: Union[str, uuid.UUID],
    ) -> DocumentProcessingResult:
        """Executes the complete processing lifecycle for a KnowledgeFile.

        Guarantees:
        - Atomic claiming in Transaction A with dedicated token.
        - Background lease heartbeat maintaining ownership during long I/O.
        - Heavy I/O (download, extract, chunk, embed) executed outside database transactions.
        - Strict 384-dimension vector verification.
        - Row-locked (SELECT FOR UPDATE) atomic finalization in Transaction B.
        - Concurrency-safe rollback on lost ownership.
        """
        # Parse file_id
        if isinstance(file_id, str):
            try:
                parsed_id = uuid.UUID(file_id)
            except ValueError:
                return DocumentProcessingResult(
                    status=ProcessingResultStatus.NOT_FOUND,
                    file_id=uuid.uuid4(),
                    error_message="Invalid UUID format for file_id.",
                )
        else:
            parsed_id = file_id

        # Transaction A: Claim
        claim_status, claim_data = await self._claim_file(parsed_id)
        if claim_status != ProcessingResultStatus.READY or claim_data is None:
            return DocumentProcessingResult(
                status=claim_status,
                file_id=parsed_id,
            )

        # Start lease heartbeat background task
        heartbeat_stop = asyncio.Event()
        lost_ownership = asyncio.Event()

        async def _heartbeat_loop():
            while not heartbeat_stop.is_set():
                try:
                    await asyncio.sleep(self._heartbeat_interval_seconds)
                    if heartbeat_stop.is_set():
                        break
                    refreshed = await self.refresh_lease(claim_data.file_id, claim_data.claim_token)
                    if not refreshed:
                        logger.warning(f"Heartbeat failed: Worker lost ownership for file {claim_data.file_id}.")
                        lost_ownership.set()
                        break
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning(f"Heartbeat error for file {claim_data.file_id}: {exc}")

        heartbeat_task = asyncio.create_task(_heartbeat_loop())

        # Outside DB Transactions: Download, Extract, Chunk, Embed
        try:
            # 1. Download raw file bytes
            raw_bytes = await self._storage_provider.download(claim_data.storage_key)

            if lost_ownership.is_set():
                return DocumentProcessingResult(
                    status=ProcessingResultStatus.CLAIM_LOST,
                    file_id=claim_data.file_id,
                    business_id=claim_data.business_id,
                    error_message="Worker lost processing lease during download.",
                )

            # 2. Extract normalized document text
            file_ext = Path(claim_data.filename).suffix or claim_data.mime_type
            extracted_doc = extract_document_text(data=raw_bytes, file_type=file_ext)

            # 3. Chunk extracted document
            chunk_result = chunk_document(
                document=extracted_doc,
                source_file_id=claim_data.file_id,
                tokenizer=self.tokenizer,
            )
            if chunk_result.total_chunks == 0:
                raise NoExtractableTextError("No extractable chunks found in document.")

            if lost_ownership.is_set():
                return DocumentProcessingResult(
                    status=ProcessingResultStatus.CLAIM_LOST,
                    file_id=claim_data.file_id,
                    business_id=claim_data.business_id,
                    error_message="Worker lost processing lease during chunking.",
                )

            # 4. Generate embeddings via provider abstraction with passage prefix
            chunk_texts = [c.text for c in chunk_result.chunks]
            embeddings = await self._embedding_provider.embed_batch(
                chunk_texts,
                prefix=PREFIX_PASSAGE,
                is_query=False,
            )

            # 5. Strict dimension and integrity verification
            if len(embeddings) != len(chunk_result.chunks):
                raise InvalidVectorDimensionError(
                    f"Generated embeddings count ({len(embeddings)}) does not match chunk count ({len(chunk_result.chunks)})."
                )

            for idx, vec in enumerate(embeddings):
                if not isinstance(vec, (list, tuple)) or len(vec) != EMBEDDING_VECTOR_DIMENSION:
                    raise InvalidVectorDimensionError(
                        f"Vector at index {idx} has invalid dimension {len(vec) if isinstance(vec, (list, tuple)) else 'non-sequence'}; "
                        f"expected {EMBEDDING_VECTOR_DIMENSION}."
                    )

            if lost_ownership.is_set():
                return DocumentProcessingResult(
                    status=ProcessingResultStatus.CLAIM_LOST,
                    file_id=claim_data.file_id,
                    business_id=claim_data.business_id,
                    error_message="Worker lost processing lease during embedding.",
                )

            # Transaction B: Finalize
            return await self._finalize_success(claim_data, chunk_result, embeddings)

        except Exception as exc:
            # Transaction C: Record Failure
            try:
                return await self._handle_failure(claim_data, exc)
            except Exception:
                # If Transaction C itself failed to commit, return transient failure
                return DocumentProcessingResult(
                    status=ProcessingResultStatus.FAILED_TRANSIENT,
                    file_id=claim_data.file_id,
                    business_id=claim_data.business_id,
                    error_message="Failed to persist document processing failure state.",
                    is_retryable=True,
                )
        finally:
            heartbeat_stop.set()
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
