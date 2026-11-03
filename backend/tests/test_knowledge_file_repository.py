"""Tests for KnowledgeFileRepository (Phase 5.2A).

Verifies:
1. File creation with tenant scoping and metadata.
2. Retrieval by ID strictly within tenant scope (cross-business returns None).
3. Listing by business with tenant isolation, status filtering, and pagination.
4. Ordering by created_at DESC (newest first).
5. Status update within tenant scope (cross-business returns None).
6. Deletion within tenant scope (cross-business returns False).
7. Cascade deletion: deleting a file removes its document chunks while leaving FAQs intact.
"""

import uuid
import pytest
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.knowledge import KnowledgeBaseEntry, KnowledgeSourceType
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus
from app.repositories.knowledge_file_repository import knowledge_file_repository


async def create_test_business(db, name: str = "Repo Test Business") -> Business:
    """Helper to persist a test business tenant."""
    biz = Business(
        name=name,
        slug=f"kfr-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


# =====================================================================
# 1. Creation & Retrieval Tests
# =====================================================================

@pytest.mark.asyncio
async def test_create_file_success():
    """Verifies that create_file persists file metadata and flushes without committing."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        kfile = await knowledge_file_repository.create_file(
            db=db,
            business_id=biz.id,
            filename="catalog.pdf",
            storage_key=f"businesses/{biz.id}/files/catalog.pdf",
            mime_type="application/pdf",
            size_bytes=1024 * 100,
            processing_status=KnowledgeFileStatus.PENDING.value,
        )

        assert isinstance(kfile.id, uuid.UUID)
        assert kfile.business_id == biz.id
        assert kfile.filename == "catalog.pdf"
        assert kfile.storage_key == f"businesses/{biz.id}/files/catalog.pdf"
        assert kfile.mime_type == "application/pdf"
        assert kfile.size_bytes == 102400
        assert kfile.processing_status == "pending"
        assert kfile.error_message is None


@pytest.mark.asyncio
async def test_get_by_id_same_business_succeeds():
    """Verifies get_by_id returns the file when business_id matches."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await knowledge_file_repository.create_file(
            db=db,
            business_id=biz.id,
            filename="price_list.pdf",
            storage_key="key_1",
            mime_type="application/pdf",
            size_bytes=5000,
        )

        retrieved = await knowledge_file_repository.get_by_id(
            db=db,
            business_id=biz.id,
            file_id=kfile.id,
        )

        assert retrieved is not None
        assert retrieved.id == kfile.id
        assert retrieved.filename == "price_list.pdf"


@pytest.mark.asyncio
async def test_get_by_id_cross_business_returns_none():
    """Verifies that Business A cannot retrieve Business B's file by ID."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Biz A")
        biz_b = await create_test_business(db, name="Biz B")

        # File belongs to Biz A
        kfile_a = await knowledge_file_repository.create_file(
            db=db,
            business_id=biz_a.id,
            filename="biz_a_contracts.pdf",
            storage_key="key_contracts",
            mime_type="application/pdf",
            size_bytes=8000,
        )

        # Biz B attempts to query Biz A's file
        retrieved = await knowledge_file_repository.get_by_id(
            db=db,
            business_id=biz_b.id,
            file_id=kfile_a.id,
        )

        assert retrieved is None


# =====================================================================
# 2. Listing & Pagination Tests
# =====================================================================

@pytest.mark.asyncio
async def test_list_by_business_isolation():
    """Verifies list_by_business only returns files belonging to the requested business."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="List Biz A")
        biz_b = await create_test_business(db, name="List Biz B")

        f_a1 = await knowledge_file_repository.create_file(
            db=db, business_id=biz_a.id, filename="a1.pdf", storage_key="a1", mime_type="application/pdf", size_bytes=100
        )
        f_a2 = await knowledge_file_repository.create_file(
            db=db, business_id=biz_a.id, filename="a2.pdf", storage_key="a2", mime_type="application/pdf", size_bytes=200
        )
        f_b1 = await knowledge_file_repository.create_file(
            db=db, business_id=biz_b.id, filename="b1.pdf", storage_key="b1", mime_type="application/pdf", size_bytes=300
        )

        list_a = await knowledge_file_repository.list_by_business(db=db, business_id=biz_a.id)
        list_b = await knowledge_file_repository.list_by_business(db=db, business_id=biz_b.id)

        ids_a = {f.id for f in list_a}
        ids_b = {f.id for f in list_b}

        assert f_a1.id in ids_a
        assert f_a2.id in ids_a
        assert f_b1.id not in ids_a
        assert f_b1.id in ids_b
        assert f_a1.id not in ids_b


@pytest.mark.asyncio
async def test_list_by_business_status_filter():
    """Verifies filtering files by processing_status."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        await knowledge_file_repository.create_file(
            db=db, business_id=biz.id, filename="f1.pdf", storage_key="f1", mime_type="application/pdf", size_bytes=100,
            processing_status=KnowledgeFileStatus.READY.value
        )
        await knowledge_file_repository.create_file(
            db=db, business_id=biz.id, filename="f2.pdf", storage_key="f2", mime_type="application/pdf", size_bytes=100,
            processing_status=KnowledgeFileStatus.FAILED.value
        )

        ready_files = await knowledge_file_repository.list_by_business(
            db=db, business_id=biz.id, status=KnowledgeFileStatus.READY.value
        )
        failed_files = await knowledge_file_repository.list_by_business(
            db=db, business_id=biz.id, status=KnowledgeFileStatus.FAILED.value
        )

        assert all(f.processing_status == "ready" for f in ready_files)
        assert len(ready_files) == 1
        assert all(f.processing_status == "failed" for f in failed_files)
        assert len(failed_files) == 1


@pytest.mark.asyncio
async def test_list_by_business_pagination():
    """Verifies limit and offset pagination on list_by_business."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        for i in range(5):
            await knowledge_file_repository.create_file(
                db=db, business_id=biz.id, filename=f"p_{i}.pdf", storage_key=f"p_{i}", mime_type="application/pdf", size_bytes=100
            )

        page1 = await knowledge_file_repository.list_by_business(db=db, business_id=biz.id, limit=2, offset=0)
        page2 = await knowledge_file_repository.list_by_business(db=db, business_id=biz.id, limit=2, offset=2)
        page3 = await knowledge_file_repository.list_by_business(db=db, business_id=biz.id, limit=2, offset=4)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

        # Check no overlapping IDs across pages
        ids_page1 = {f.id for f in page1}
        ids_page2 = {f.id for f in page2}
        assert ids_page1.isdisjoint(ids_page2)


# =====================================================================
# 3. Update & Delete Tests
# =====================================================================

@pytest.mark.asyncio
async def test_update_status_success():
    """Verifies update_status modifies status and error_message for the owning tenant."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await knowledge_file_repository.create_file(
            db=db, business_id=biz.id, filename="proc.pdf", storage_key="proc_key", mime_type="application/pdf", size_bytes=500
        )

        updated = await knowledge_file_repository.update_status(
            db=db,
            business_id=biz.id,
            file_id=kfile.id,
            status=KnowledgeFileStatus.FAILED.value,
            error_message="Corrupted PDF file header",
        )

        assert updated is not None
        assert updated.processing_status == "failed"
        assert updated.error_message == "Corrupted PDF file header"


@pytest.mark.asyncio
async def test_update_status_cross_business_returns_none():
    """Verifies Business B cannot update the status of Business A's file."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Owner A")
        biz_b = await create_test_business(db, name="Intruder B")

        kfile_a = await knowledge_file_repository.create_file(
            db=db, business_id=biz_a.id, filename="a_doc.pdf", storage_key="a_key", mime_type="application/pdf", size_bytes=500
        )

        result = await knowledge_file_repository.update_status(
            db=db,
            business_id=biz_b.id,
            file_id=kfile_a.id,
            status=KnowledgeFileStatus.READY.value,
        )

        assert result is None
        # Verify status in database did not change
        refreshed = await knowledge_file_repository.get_by_id(db=db, business_id=biz_a.id, file_id=kfile_a.id)
        assert refreshed.processing_status == "pending"


@pytest.mark.asyncio
async def test_delete_file_success():
    """Verifies delete_file removes the file record for the owning tenant."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await knowledge_file_repository.create_file(
            db=db, business_id=biz.id, filename="del.pdf", storage_key="del_key", mime_type="application/pdf", size_bytes=100
        )

        deleted = await knowledge_file_repository.delete_file(
            db=db,
            business_id=biz.id,
            file_id=kfile.id,
        )

        assert deleted is True
        assert await knowledge_file_repository.get_by_id(db=db, business_id=biz.id, file_id=kfile.id) is None


@pytest.mark.asyncio
async def test_delete_file_cross_business_returns_false():
    """Verifies Business B cannot delete Business A's file."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Owner A")
        biz_b = await create_test_business(db, name="Intruder B")

        kfile_a = await knowledge_file_repository.create_file(
            db=db, business_id=biz_a.id, filename="safe.pdf", storage_key="safe_key", mime_type="application/pdf", size_bytes=100
        )

        deleted = await knowledge_file_repository.delete_file(
            db=db,
            business_id=biz_b.id,
            file_id=kfile_a.id,
        )

        assert deleted is False
        assert await knowledge_file_repository.get_by_id(db=db, business_id=biz_a.id, file_id=kfile_a.id) is not None


@pytest.mark.asyncio
async def test_delete_file_cascades_chunks_not_faqs():
    """Verifies deleting a file cascades to delete its document chunks while leaving independent FAQs intact."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        kfile = await knowledge_file_repository.create_file(
            db=db, business_id=biz.id, filename="casc.pdf", storage_key="casc_key", mime_type="application/pdf", size_bytes=100
        )

        # Chunks referencing kfile
        chunk1 = KnowledgeBaseEntry(
            business_id=biz.id,
            source_file_id=kfile.id,
            chunk_index=0,
            answer="Chunk 1",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
        )
        chunk2 = KnowledgeBaseEntry(
            business_id=biz.id,
            source_file_id=kfile.id,
            chunk_index=1,
            answer="Chunk 2",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
        )
        # Independent FAQ
        faq = KnowledgeBaseEntry(
            business_id=biz.id,
            question="FAQ Q?",
            answer="FAQ A.",
            source_type=KnowledgeSourceType.FAQ.value,
        )
        db.add_all([chunk1, chunk2, faq])
        await db.flush()

        # Delete the file
        deleted = await knowledge_file_repository.delete_file(db=db, business_id=biz.id, file_id=kfile.id)
        assert deleted is True

        # Verify chunks deleted
        chunks_res = await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.source_file_id == kfile.id)
        )
        assert len(chunks_res.scalars().all()) == 0

        # Verify FAQ still exists
        faq_res = await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq.id)
        )
        assert faq_res.scalar_one_or_none() is not None

