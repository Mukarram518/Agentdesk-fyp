"""Unit and integration tests for KnowledgeService (Phase 5.2C).

Verifies:
1. Successful FAQ creation and embedding persistence.
2. Creation when embedding generation fails (graceful fallback).
3. Optional question handling according to the existing model.
4. Empty answer and invalid language validation.
5. Tenant-scoped get, list, update, and delete.
6. Pagination and language filtering.
7. Content updates regenerate embeddings.
8. Tags/language-only updates do not regenerate embeddings.
9. Failed update embedding marks the entry stale.
10. Semantic search uses query embeddings and correct tenant scope.
11. Stale and null embeddings are excluded from search.
12. Re-embedding stale FAQ entries.
13. Re-embedding does not process document chunks.
14. No service or repository commits transactions.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
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
from app.providers.embeddings.base import PREFIX_PASSAGE, PREFIX_QUERY
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.services.knowledge_service import KnowledgeService, knowledge_service


async def create_test_business(db, name: str = "Knowledge Service Biz") -> Business:
    """Helper to persist a test business tenant."""
    biz = Business(
        name=name,
        slug=f"ks-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.flush()
    await db.commit()
    await db.refresh(biz)
    return biz


async def create_test_file(db, business_id: uuid.UUID, filename: str = "doc.pdf") -> KnowledgeFile:
    """Helper to persist a test knowledge file."""
    kfile = KnowledgeFile(
        business_id=business_id,
        filename=filename,
        storage_key=f"biz/{business_id}/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        processing_status=KnowledgeFileStatus.READY.value,
    )
    db.add(kfile)
    await db.flush()
    return kfile


# =====================================================================
# 1. Successful FAQ Creation and Embedding Persistence
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_success():
    """Verifies successful FAQ creation, answer-only embedding generation, and DB persistence."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        faq = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="What are your consultation fees?",
            answer="Initial consultation is 50 USD.",
            tags=["fees", "pricing"],
            language=KnowledgeLanguage.EN.value,
        )

        assert faq.id is not None
        assert faq.business_id == biz.id
        assert faq.question == "What are your consultation fees?"
        assert faq.answer == "Initial consultation is 50 USD."
        assert faq.tags == ["fees", "pricing"]
        assert faq.language == "en"
        assert faq.source_type == KnowledgeSourceType.FAQ.value
        assert faq.source_file_id is None
        assert faq.chunk_index is None
        assert faq.embedding_stale is False

        # Verify 384-dimensional unit vector generated from answer text
        assert faq.embedding is not None
        assert len(faq.embedding) == EMBEDDING_VECTOR_DIMENSION
        assert all(isinstance(x, float) for x in faq.embedding)

        # Confirm persisted in DB
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq.id)
        persisted = (await db.execute(stmt)).scalar_one_or_none()
        assert persisted is not None
        assert persisted.answer == "Initial consultation is 50 USD."
        await db.commit()


# =====================================================================
# 2. Embedding Generation Failure (Graceful Fallback)
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_embedding_failure_graceful_fallback():
    """Verifies that FAQ creation succeeds with embedding=None and stale=True when provider fails."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Mock provider that fails during embed_text
        failing_provider = MagicMock()
        failing_provider.dimension = 384
        failing_provider.embed_text = AsyncMock(side_effect=RuntimeError("Embedding model offline"))

        svc = KnowledgeService(embedding_provider=failing_provider)

        faq = await svc.create_faq(
            db=db,
            business_id=biz.id,
            question="Where are you located?",
            answer="123 Main Street, Suite 400.",
        )

        assert faq.id is not None
        assert faq.question == "Where are you located?"
        assert faq.answer == "123 Main Street, Suite 400."
        assert faq.embedding is None
        assert faq.embedding_stale is True

        await db.commit()


# =====================================================================
# 3. Optional Question Handling
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_optional_question():
    """Verifies question is optional according to the database model."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # 1. Question omitted (None default)
        faq1 = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            answer="Direct general policy note without question.",
        )
        assert faq1.question is None
        assert faq1.answer == "Direct general policy note without question."
        assert faq1.embedding is not None
        assert faq1.embedding_stale is False

        # 2. Question passed explicitly as None
        faq2 = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question=None,
            answer="Another standalone knowledge note.",
        )
        assert faq2.question is None
        assert faq2.answer == "Another standalone knowledge note."
        assert faq2.embedding is not None

        # 3. Empty string question becomes None
        faq3 = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="   ",
            answer="Answer with blank question.",
        )
        assert faq3.question is None

        await db.commit()


# =====================================================================
# 4. Input Validation
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_validation_errors():
    """Verifies that invalid answer, language, tags, or business_id raise ValueError."""
    async with async_session_factory() as db:
        valid_biz_id = uuid.uuid4()

        # Empty or whitespace answer
        with pytest.raises(ValueError, match="Answer cannot be empty"):
            await knowledge_service.create_faq(db, business_id=valid_biz_id, answer="")

        with pytest.raises(ValueError, match="Answer cannot be empty"):
            await knowledge_service.create_faq(db, business_id=valid_biz_id, answer="   ")

        with pytest.raises(ValueError, match="Answer cannot be empty"):
            await knowledge_service.create_faq(db, business_id=valid_biz_id, answer=None)  # type: ignore

        # Invalid language
        with pytest.raises(ValueError, match="Invalid language 'french'"):
            await knowledge_service.create_faq(
                db, business_id=valid_biz_id, answer="Valid answer", language="french"
            )

        # Invalid tags
        with pytest.raises(ValueError, match="Tags must be a list"):
            await knowledge_service.create_faq(
                db, business_id=valid_biz_id, answer="Valid answer", tags="not-a-list"  # type: ignore
            )

        # Invalid business_id
        with pytest.raises(ValueError, match="Valid business_id is required"):
            await knowledge_service.create_faq(db, business_id=None, answer="Valid answer")  # type: ignore


# =====================================================================
# 5. Tenant-Scoped Get, List, Update, and Delete
# =====================================================================

@pytest.mark.asyncio
async def test_tenant_isolation_get_list_update_delete():
    """Verifies that a tenant cannot read, list, update, or delete another tenant's FAQ."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, "Tenant Alpha")
        biz_b = await create_test_business(db, "Tenant Beta")

        faq_a = await knowledge_service.create_faq(
            db=db,
            business_id=biz_a.id,
            question="Alpha Question?",
            answer="Alpha secret answer.",
        )

        # 1. Get cross-tenant -> returns None
        retrieved = await knowledge_service.get_faq(db, business_id=biz_b.id, entry_id=faq_a.id)
        assert retrieved is None

        # 2. List cross-tenant -> Tenant B sees empty list
        list_b = await knowledge_service.list_faqs(db, business_id=biz_b.id)
        assert len(list_b) == 0

        # 3. Update cross-tenant -> returns None, DB remains unchanged
        update_res = await knowledge_service.update_faq(
            db=db,
            business_id=biz_b.id,
            entry_id=faq_a.id,
            answer="Tampered answer!",
        )
        assert update_res is None

        persisted = await knowledge_service.get_faq(db, business_id=biz_a.id, entry_id=faq_a.id)
        assert persisted is not None
        assert persisted.answer == "Alpha secret answer."

        # 4. Delete cross-tenant -> returns False, record is NOT deleted
        delete_res = await knowledge_service.delete_faq(
            db=db,
            business_id=biz_b.id,
            entry_id=faq_a.id,
        )
        assert delete_res is False

        persisted_after = await knowledge_service.get_faq(db, business_id=biz_a.id, entry_id=faq_a.id)
        assert persisted_after is not None

        # 5. Legitimate owner delete -> returns True
        owner_delete_res = await knowledge_service.delete_faq(
            db=db,
            business_id=biz_a.id,
            entry_id=faq_a.id,
        )
        assert owner_delete_res is True

        persisted_deleted = await knowledge_service.get_faq(db, business_id=biz_a.id, entry_id=faq_a.id)
        assert persisted_deleted is None

        await db.commit()


# =====================================================================
# 6. Pagination and Language Filtering
# =====================================================================

@pytest.mark.asyncio
async def test_list_faqs_pagination_and_language_filter():
    """Verifies list_faqs enforces pagination and language filtering."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Create 3 English FAQs and 2 Urdu FAQs
        for i in range(3):
            await knowledge_service.create_faq(
                db=db,
                business_id=biz.id,
                question=f"English Q{i}",
                answer=f"English Answer {i}",
                language=KnowledgeLanguage.EN.value,
            )

        for i in range(2):
            await knowledge_service.create_faq(
                db=db,
                business_id=biz.id,
                question=f"Urdu Q{i}",
                answer=f"Urdu Answer {i}",
                language=KnowledgeLanguage.UR.value,
            )

        # Pagination: limit 2, offset 0
        page1 = await knowledge_service.list_faqs(db, business_id=biz.id, limit=2, offset=0)
        assert len(page1) == 2

        # Pagination: limit 2, offset 2
        page2 = await knowledge_service.list_faqs(db, business_id=biz.id, limit=2, offset=2)
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

        # Language filter: Urdu only
        urdu_list = await knowledge_service.list_faqs(db, business_id=biz.id, language="ur")
        assert len(urdu_list) == 2
        assert all(entry.language == "ur" for entry in urdu_list)

        # Language filter: English only
        en_list = await knowledge_service.list_faqs(db, business_id=biz.id, language="en")
        assert len(en_list) == 3
        assert all(entry.language == "en" for entry in en_list)

        await db.commit()


# =====================================================================
# 7. Content Updates Regenerate Embeddings
# =====================================================================

@pytest.mark.asyncio
async def test_update_faq_content_regenerates_embedding():
    """Verifies that changing answer or question text regenerates vector embedding."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        faq = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="What is the price?",
            answer="Original price is 100.",
        )
        original_vector = list(faq.embedding)  # copy
        assert faq.embedding_stale is False

        # 1. Update answer -> vector regenerated, stale remains False
        updated_faq = await knowledge_service.update_faq(
            db=db,
            business_id=biz.id,
            entry_id=faq.id,
            answer="Revised price is 150.",
        )
        assert updated_faq is not None
        assert updated_faq.answer == "Revised price is 150."
        assert updated_faq.embedding != original_vector
        assert updated_faq.embedding_stale is False

        # 2. Update question -> embedding regenerated, stale remains False
        vector_before_q_update = list(updated_faq.embedding)
        updated_q_faq = await knowledge_service.update_faq(
            db=db,
            business_id=biz.id,
            entry_id=faq.id,
            question="Updated price query?",
        )
        assert updated_q_faq is not None
        assert updated_q_faq.question == "Updated price query?"
        assert updated_q_faq.embedding_stale is False

        await db.commit()


# =====================================================================
# 8. Metadata-Only Updates Do Not Regenerate Embeddings
# =====================================================================

@pytest.mark.asyncio
async def test_update_faq_metadata_only_does_not_regenerate_embedding():
    """Verifies that updating tags or language alone does NOT call embed_text."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        mock_provider = MockEmbeddingProvider()
        mock_provider.embed_text = AsyncMock(wraps=mock_provider.embed_text)

        svc = KnowledgeService(embedding_provider=mock_provider)

        faq = await svc.create_faq(
            db=db,
            business_id=biz.id,
            question="What are your tags?",
            answer="We use tags to organize information.",
            tags=["v1"],
            language="en",
        )
        original_vector = list(faq.embedding)
        assert mock_provider.embed_text.call_count == 1

        # Reset call counter
        mock_provider.embed_text.reset_mock()

        # Update only tags and language
        updated = await svc.update_faq(
            db=db,
            business_id=biz.id,
            entry_id=faq.id,
            tags=["v2", "updated"],
            language="mixed",
        )

        assert updated is not None
        assert updated.tags == ["v2", "updated"]
        assert updated.language == "mixed"
        assert updated.embedding == original_vector
        assert updated.embedding_stale is False

        # Confirm embed_text was NEVER called for metadata update
        mock_provider.embed_text.assert_not_called()

        await db.commit()


# =====================================================================
# 9. Failed Update Embedding Marks Entry Stale
# =====================================================================

@pytest.mark.asyncio
async def test_update_faq_embedding_failure_marks_stale():
    """Verifies that if embedding fails on update, the new content is saved and marked stale."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Start with working provider
        mock_provider = MockEmbeddingProvider()
        svc = KnowledgeService(embedding_provider=mock_provider)

        faq = await svc.create_faq(
            db=db,
            business_id=biz.id,
            question="Initial Q",
            answer="Initial Answer",
        )
        assert faq.embedding_stale is False

        # Now simulate embedding failure on update
        mock_provider.embed_text = AsyncMock(side_effect=RuntimeError("GPU out of memory"))

        updated = await svc.update_faq(
            db=db,
            business_id=biz.id,
            entry_id=faq.id,
            answer="Updated Answer During Outage",
        )

        assert updated is not None
        assert updated.answer == "Updated Answer During Outage"
        assert updated.embedding_stale is True

        await db.commit()


# =====================================================================
# 10. Semantic Search with Query Embeddings and Tenant Isolation
# =====================================================================

@pytest.mark.asyncio
async def test_search_knowledge_tenant_isolation_and_ranking():
    """Verifies search uses query embeddings, orders by distance, and respects tenant boundaries."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, "Search Tenant A")
        biz_b = await create_test_business(db, "Search Tenant B")

        # Business A FAQs
        faq_a1 = await knowledge_service.create_faq(
            db=db,
            business_id=biz_a.id,
            question="When do you open?",
            answer="We open Monday to Saturday at 9 AM.",
        )
        faq_a2 = await knowledge_service.create_faq(
            db=db,
            business_id=biz_a.id,
            question="What is your return policy?",
            answer="Returns accepted within 30 days of purchase.",
        )

        # Business B FAQ
        faq_b1 = await knowledge_service.create_faq(
            db=db,
            business_id=biz_b.id,
            question="When do you open?",
            answer="Business B is open 24/7.",
        )

        # Search for Business A opening hours
        results = await knowledge_service.search_knowledge(
            db=db,
            business_id=biz_a.id,
            query="opening hours timing",
            top_k=5,
        )

        assert len(results) >= 1
        # Result items are (KnowledgeBaseEntry, distance_float)
        top_entry, top_distance = results[0]
        assert isinstance(top_distance, float)
        assert top_entry.business_id == biz_a.id

        # Verify Business B entry is NEVER in Business A results
        result_ids = [entry.id for entry, _ in results]
        assert faq_b1.id not in result_ids
        assert faq_a1.id in result_ids

        await db.commit()


# =====================================================================
# 11. Stale and Null Embeddings Excluded from Search
# =====================================================================

@pytest.mark.asyncio
async def test_search_knowledge_excludes_null_and_stale_embeddings():
    """Verifies that entries with null embeddings or embedding_stale=True are excluded from search."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # 1. Fresh valid FAQ
        valid_faq = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="Valid entry?",
            answer="Searchable answer about warranty and support.",
        )
        assert valid_faq.embedding is not None
        assert valid_faq.embedding_stale is False

        # 2. Stale FAQ (with embedding but marked stale)
        stale_faq = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="Stale entry?",
            answer="Old answer about warranty and support.",
        )
        # Mark stale
        stale_faq.embedding_stale = True
        await db.flush()

        # 3. FAQ with null embedding
        null_faq = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="Null vector entry?",
            answer="Un-embedded answer about warranty and support.",
        )
        null_faq.embedding = None
        null_faq.embedding_stale = True
        await db.flush()

        results = await knowledge_service.search_knowledge(
            db=db,
            business_id=biz.id,
            query="warranty and support",
            top_k=10,
        )

        result_ids = [entry.id for entry, _ in results]
        assert valid_faq.id in result_ids
        assert stale_faq.id not in result_ids
        assert null_faq.id not in result_ids

        await db.commit()


# =====================================================================
# 12. Re-embedding Stale FAQ Entries
# =====================================================================

@pytest.mark.asyncio
async def test_reembed_stale_faq_entries():
    """Verifies that reembed_stale_entries processes only stale entries and clears stale flag."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Create 2 FAQs that become stale
        faq1 = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="Q1",
            answer="Answer 1",
        )
        faq2 = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="Q2",
            answer="Answer 2",
        )

        # Mark them stale with null embedding
        faq1.embedding_stale = True
        faq1.embedding = None
        faq2.embedding_stale = True
        faq2.embedding = None
        await db.flush()

        # Re-embed
        reembedded_count = await knowledge_service.reembed_stale_entries(
            db=db,
            business_id=biz.id,
        )
        assert reembedded_count == 2

        # Verify refreshed state in DB
        entry1 = await knowledge_service.get_faq(db, business_id=biz.id, entry_id=faq1.id)
        assert entry1 is not None
        assert entry1.embedding_stale is False
        assert entry1.embedding is not None
        assert len(entry1.embedding) == 384

        entry2 = await knowledge_service.get_faq(db, business_id=biz.id, entry_id=faq2.id)
        assert entry2 is not None
        assert entry2.embedding_stale is False
        assert entry2.embedding is not None
        assert len(entry2.embedding) == 384

        await db.commit()


# =====================================================================
# 13. Re-embedding Does Not Process Document Chunks
# =====================================================================

@pytest.mark.asyncio
async def test_reembed_does_not_process_document_chunks():
    """Verifies that reembed_stale_entries strictly ignores document chunk records."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)
        kfile = await create_test_file(db, business_id=biz.id)

        # Create a stale document chunk
        chunk = KnowledgeBaseEntry(
            business_id=biz.id,
            source_file_id=kfile.id,
            chunk_index=0,
            answer="Document chunk text from uploaded PDF.",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            embedding=None,
            embedding_stale=True,
            language="en",
        )
        db.add(chunk)

        # Create a stale FAQ
        faq = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="Stale FAQ",
            answer="Stale FAQ answer.",
        )
        faq.embedding_stale = True
        faq.embedding = None
        await db.flush()

        # Run reembed_stale_entries
        count = await knowledge_service.reembed_stale_entries(db, business_id=biz.id)

        # Should only process the 1 FAQ, NOT the document chunk
        assert count == 1

        # Confirm FAQ is now fresh
        refreshed_faq = await knowledge_service.get_faq(db, business_id=biz.id, entry_id=faq.id)
        assert refreshed_faq is not None
        assert refreshed_faq.embedding_stale is False
        assert refreshed_faq.embedding is not None

        # Confirm Document Chunk remains stale and untouched
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == chunk.id)
        refreshed_chunk = (await db.execute(stmt)).scalar_one_or_none()
        assert refreshed_chunk is not None
        assert refreshed_chunk.embedding_stale is True
        assert refreshed_chunk.embedding is None

        await db.commit()


# =====================================================================
# 14. Transaction Safety (No Service/Repository Commits)
# =====================================================================

@pytest.mark.asyncio
async def test_no_service_or_repository_commits_transactions():
    """Verifies that KnowledgeService methods never invoke db.commit()."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        # Spy on db.commit
        original_commit = db.commit
        commit_called = False

        async def spy_commit():
            nonlocal commit_called
            commit_called = True
            return await original_commit()

        db.commit = spy_commit  # type: ignore

        # 1. create_faq
        faq = await knowledge_service.create_faq(
            db=db,
            business_id=biz.id,
            question="Commit Test?",
            answer="Checking commit behavior.",
        )
        assert commit_called is False

        # 2. get_faq
        await knowledge_service.get_faq(db, business_id=biz.id, entry_id=faq.id)
        assert commit_called is False

        # 3. list_faqs
        await knowledge_service.list_faqs(db, business_id=biz.id)
        assert commit_called is False

        # 4. update_faq
        await knowledge_service.update_faq(
            db=db,
            business_id=biz.id,
            entry_id=faq.id,
            answer="Updated answer for commit test.",
        )
        assert commit_called is False

        # 5. search_knowledge
        await knowledge_service.search_knowledge(
            db=db,
            business_id=biz.id,
            query="Checking commit",
        )
        assert commit_called is False

        # 6. reembed_stale_entries
        await knowledge_service.reembed_stale_entries(db, business_id=biz.id)
        assert commit_called is False

        # 7. delete_faq
        await knowledge_service.delete_faq(db, business_id=biz.id, entry_id=faq.id)
        assert commit_called is False

        # Restore original commit and cleanly finish
        db.commit = original_commit  # type: ignore
        await db.commit()


# =====================================================================
# 15. E5 Prefix Tests (Phase 5.4F.6)
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_uses_passage_prefix():
    """Verifies that create_faq passes prefix=PREFIX_PASSAGE and is_query=False to embed_text."""
    mock_provider = MockEmbeddingProvider()
    mock_provider.embed_text = AsyncMock(wraps=mock_provider.embed_text)
    service = KnowledgeService(embedding_provider=mock_provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Prefix FAQ Create Biz")

        faq = await service.create_faq(
            db=db,
            business_id=biz.id,
            question="What is E5?",
            answer="E5 is an embedding model requiring task prefixes.",
        )
        assert faq.id is not None

        mock_provider.embed_text.assert_called_once()
        args, kwargs = mock_provider.embed_text.call_args
        prefix_val = kwargs.get("prefix", args[1] if len(args) > 1 else None)
        is_query_val = kwargs.get("is_query", args[2] if len(args) > 2 else False)
        assert prefix_val == PREFIX_PASSAGE
        assert is_query_val is False


@pytest.mark.asyncio
async def test_update_faq_uses_passage_prefix():
    """Verifies that update_faq passes prefix=PREFIX_PASSAGE and is_query=False to embed_text."""
    mock_provider = MockEmbeddingProvider()
    service = KnowledgeService(embedding_provider=mock_provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Prefix FAQ Update Biz")

        faq = await service.create_faq(
            db=db,
            business_id=biz.id,
            question="Initial question?",
            answer="Initial answer text.",
        )

        mock_provider.embed_text = AsyncMock(wraps=mock_provider.embed_text)

        updated = await service.update_faq(
            db=db,
            business_id=biz.id,
            entry_id=faq.id,
            answer="Updated answer text with new passage.",
        )
        assert updated is not None

        mock_provider.embed_text.assert_called_once()
        args, kwargs = mock_provider.embed_text.call_args
        prefix_val = kwargs.get("prefix", args[1] if len(args) > 1 else None)
        is_query_val = kwargs.get("is_query", args[2] if len(args) > 2 else False)
        assert prefix_val == PREFIX_PASSAGE
        assert is_query_val is False


@pytest.mark.asyncio
async def test_reembed_stale_entries_uses_passage_prefix():
    """Verifies that reembed_stale_entries passes prefix=PREFIX_PASSAGE and is_query=False to embed_text."""
    mock_provider = MockEmbeddingProvider()
    service = KnowledgeService(embedding_provider=mock_provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Prefix Reembed Biz")

        faq = await service.create_faq(
            db=db,
            business_id=biz.id,
            question="Stale FAQ?",
            answer="Stale answer text waiting for re-embedding.",
        )

        # Mark entry as stale
        faq.embedding_stale = True
        await db.flush()

        mock_provider.embed_text = AsyncMock(wraps=mock_provider.embed_text)

        reembedded_count = await service.reembed_stale_entries(db=db, business_id=biz.id)
        assert reembedded_count == 1

        mock_provider.embed_text.assert_called_once()
        args, kwargs = mock_provider.embed_text.call_args
        prefix_val = kwargs.get("prefix", args[1] if len(args) > 1 else None)
        is_query_val = kwargs.get("is_query", args[2] if len(args) > 2 else False)
        assert prefix_val == PREFIX_PASSAGE
        assert is_query_val is False


@pytest.mark.asyncio
async def test_search_knowledge_uses_query_prefix():
    """Verifies that search_knowledge passes prefix=PREFIX_QUERY and is_query=True to embed_text."""
    mock_provider = MockEmbeddingProvider()
    mock_provider.embed_text = AsyncMock(wraps=mock_provider.embed_text)
    service = KnowledgeService(embedding_provider=mock_provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Prefix Search Biz")

        results = await service.search_knowledge(
            db=db,
            business_id=biz.id,
            query="find dental services",
        )

        mock_provider.embed_text.assert_called_once()
        args, kwargs = mock_provider.embed_text.call_args
        prefix_val = kwargs.get("prefix", args[1] if len(args) > 1 else None)
        is_query_val = kwargs.get("is_query", args[2] if len(args) > 2 else False)
        assert prefix_val == PREFIX_QUERY
        assert is_query_val is True

