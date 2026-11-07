"""Comprehensive unit and concurrency tests for Phase 5.4F.9B: FAQ Re-embedding Infrastructure.

Verifies:
1. Dry-run immutability (zero database writes or vector updates).
2. Live batch re-embedding updates embedding_model to active E5 identifier, marks stale=False, and verifies 384d vector.
3. Strict preservation of FAQ content (question, answer, tags, language), business ownership, and created_at.
4. Tenant-scoped batch execution (Tenant A execution never modifies Tenant B).
5. Immediate semantic search discovery after re-embedding.
6. Concurrent worker execution using FOR UPDATE SKIP LOCKED without collisions or duplicate processing.
7. Provider failure handling (clean rollback, never labels failed vectors as E5).
8. Explicit isolation of empty/whitespace answers without crashing the batch.
9. Retry safety and idempotency (already re-embedded entries are skipped on subsequent runs).
"""

import asyncio
import math
from unittest.mock import AsyncMock
import uuid
import pytest
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.knowledge import (
    ACTIVE_EMBEDDING_MODEL,
    LEGACY_UNKNOWN_EMBEDDING_MODEL,
    EMBEDDING_VECTOR_DIMENSION,
    KnowledgeBaseEntry,
    KnowledgeLanguage,
    KnowledgeSourceType,
)
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.repositories.knowledge_repository import knowledge_repository
from app.services.knowledge_service import KnowledgeService, ReembedBatchResult


# =====================================================================
# Database Helpers
# =====================================================================

async def create_test_business(db, name: str = "FAQ Reembed Biz") -> Business:
    biz = Business(
        name=name,
        slug=f"faq-re-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.flush()
    await db.commit()
    await db.refresh(biz)
    return biz


async def create_legacy_faq(
    db,
    business_id: uuid.UUID,
    question: str = "Legacy FAQ question?",
    answer: str = "Legacy FAQ answer.",
    model: str = LEGACY_UNKNOWN_EMBEDDING_MODEL,
    stale: bool = False,
    has_vector: bool = True,
) -> KnowledgeBaseEntry:
    entry = KnowledgeBaseEntry(
        business_id=business_id,
        question=question,
        answer=answer,
        tags=["legacy", "test"],
        language=KnowledgeLanguage.EN.value,
        source_type=KnowledgeSourceType.FAQ.value,
        embedding=[0.05] * 384 if has_vector else None,
        embedding_stale=stale,
        embedding_model=model if has_vector else None,
    )
    db.add(entry)
    await db.flush()
    await db.commit()
    await db.refresh(entry)
    return entry


# =====================================================================
# 1. Dry Run Immutability Test
# =====================================================================

@pytest.mark.asyncio
async def test_reembed_dry_run_immutability():
    """Verifies that dry_run=True scans eligible entries but modifies zero database records."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Dry Run Biz")
        faq1 = await create_legacy_faq(db, biz.id, question="Q1?", answer="Answer 1")
        faq2 = await create_legacy_faq(db, biz.id, question="Q2?", answer="Answer 2")

        original_updated_at1 = faq1.updated_at
        original_updated_at2 = faq2.updated_at

        # Execute dry-run
        result: ReembedBatchResult = await service.reembed_faq_batch(
            db=db,
            business_id=biz.id,
            batch_size=50,
            dry_run=True,
        )

        assert result.dry_run is True
        assert result.scanned == 2
        assert result.reembedded == 0
        assert result.failed == 0
        assert result.remaining >= 2
        assert set(result.entry_ids) == {faq1.id, faq2.id}

        # Verify database records are 100% untouched
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.business_id == biz.id)
        entries = (await db.execute(stmt)).scalars().all()
        for e in entries:
            assert e.embedding_model == LEGACY_UNKNOWN_EMBEDDING_MODEL
            assert e.embedding == [0.05] * 384
            assert e.embedding_stale is False
            if e.id == faq1.id:
                assert e.updated_at == original_updated_at1
            elif e.id == faq2.id:
                assert e.updated_at == original_updated_at2


# =====================================================================
# 2. Live Batch Re-embedding & E5 Vector Validation
# =====================================================================

@pytest.mark.asyncio
async def test_reembed_batch_e5_labeling_and_vector_validation():
    """Verifies that live batch execution persists active E5 model label and valid 384d unit vectors."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Live Reembed Biz")
        faq1 = await create_legacy_faq(db, biz.id, question="Hours?", answer="Open 9am to 5pm")
        faq2 = await create_legacy_faq(db, biz.id, question="Fee?", answer="Initial fee is 50 USD")

        result = await service.reembed_faq_batch(
            db=db,
            business_id=biz.id,
            batch_size=50,
            dry_run=False,
        )
        await db.commit()

        assert result.dry_run is False
        assert result.scanned == 2
        assert result.reembedded == 2
        assert result.failed == 0

        # Verify DB updates
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.business_id == biz.id)
        entries = (await db.execute(stmt)).scalars().all()

        for e in entries:
            assert e.embedding_model == ACTIVE_EMBEDDING_MODEL
            assert e.embedding_stale is False
            assert e.embedding is not None
            assert len(e.embedding) == EMBEDDING_VECTOR_DIMENSION
            assert all(math.isfinite(x) for x in e.embedding)

            norm = math.sqrt(sum(x * x for x in e.embedding))
            assert 0.99 <= norm <= 1.01


# =====================================================================
# 3. Content and Ownership Preservation Test
# =====================================================================

@pytest.mark.asyncio
async def test_reembed_preserves_content_tags_and_ownership():
    """Verifies that re-embedding never mutates question, answer, tags, language, or tenant ownership."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Content Preservation Biz")
        faq = await create_legacy_faq(
            db=db,
            business_id=biz.id,
            question="What are your dental hygiene protocols?",
            answer="We sterilize all dental instruments using a medical-grade autoclave.",
        )
        original_created_at = faq.created_at

        await service.reembed_faq_batch(db=db, business_id=biz.id, batch_size=50, dry_run=False)
        await db.commit()

        # Re-fetch
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq.id)
        refetched = (await db.execute(stmt)).scalar_one()

        assert refetched.business_id == biz.id
        assert refetched.question == "What are your dental hygiene protocols?"
        assert refetched.answer == "We sterilize all dental instruments using a medical-grade autoclave."
        assert refetched.tags == ["legacy", "test"]
        assert refetched.language == KnowledgeLanguage.EN.value
        assert refetched.source_type == KnowledgeSourceType.FAQ.value
        assert refetched.created_at == original_created_at
        assert refetched.embedding_model == ACTIVE_EMBEDDING_MODEL


# =====================================================================
# 4. Tenant Isolation in Batch Execution
# =====================================================================

@pytest.mark.asyncio
async def test_reembed_batch_enforces_tenant_isolation():
    """Verifies that re-embedding Tenant A never touches or updates Tenant B's legacy FAQs."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Tenant A Isolation")
        biz_b = await create_test_business(db, name="Tenant B Isolation")

        faq_a = await create_legacy_faq(db, biz_a.id, question="A question?", answer="A answer")
        faq_b = await create_legacy_faq(db, biz_b.id, question="B question?", answer="B answer")

        # Execute only for Tenant A
        result = await service.reembed_faq_batch(
            db=db,
            business_id=biz_a.id,
            batch_size=50,
            dry_run=False,
        )
        await db.commit()

        assert result.reembedded == 1
        assert faq_a.id in result.entry_ids
        assert faq_b.id not in result.entry_ids

        # Verify Tenant A updated
        stmt_a = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq_a.id)
        res_a = (await db.execute(stmt_a)).scalar_one()
        assert res_a.embedding_model == ACTIVE_EMBEDDING_MODEL

        # Verify Tenant B completely untouched
        stmt_b = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq_b.id)
        res_b = (await db.execute(stmt_b)).scalar_one()
        assert res_b.embedding_model == LEGACY_UNKNOWN_EMBEDDING_MODEL


# =====================================================================
# 5. Immediate Search Discovery After Re-embedding
# =====================================================================

@pytest.mark.asyncio
async def test_search_discovers_faq_immediately_after_reembedding():
    """Verifies that a quarantined FAQ becomes discoverable in search immediately after re-embedding."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)
    answer_text = "We specialize in orthodontic aligners and root canal treatment."

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Search Discovery Biz")
        faq = await create_legacy_faq(
            db=db,
            business_id=biz.id,
            question="Orthodontics?",
            answer=answer_text,
            model=LEGACY_UNKNOWN_EMBEDDING_MODEL,
        )

        # 1. Search before re-embedding: MUST RETURN ZERO (quarantined)
        before_results = await service.search_knowledge(
            db=db,
            business_id=biz.id,
            query="orthodontic aligners",
        )
        assert faq.id not in [e.id for e, _ in before_results]

        # 2. Re-embed batch
        await service.reembed_faq_batch(db=db, business_id=biz.id, dry_run=False)
        await db.commit()

        # 3. Search after re-embedding: MUST DISCOVER THE ENTRY
        after_results = await service.search_knowledge(
            db=db,
            business_id=biz.id,
            query="orthodontic aligners",
        )
        matched_ids = [e.id for e, _ in after_results]
        assert faq.id in matched_ids


# =====================================================================
# 6. Concurrency Safety with FOR UPDATE SKIP LOCKED
# =====================================================================

@pytest.mark.asyncio
async def test_concurrency_skip_locked_parallel_workers():
    """Verifies that 2 concurrent workers execute disjoint batches in parallel without collisions."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Concurrency Parallel Biz")
        # Create 10 legacy FAQs
        created_ids = []
        for i in range(10):
            f = await create_legacy_faq(db, biz.id, question=f"Q{i}?", answer=f"Parallel Answer {i}")
            created_ids.append(f.id)

    # Worker task
    async def worker_job():
        async with async_session_factory() as session:
            res = await service.reembed_faq_batch(
                db=session,
                business_id=biz.id,
                batch_size=5,
                dry_run=False,
            )
            await session.commit()
            return res

    # Run both workers in parallel using asyncio.gather
    res1, res2 = await asyncio.gather(worker_job(), worker_job())

    # Disjoint check: no FAQ processed by both workers
    intersection = set(res1.entry_ids).intersection(set(res2.entry_ids))
    assert len(intersection) == 0, f"Workers processed overlapping entries: {intersection}"

    # Both workers should have processed 5 entries each
    assert res1.reembedded == 5
    assert res2.reembedded == 5
    assert set(res1.entry_ids + res2.entry_ids) == set(created_ids)


# =====================================================================
# 7. Provider Failure Rollback (Never Label as E5)
# =====================================================================

@pytest.mark.asyncio
async def test_provider_failure_rolls_back_and_never_labels_e5():
    """Verifies that when embedding fails, transaction rolls back and vectors are not labeled as E5."""
    failing_provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    failing_provider.embed_batch = AsyncMock(side_effect=RuntimeError("Provider hardware failure"))
    service = KnowledgeService(embedding_provider=failing_provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Provider Failure Biz")
        faq = await create_legacy_faq(db, biz.id, question="Fail Q?", answer="Fail Answer")
        faq_id = faq.id

        with pytest.raises(RuntimeError, match="Provider hardware failure"):
            await service.reembed_faq_batch(db=db, business_id=biz.id, batch_size=50, dry_run=False)
        await db.rollback()

        # Re-fetch from fresh session to verify database state
        async with async_session_factory() as check_db:
            stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq_id)
            entry = (await check_db.execute(stmt)).scalar_one()
            assert entry.embedding_model == LEGACY_UNKNOWN_EMBEDDING_MODEL
            assert entry.embedding == [0.05] * 384
            assert entry.embedding_stale is False


# =====================================================================
# 8. Empty / Whitespace Answer Handling (Excluded from Selection)
# =====================================================================

@pytest.mark.asyncio
async def test_whitespace_answer_excluded_from_selection_and_remains_unchanged():
    """Verifies that an FAQ with empty or whitespace answer is excluded from selection and remains untouched."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Whitespace Excluded Biz")
        valid_faq = await create_legacy_faq(db, biz.id, question="Valid?", answer="Valid content")
        empty_faq = await create_legacy_faq(
            db, biz.id, question="Empty?", answer="   ", model=LEGACY_UNKNOWN_EMBEDDING_MODEL
        )
        empty_id = empty_faq.id

        # 1. Count checks: count_faqs_needing_reembed excludes blank answers
        eligible_count = await knowledge_repository.count_faqs_needing_reembed(db, business_id=biz.id)
        assert eligible_count == 1

        # count_faqs_with_blank_answer identifies the invalid record
        invalid_count = await knowledge_repository.count_faqs_with_blank_answer(db, business_id=biz.id)
        assert invalid_count == 1

        # 2. List check: only valid_faq is selected
        selected_entries = await knowledge_repository.list_faqs_needing_reembed(db, business_id=biz.id)
        assert len(selected_entries) == 1
        assert selected_entries[0].id == valid_faq.id

        # 3. Batch re-embed processes only the valid FAQ
        result = await service.reembed_faq_batch(db=db, business_id=biz.id, batch_size=50, dry_run=False)
        await db.commit()

        assert result.scanned == 1
        assert result.reembedded == 1
        assert result.failed == 0
        assert result.remaining == 0

        # Valid FAQ updated to E5
        stmt_v = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == valid_faq.id)
        res_v = (await db.execute(stmt_v)).scalar_one()
        assert res_v.embedding_model == ACTIVE_EMBEDDING_MODEL
        assert res_v.embedding_stale is False

        # Empty FAQ remains COMPLETELY UNCHANGED in database
        stmt_e = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == empty_id)
        res_e = (await db.execute(stmt_e)).scalar_one()
        assert res_e.embedding_model == LEGACY_UNKNOWN_EMBEDDING_MODEL
        assert res_e.embedding == [0.05] * 384
        assert res_e.embedding_stale is False
        assert res_e.answer == "   "


# =====================================================================
# 9. Idempotency & Remaining Count Test
# =====================================================================

@pytest.mark.asyncio
async def test_reembed_batch_idempotency():
    """Verifies that subsequent runs skip already re-embedded FAQs cleanly."""
    provider = MockEmbeddingProvider(model_name=ACTIVE_EMBEDDING_MODEL)
    service = KnowledgeService(embedding_provider=provider)

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Idempotency Biz")
        await create_legacy_faq(db, biz.id, question="Q?", answer="Answer")

        # First run: processes 1
        res1 = await service.reembed_faq_batch(db=db, business_id=biz.id, dry_run=False)
        await db.commit()
        assert res1.reembedded == 1
        assert res1.remaining == 0

        # Second run: 0 remaining
        res2 = await service.reembed_faq_batch(db=db, business_id=biz.id, dry_run=False)
        await db.commit()
        assert res2.scanned == 0
        assert res2.reembedded == 0
        assert res2.remaining == 0


# =====================================================================
# 10. Blank Answer Exclusions & Count/Selection Agreement
# =====================================================================

@pytest.mark.asyncio
async def test_blank_and_whitespace_answers_excluded_and_counts_agree():
    """Verifies that blank/whitespace answers are excluded from selection and count matches list."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Blank Exclude Agreement Biz")
        await create_legacy_faq(db, biz.id, question="Valid 1?", answer="Valid Answer 1")
        await create_legacy_faq(db, biz.id, question="Valid 2?", answer="Valid Answer 2")
        await create_legacy_faq(db, biz.id, question="Blank?", answer="")
        await create_legacy_faq(db, biz.id, question="Whitespace?", answer="     ")
        # An active E5 FAQ that does not need re-embedding
        faq_e5 = KnowledgeBaseEntry(
            business_id=biz.id,
            source_type=KnowledgeSourceType.FAQ.value,
            question="Active E5?",
            answer="Already good",
            embedding_model=ACTIVE_EMBEDDING_MODEL,
            embedding=[0.05] * 384,
            embedding_stale=False,
        )
        db.add(faq_e5)
        await db.commit()

        # Count of entries needing re-embed: exactly 2
        count_needing = await knowledge_repository.count_faqs_needing_reembed(db, business_id=biz.id)
        assert count_needing == 2

        # Count of invalid blank/whitespace entries: exactly 2
        count_blank = await knowledge_repository.count_faqs_with_blank_answer(db, business_id=biz.id)
        assert count_blank == 2

        # Selection list: exactly 2, matches count_needing
        entries = await knowledge_repository.list_faqs_needing_reembed(db, business_id=biz.id, limit=50)
        assert len(entries) == count_needing
        assert all(e.answer.strip() != "" for e in entries)


# =====================================================================
# 11. CLI Termination & Infinite Loop Prevention
# =====================================================================

@pytest.mark.asyncio
async def test_cli_terminates_when_no_progress_possible(monkeypatch, capsys):
    """Verifies that CLI terminates cleanly with error code 1 when a batch makes 0 progress."""
    from app.commands.reembed_faqs import run_reembed

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="CLI No Progress Biz")
        await create_legacy_faq(db, biz.id, question="Stuck Q?", answer="Stuck Answer")

    # Mock reembed_faq_batch to simulate 0 reembedded progress
    async def mock_no_progress(**kwargs):
        return ReembedBatchResult(scanned=1, reembedded=0, failed=1, remaining=1, dry_run=False, entry_ids=[])

    monkeypatch.setattr("app.commands.reembed_faqs.knowledge_service.reembed_faq_batch", mock_no_progress)

    exit_code = await run_reembed(business_id_str=str(biz.id), batch_size=10)
    assert exit_code == 1

    captured = capsys.readouterr().out
    assert "Batch made no progress" in captured
    assert "Halting to avoid infinite loop" in captured
    assert "All eligible FAQ entries have been successfully processed" not in captured


# =====================================================================
# 12. CLI Incomplete Completion Reporting
# =====================================================================

@pytest.mark.asyncio
async def test_cli_does_not_claim_completion_with_remaining_entries(capsys):
    """Verifies that when stopped by max_batches with remaining entries, CLI does not claim completion."""
    from app.commands.reembed_faqs import run_reembed

    async with async_session_factory() as db:
        biz = await create_test_business(db, name="CLI Incomplete Biz")
        for i in range(5):
            await create_legacy_faq(db, biz.id, question=f"Q{i}?", answer=f"Answer {i}")

    # Process only 1 batch of size 2 -> 3 entries remain
    exit_code = await run_reembed(business_id_str=str(biz.id), batch_size=2, max_batches=1)
    assert exit_code == 0

    captured = capsys.readouterr().out
    assert "Reached maximum requested batches (1). Halting." in captured
    assert "Total Remaining Eligible: 3" in captured
    assert "Process completed with 3 eligible entries remaining. Incomplete." in captured
    assert "All eligible FAQ entries have been successfully processed" not in captured

