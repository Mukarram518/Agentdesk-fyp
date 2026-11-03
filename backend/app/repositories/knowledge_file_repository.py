"""KnowledgeFile database repository for document upload metadata and lifecycle."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus


class KnowledgeFileRepository:
    """Repository handling persistence operations for KnowledgeFile entities."""

    async def create_file(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        filename: str,
        storage_key: str,
        mime_type: str,
        size_bytes: int,
        processing_status: str = KnowledgeFileStatus.PENDING.value,
        error_message: Optional[str] = None,
    ) -> KnowledgeFile:
        """Creates and flushes a new knowledge file record without committing."""
        kfile = KnowledgeFile(
            business_id=business_id,
            filename=filename.strip(),
            storage_key=storage_key.strip(),
            mime_type=mime_type.strip().lower(),
            size_bytes=size_bytes,
            processing_status=processing_status,
            error_message=error_message,
        )
        db.add(kfile)
        await db.flush()
        return kfile

    async def get_by_id(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        file_id: uuid.UUID,
    ) -> Optional[KnowledgeFile]:
        """Fetches a knowledge file by primary key strictly scoped to the tenant."""
        stmt = select(KnowledgeFile).where(
            KnowledgeFile.id == file_id,
            KnowledgeFile.business_id == business_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_business(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[KnowledgeFile]:
        """Retrieves paginated knowledge files for a business, ordered newest first."""
        stmt = (
            select(KnowledgeFile)
            .where(KnowledgeFile.business_id == business_id)
            .order_by(KnowledgeFile.created_at.desc())
        )
        if status:
            stmt = stmt.where(KnowledgeFile.processing_status == status)
        if limit > 0:
            stmt = stmt.limit(limit)
        if offset > 0:
            stmt = stmt.offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        file_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[KnowledgeFile]:
        """Updates file processing status and error message within tenant scope.

        Returns None if the file does not belong to the supplied business.
        """
        kfile = await self.get_by_id(db, business_id=business_id, file_id=file_id)
        if not kfile:
            return None

        kfile.processing_status = status
        kfile.error_message = error_message
        await db.flush()
        return kfile

    async def delete_file(
        self,
        db: AsyncSession,
        business_id: uuid.UUID,
        file_id: uuid.UUID,
    ) -> bool:
        """Deletes a file record strictly within tenant scope (cascades to chunks).

        Returns True if deleted, False if file was not found for the business.
        """
        kfile = await self.get_by_id(db, business_id=business_id, file_id=file_id)
        if not kfile:
            return False

        await db.delete(kfile)
        await db.flush()
        return True


knowledge_file_repository = KnowledgeFileRepository()

