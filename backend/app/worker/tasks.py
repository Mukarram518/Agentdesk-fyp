"""AgentDesk ARQ Worker Tasks for Document Processing (Phase 5.4E.3).

Defines background tasks executed by the ARQ worker process:
- process_knowledge_file: Coordinates end-to-end background extraction, chunking,
  embedding generation, and storage persistence for uploaded knowledge documents.
- Explicit retry handling using ARQ's Retry mechanism with exponential backoff for transient errors.
- Strict non-retry of permanent document errors (unsupported formats, corruption, etc.).
"""

from typing import Any, Dict, Optional, Union
import uuid

from arq.worker import Retry

from app.core.database import async_session_factory
from app.core.logging import logger
from app.providers.embeddings import get_embedding_provider
from app.providers.storage import get_storage_provider
from app.repositories.knowledge_file_repository import knowledge_file_repository
from app.repositories.knowledge_repository import knowledge_repository
from app.services.document_processing_service import (
    DocumentProcessingResult,
    DocumentProcessingService,
    ProcessingResultStatus,
)

MAX_JOB_TRIES: int = 3
BASE_BACKOFF_SECONDS: int = 5


async def process_knowledge_file(
    ctx: Dict[str, Any],
    file_id: Union[str, uuid.UUID],
) -> Dict[str, Any]:
    """ARQ background task executing document extraction, chunking, and vector embedding.

    Guarantees:
    - Accepts file UUID (string or uuid.UUID).
    - Derives business ownership strictly from database records (zero untrusted arguments).
    - Uses shared worker dependencies from `ctx` when available, with safe singleton fallbacks.
    - Finishes cleanly without retry for SUCCESS, ALREADY_READY, NOT_FOUND, or CLAIM_LOST.
    - Distinguishes retryable infrastructure errors (using ARQ Retry) from permanent document failures.
    - Enforces maximum attempt limits based on `ctx['job_try']`.
    - Never leaks internal stack traces, system paths, or secrets to logs or output dicts.

    Args:
        ctx: ARQ worker execution context containing job metadata and shared dependencies.
        file_id: Primary key of the KnowledgeFile to process.

    Returns:
        Structured outcome dictionary describing execution status.

    Raises:
        Retry: When a transient infrastructure error occurs and `job_try < MAX_JOB_TRIES`.
    """
    job_id = ctx.get("job_id", "local")
    job_try = ctx.get("job_try", 1)
    logger.info(f"ARQ task process_knowledge_file started for file {file_id} (job_id={job_id}, try={job_try})")

    # Resolve dependencies from context or fall back to application defaults
    session_factory = ctx.get("session_factory") or async_session_factory
    storage_provider = ctx.get("storage_provider") or get_storage_provider()
    embedding_provider = ctx.get("embedding_provider") or get_embedding_provider()
    file_repo = ctx.get("knowledge_file_repo") or knowledge_file_repository
    knowledge_repo = ctx.get("knowledge_repo") or knowledge_repository
    tokenizer = ctx.get("tokenizer")

    service = DocumentProcessingService(
        session_factory=session_factory,
        storage_provider=storage_provider,
        embedding_provider=embedding_provider,
        knowledge_file_repo=file_repo,
        knowledge_repo=knowledge_repo,
        tokenizer=tokenizer,
    )

    try:
        result: DocumentProcessingResult = await service.process_file(file_id=file_id)

        # 1. Success
        if result.status == ProcessingResultStatus.READY:
            logger.info(
                f"ARQ task successfully processed file {file_id}: "
                f"{result.chunks_created} chunks created for business {result.business_id}."
            )
            return {
                "status": "ready",
                "file_id": str(file_id),
                "business_id": str(result.business_id) if result.business_id else None,
                "chunks_created": result.chunks_created,
            }

        # 2. Already processed (Idempotent no-op)
        if result.status == ProcessingResultStatus.ALREADY_READY:
            logger.info(f"ARQ task: file {file_id} is already in ready status. Skipping without retry.")
            return {
                "status": "already_ready",
                "file_id": str(file_id),
            }

        # 3. File not found / deleted
        if result.status == ProcessingResultStatus.NOT_FOUND:
            logger.warning(f"ARQ task: file {file_id} not found in database. Skipping without retry.")
            return {
                "status": "not_found",
                "file_id": str(file_id),
            }

        # 4. Already claimed by another active worker
        if result.status == ProcessingResultStatus.ALREADY_CLAIMED:
            logger.info(
                f"ARQ task: file {file_id} is actively claimed by another worker process. Skipping duplicate run."
            )
            return {
                "status": "already_claimed",
                "file_id": str(file_id),
            }

        # 5. Claim lost during processing
        if result.status == ProcessingResultStatus.CLAIM_LOST:
            logger.warning(
                f"ARQ task: worker lost lease ownership for file {file_id}. Aborting without retry."
            )
            return {
                "status": "claim_lost",
                "file_id": str(file_id),
                "error": result.error_message,
            }

        # 6. Permanent document failure (unsupported type, corrupt file, blank text) -> Do NOT retry
        if result.status == ProcessingResultStatus.FAILED_PERMANENT:
            logger.warning(
                f"ARQ task: file {file_id} failed permanently: {result.error_message}. Not retrying."
            )
            return {
                "status": "failed_permanent",
                "file_id": str(file_id),
                "error": result.error_message,
            }

        # 7. Transient infrastructure failure -> Evaluate retry eligibility
        if result.status == ProcessingResultStatus.FAILED_TRANSIENT:
            if job_try < MAX_JOB_TRIES:
                defer_seconds = BASE_BACKOFF_SECONDS * (2 ** (job_try - 1))
                logger.warning(
                    f"ARQ task: file {file_id} encountered transient error: {result.error_message}. "
                    f"Retrying (attempt {job_try}/{MAX_JOB_TRIES}) in {defer_seconds}s."
                )
                raise Retry(defer=defer_seconds)
            else:
                logger.error(
                    f"ARQ task: file {file_id} exhausted maximum retry attempts ({MAX_JOB_TRIES}). "
                    f"Last error: {result.error_message}."
                )
                return {
                    "status": "failed_transient_max_retries",
                    "file_id": str(file_id),
                    "error": result.error_message,
                }

        # Fallback for unexpected status
        return {
            "status": str(result.status.value),
            "file_id": str(file_id),
            "error": result.error_message,
        }

    except Retry:
        # Re-raise ARQ Retry exceptions directly so the worker runtime handles rescheduling
        raise
    except Exception as exc:
        logger.exception(f"Unexpected unhandled exception in ARQ task process_knowledge_file for file {file_id}: {exc}")
        if job_try < MAX_JOB_TRIES:
            defer_seconds = BASE_BACKOFF_SECONDS * (2 ** (job_try - 1))
            raise Retry(defer=defer_seconds) from exc
        return {
            "status": "failed_unexpected",
            "file_id": str(file_id),
            "error": "An unexpected error occurred while processing the document.",
        }

