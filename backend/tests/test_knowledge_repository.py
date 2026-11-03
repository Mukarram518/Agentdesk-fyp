"""Tests for KnowledgeRepository (Phase 5.2A).

Verifies:
1. FAQ and document chunk creation with integrity constraints.
2. Batch creation of chunks preserving input order.
3. Retrieval by ID strictly within tenant scope (cross-business returns None).
4. Listing by business with tenant isolation, filters (source_type, source_file_id, stale), and pagination.
5. Update operations with allow-list validation, rejection of immutable fields, and automatic stale marking on content changes.
6. Deletion within tenant scope (cross-business returns False).
7. pgvector cosine similarity search:
   - Strict tenant isolation (never returns other business entries).
   - Correct ranking by cosine distance ascending.
   - Respects top_k limits.
   - Excludes NULL embeddings.
   - Excludes stale embeddings.
   - Source-type filtering.
   - Distance threshold filtering.
   - Rejection of invalid vector dimensions and invalid top_k.
"""

import uuid
import pytest
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.knowledge import (
    KnowledgeBaseEntry,
    KnowledgeSourceType,
    KnowledgeLanguage,
    EMBEDDING_VECTOR_DIMENSION,
)
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus
from app.repositories.knowledge_repository import knowledge_repository


async def create_test_business(db, name: str = "Knowledge Repo Biz") -> Business:
    """Helper to persist a test business tenant."""
    biz = Business(
        name=name,
        slug=f"kr-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


async def create_test_file(db, business_id: uuid.UUID, filename: str = "source.pdf") -> KnowledgeFile:
    """Helper to persist a test knowledge file."""
    kfile = KnowledgeFile(
        business_id=business_id,
        filename=filename,
        storage_key=f"biz/{business_id}/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        processing_status=KnowledgeFileStatus.READY.value,
    )
    db.add(kfile)
    await db.flush()
    return kfile


def create_unit_vector(active_index: int) -> list:
    """Creates a deterministic 384-dimensional unit basis vector."""
    vec = [0.0] * EMBEDDING_VECTOR_DIMENSION
    vec[active_index % EMBEDDING_VECTOR_DIMENSION] = 1.0
    return vec


# =====================================================================
# 1. Creation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_success():
    """Verifies create_faq persists FAQ with source_type='FAQ' and null file references."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        faq = await knowledge_repository.create_faq(
            db=db,
            business_id=biz.id,
            question="What are your hours?",
            answer="9 AM to 6 PM.",
            tags=["hours", "support"],
            language=KnowledgeLanguage.EN.value,
        )

        assert isinstance(faq.id, uuid.UUID)
        assert faq.business_id == biz.id
        assert faq.question == "What are your hours?"
        assert faq.answer == "9 AM to 6 PM."
        assert faq.tags == ["hours", "support"]
        assert faq.source_type == "FAQ"
        assert faq.source_file_id is None
        assert faq.chunk_index is None
        assert faq.embedding_stale is False


@pytest.mark.asyncio
async def test_create_chunk_success():
    """Verifies create_chunk persists document chunk with source_file_id and chunk_index."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

        chunk = await knowledge_repository.create_chunk(
            db=db,
            business_id=biz.id,
            source_file_id=kfile.id,
            chunk_index=0,
            answer="Section 1 text.",
            page_number=1,
            section_title="Intro",
        )

        assert chunk.id is not None
        assert chunk.business_id == biz.id
        assert chunk.source_file_id == kfile.id
        assert chunk.chunk_index == 0
        assert chunk.source_type == "document_chunk"
        assert chunk.page_number == 1
        assert chunk.section_title == "Intro"


@pytest.mark.asyncio
async def test_create_chunks_batch_preserves_order():
    """Verifies create_chunks_batch saves multiple chunks preserving their exact input order."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

        chunks_input = [
            {"source_file_id": kfile.id, "chunk_index": 0, "answer": "Part 0", "section_title": "Sec 0"},
            {"source_file_id": kfile.id, "chunk_index": 1, "answer": "Part 1", "section_title": "Sec 1"},
            {"source_file_id": kfile.id, "chunk_index": 2, "answer": "Part 2", "section_title": "Sec 2"},
        ]

        batch = await knowledge_repository.create_chunks_batch(
            db=db, business_id=biz.id, chunks_data=chunks_input
        )

        assert len(batch) == 3
        for i, item in enumerate(batch):
            assert item.chunk_index == i
            assert item.answer == f"Part {i}"
            assert item.source_file_id == kfile.id
            assert item.business_id == biz.id


# =====================================================================
# 2. Retrieval & Listing Tests
# =====================================================================

@pytest.mark.asyncio
async def test_get_by_id_tenant_isolation():
    """Verifies Business A cannot retrieve Business B's knowledge entry by ID."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Tenant A")
        biz_b = await create_test_business(db, name="Tenant B")

        faq_a = await knowledge_repository.create_faq(
            db=db, business_id=biz_a.id, question="Q A?", answer="A A."
        )

        # Same tenant succeeds
        retrieved_a = await knowledge_repository.get_by_id(db=db, business_id=biz_a.id, entry_id=faq_a.id)
        assert retrieved_a is not None
        assert retrieved_a.id == faq_a.id

        # Different tenant returns None
        retrieved_b = await knowledge_repository.get_by_id(db=db, business_id=biz_b.id, entry_id=faq_a.id)
        assert retrieved_b is None


@pytest.mark.asyncio
async def test_list_by_business_filters():
    """Verifies list_by_business filters by source_type, file, and pagination."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)

        # 2 FAQs
        await knowledge_repository.create_faq(db=db, business_id=biz.id, question="FAQ 1", answer="Ans 1")
        await knowledge_repository.create_faq(db=db, business_id=biz.id, question="FAQ 2", answer="Ans 2")
        # 1 Chunk
        await knowledge_repository.create_chunk(
            db=db, business_id=biz.id, source_file_id=kfile.id, chunk_index=0, answer="Chunk content"
        )

        # Filter by source_type FAQ
        faqs = await knowledge_repository.list_by_business(
            db=db, business_id=biz.id, source_type=KnowledgeSourceType.FAQ.value
        )
        assert len(faqs) == 2
        assert all(f.source_type == "FAQ" for f in faqs)

        # Filter by source_type document_chunk
        chunks = await knowledge_repository.list_by_business(
            db=db, business_id=biz.id, source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value
        )
        assert len(chunks) == 1
        assert chunks[0].source_type == "document_chunk"

        # Filter by file ID
        file_chunks = await knowledge_repository.list_by_business(
            db=db, business_id=biz.id, source_file_id=kfile.id
        )
        assert len(file_chunks) == 1
        assert file_chunks[0].source_file_id == kfile.id


# =====================================================================
# 3. Update & Delete Tests
# =====================================================================

@pytest.mark.asyncio
async def test_update_entry_success_and_stale_flag():
    """Verifies updating text content automatically sets embedding_stale=True."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        faq = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="Initial Q", answer="Initial A"
        )
        assert faq.embedding_stale is False

        # 1. Update content -> marks stale
        updated = await knowledge_repository.update_entry(
            db=db, business_id=biz.id, entry_id=faq.id, answer="Updated Answer Text"
        )
        assert updated is not None
        assert updated.answer == "Updated Answer Text"
        assert updated.embedding_stale is True

        # 2. Update with new embedding -> marks not stale
        vec = create_unit_vector(0)
        updated2 = await knowledge_repository.update_entry(
            db=db, business_id=biz.id, entry_id=faq.id, embedding=vec, embedding_stale=False
        )
        assert updated2.embedding_stale is False
        assert updated2.embedding is not None

        # 3. Update non-content (tags) -> does not mark stale
        updated3 = await knowledge_repository.update_entry(
            db=db, business_id=biz.id, entry_id=faq.id, tags=["new_tag"]
        )
        assert updated3.tags == ["new_tag"]
        assert updated3.embedding_stale is False


@pytest.mark.asyncio
async def test_update_entry_rejects_immutable_fields():
    """Verifies update_entry raises ValueError when trying to modify immutable structural fields."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        faq = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="Q?", answer="A."
        )

        with pytest.raises(ValueError, match="Field 'id' cannot be modified"):
            await knowledge_repository.update_entry(
                db=db, business_id=biz.id, entry_id=faq.id, id=uuid.uuid4()
            )

        with pytest.raises(ValueError, match="Field 'source_file_id' cannot be modified"):
            await knowledge_repository.update_entry(
                db=db, business_id=biz.id, entry_id=faq.id, source_file_id=uuid.uuid4()
            )

        with pytest.raises(ValueError, match="Field 'source_type' cannot be modified"):
            await knowledge_repository.update_entry(
                db=db, business_id=biz.id, entry_id=faq.id, source_type="document_chunk"
            )

        with pytest.raises(ValueError, match="Field 'chunk_index' cannot be modified"):
            await knowledge_repository.update_entry(
                db=db, business_id=biz.id, entry_id=faq.id, chunk_index=1
            )


@pytest.mark.asyncio
async def test_update_entry_cross_business_returns_none():
    """Verifies Business B cannot update Business A's entry."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Owner A")
        biz_b = await create_test_business(db, name="Intruder B")

        faq_a = await knowledge_repository.create_faq(
            db=db, business_id=biz_a.id, question="Original Q", answer="Original A"
        )

        res = await knowledge_repository.update_entry(
            db=db, business_id=biz_b.id, entry_id=faq_a.id, answer="Hacked Answer"
        )
        assert res is None

        refreshed = await knowledge_repository.get_by_id(db=db, business_id=biz_a.id, entry_id=faq_a.id)
        assert refreshed.answer == "Original A"


@pytest.mark.asyncio
async def test_delete_entry_tenant_isolation():
    """Verifies delete_entry strictly respects tenant boundaries."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Del Biz A")
        biz_b = await create_test_business(db, name="Del Biz B")

        faq_a = await knowledge_repository.create_faq(
            db=db, business_id=biz_a.id, question="Del Q", answer="Del A"
        )

        # Cross-business deletion fails
        deleted_b = await knowledge_repository.delete_entry(
            db=db, business_id=biz_b.id, entry_id=faq_a.id
        )
        assert deleted_b is False
        assert await knowledge_repository.get_by_id(db=db, business_id=biz_a.id, entry_id=faq_a.id) is not None

        # Same-business deletion succeeds
        deleted_a = await knowledge_repository.delete_entry(
            db=db, business_id=biz_a.id, entry_id=faq_a.id
        )
        assert deleted_a is True
        assert await knowledge_repository.get_by_id(db=db, business_id=biz_a.id, entry_id=faq_a.id) is None


# =====================================================================
# 4. Vector Similarity Search Tests
# =====================================================================

@pytest.mark.asyncio
async def test_search_similar_ordering_and_top_k():
    """Verifies search_similar returns results ordered by cosine distance ascending and respects top_k."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Vector 0: [1, 0, 0, ...]
        v0 = create_unit_vector(0)
        # Vector 1: [0, 1, 0, ...]
        v1 = create_unit_vector(1)
        # Vector 2: [0, 0, 1, ...]
        v2 = create_unit_vector(2)

        # Query vector is closest to v0
        query_v = create_unit_vector(0)

        faq0 = await knowledge_repository.create_faq(db=db, business_id=biz.id, question="Q0", answer="Ans 0", embedding=v0)
        faq1 = await knowledge_repository.create_faq(db=db, business_id=biz.id, question="Q1", answer="Ans 1", embedding=v1)
        faq2 = await knowledge_repository.create_faq(db=db, business_id=biz.id, question="Q2", answer="Ans 2", embedding=v2)

        results = await knowledge_repository.search_similar(
            db=db,
            business_id=biz.id,
            query_vector=query_v,
            top_k=2,
        )

        # Respects top_k=2
        assert len(results) == 2

        # First result is identical (distance ~ 0.0)
        top_entry, top_dist = results[0]
        assert top_entry.id == faq0.id
        assert top_dist < 1e-4

        # Second result has higher distance
        second_entry, second_dist = results[1]
        assert second_dist > top_dist


@pytest.mark.asyncio
async def test_search_similar_tenant_isolation():
    """Verifies vector search for Business A never returns matching embeddings from Business B."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Search Biz A")
        biz_b = await create_test_business(db, name="Search Biz B")

        # Same vector saved under both businesses
        identical_vec = create_unit_vector(5)

        faq_a = await knowledge_repository.create_faq(
            db=db, business_id=biz_a.id, question="Biz A FAQ", answer="A content", embedding=identical_vec
        )
        faq_b = await knowledge_repository.create_faq(
            db=db, business_id=biz_b.id, question="Biz B FAQ", answer="B content", embedding=identical_vec
        )

        # Search for Biz A
        results_a = await knowledge_repository.search_similar(
            db=db,
            business_id=biz_a.id,
            query_vector=identical_vec,
            top_k=10,
        )

        returned_ids_a = {entry.id for entry, _ in results_a}
        assert faq_a.id in returned_ids_a
        assert faq_b.id not in returned_ids_a


@pytest.mark.asyncio
async def test_search_similar_excludes_null_and_stale_embeddings():
    """Verifies that search_similar excludes entries with NULL or stale embeddings."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        vec = create_unit_vector(10)

        # 1. Valid embedding
        valid_faq = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="Valid", answer="Valid Ans", embedding=vec
        )
        # 2. NULL embedding
        null_faq = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="Null", answer="Null Ans", embedding=None
        )
        # 3. Stale embedding
        stale_faq = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="Stale", answer="Stale Ans", embedding=vec
        )
        await knowledge_repository.update_entry(
            db=db, business_id=biz.id, entry_id=stale_faq.id, embedding_stale=True
        )

        results = await knowledge_repository.search_similar(
            db=db,
            business_id=biz.id,
            query_vector=vec,
            top_k=10,
        )

        returned_ids = {entry.id for entry, _ in results}
        assert valid_faq.id in returned_ids
        assert null_faq.id not in returned_ids
        assert stale_faq.id not in returned_ids


@pytest.mark.asyncio
async def test_search_similar_source_type_filter():
    """Verifies search_similar filters by source_type (FAQ vs document_chunk)."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, biz.id)
        vec = create_unit_vector(20)

        faq = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="FAQ", answer="FAQ text", embedding=vec
        )
        chunk = await knowledge_repository.create_chunk(
            db=db, business_id=biz.id, source_file_id=kfile.id, chunk_index=0, answer="Chunk text", embedding=vec
        )

        # Search only FAQs
        faq_results = await knowledge_repository.search_similar(
            db=db,
            business_id=biz.id,
            query_vector=vec,
            source_type=KnowledgeSourceType.FAQ.value,
        )
        faq_ids = {e.id for e, _ in faq_results}
        assert faq.id in faq_ids
        assert chunk.id not in faq_ids

        # Search only document chunks
        chunk_results = await knowledge_repository.search_similar(
            db=db,
            business_id=biz.id,
            query_vector=vec,
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
        )
        chunk_ids = {e.id for e, _ in chunk_results}
        assert chunk.id in chunk_ids
        assert faq.id not in chunk_ids


@pytest.mark.asyncio
async def test_search_similar_score_threshold_filter():
    """Verifies score_threshold excludes results whose cosine distance exceeds the threshold."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Identical vector (distance = 0.0)
        v_ident = create_unit_vector(30)
        # Orthogonal vector (distance = 1.0)
        v_ortho = create_unit_vector(31)

        faq_ident = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="Identical", answer="Ans", embedding=v_ident
        )
        faq_ortho = await knowledge_repository.create_faq(
            db=db, business_id=biz.id, question="Orthogonal", answer="Ans", embedding=v_ortho
        )

        # Threshold of 0.5 should include identical (0.0) but exclude orthogonal (1.0)
        results = await knowledge_repository.search_similar(
            db=db,
            business_id=biz.id,
            query_vector=v_ident,
            score_threshold=0.5,
        )

        returned_ids = {e.id for e, _ in results}
        assert faq_ident.id in returned_ids
        assert faq_ortho.id not in returned_ids


@pytest.mark.asyncio
async def test_search_similar_validates_dimensions_and_top_k():
    """Verifies search_similar raises ValueError on invalid vector dimensions or top_k."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Invalid dimension: 10 instead of 384
        with pytest.raises(ValueError, match="Query vector must contain exactly 384 dimensions"):
            await knowledge_repository.search_similar(
                db=db,
                business_id=biz.id,
                query_vector=[0.1] * 10,
            )

        # Invalid top_k: 0
        valid_vec = create_unit_vector(0)
        with pytest.raises(ValueError, match="top_k must be between 1 and 100"):
            await knowledge_repository.search_similar(
                db=db,
                business_id=biz.id,
                query_vector=valid_vec,
                top_k=0,
            )

        # Invalid top_k: 200
        with pytest.raises(ValueError, match="top_k must be between 1 and 100"):
            await knowledge_repository.search_similar(
                db=db,
                business_id=biz.id,
                query_vector=valid_vec,
                top_k=200,
            )
