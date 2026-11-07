"""Tests for the Demo FAQ Seeding script (Phase 5.5A.3)."""

import json
from pathlib import Path
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text, select, func
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.business import Business
from app.models.knowledge import KnowledgeLanguage, KnowledgeBaseEntry
from app.services.knowledge_service import knowledge_service
from scripts.seed_demo_faqs import (
    DEFAULT_DATASET_PATH,
    EXPECTED_FAQ_COUNT,
    execute_seed_transaction,
    find_existing_duplicates,
    load_demo_faqs_from_markdown,
    verify_environment_and_targets,
    TARGET_BUSINESS_ID,
    TARGET_OWNER_ID,
)


async def create_isolated_test_business(db: AsyncSession) -> Business:
    """Helper to persist a temporary business tenant in the test database."""
    biz = Business(
        name="Seed Demo Test Biz",
        slug=f"seed-test-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(biz)
    await db.commit()
    await db.refresh(biz)
    return biz


def test_load_demo_faqs_success():
    """Verifies that the canonical demo dataset loads and passes all validations."""
    entries = load_demo_faqs_from_markdown(DEFAULT_DATASET_PATH)

    assert len(entries) == EXPECTED_FAQ_COUNT
    assert len(entries) == 12

    # Check language breakdown
    lang_counts = {l.value: 0 for l in KnowledgeLanguage}
    for item in entries:
        assert "question" in item
        assert "answer" in item
        assert "tags" in item
        assert "language" in item
        assert "category" in item
        assert len(item["answer"].strip()) > 0
        lang_counts[item["language"]] += 1

    assert lang_counts[KnowledgeLanguage.EN.value] == 4
    assert lang_counts[KnowledgeLanguage.UR.value] == 4
    assert lang_counts[KnowledgeLanguage.MIXED.value] == 4


def test_load_demo_faqs_file_not_found(tmp_path: Path):
    """Verifies FileNotFoundError when markdown dataset does not exist."""
    missing_file = tmp_path / "non_existent.md"
    with pytest.raises(FileNotFoundError, match="Demo FAQ dataset not found"):
        load_demo_faqs_from_markdown(missing_file)


def test_load_demo_faqs_no_json_fence(tmp_path: Path):
    """Verifies ValueError when markdown file lacks ```json code fence."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("# Demo FAQs\n\nNo json fence here.", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to find valid JSON code fence"):
        load_demo_faqs_from_markdown(bad_file)


def test_load_demo_faqs_invalid_count(tmp_path: Path):
    """Verifies ValueError when JSON contains fewer or more than 12 entries."""
    bad_file = tmp_path / "bad_count.md"
    bad_json = [{"id": 1, "answer": "Test answer", "language": "en"}]
    bad_file.write_text(f"```json\n{json.dumps(bad_json)}\n```", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected exactly 12 FAQ entries"):
        load_demo_faqs_from_markdown(bad_file)


def test_load_demo_faqs_schema_validation_failure(tmp_path: Path):
    """Verifies ValueError when an entry has an empty answer."""
    bad_file = tmp_path / "bad_schema.md"
    bad_entries = [
        {"id": i, "question": f"Q{i}", "answer": "" if i == 1 else "Valid", "language": "en"}
        for i in range(1, 13)
    ]
    bad_file.write_text(f"```json\n{json.dumps(bad_entries)}\n```", encoding="utf-8")
    with pytest.raises(ValueError, match="Validation failed for FAQ entry #1"):
        load_demo_faqs_from_markdown(bad_file)


@pytest.mark.asyncio
async def test_find_existing_duplicates_logic():
    """Verifies that find_existing_duplicates correctly flags matches by question or answer."""
    session = AsyncMock()

    existing_entry_1 = MagicMock(spec=KnowledgeBaseEntry)
    existing_entry_1.id = uuid.uuid4()
    existing_entry_1.language = "en"
    existing_entry_1.question = "Existing Question?"
    existing_entry_1.answer = "Existing Answer."

    with patch(
        "scripts.seed_demo_faqs.knowledge_repository.list_by_business",
        new=AsyncMock(return_value=[existing_entry_1]),
    ):
        items = [
            {
                "id": 1,
                "language": "en",
                "question": "Existing Question?",
                "answer": "A different answer text.",
            },
            {
                "id": 2,
                "language": "en",
                "question": "A completely new question?",
                "answer": "Existing Answer.",
            },
            {
                "id": 3,
                "language": "en",
                "question": "Brand new question?",
                "answer": "Brand new unique answer.",
            },
        ]

        checked = await find_existing_duplicates(session, items)

        # Item 1 matches existing_entry_1 by (language, question)
        assert checked[0][1] is True
        assert checked[0][2] == existing_entry_1.id

        # Item 2 matches existing_entry_1 by answer
        assert checked[1][1] is True
        assert checked[1][2] == existing_entry_1.id

        # Item 3 is completely new
        assert checked[2][1] is False
        assert checked[2][2] is None


@pytest.mark.asyncio
async def test_transaction_autobegin_conflict_reproduction():
    """Reproduces the exact SQLAlchemy error when session.begin() is called after SELECTs."""
    async with async_session_factory() as session:
        # 1. Execute a SELECT query to simulate target verification
        await session.execute(text("SELECT 1"))
        assert session.in_transaction() is True

        # 2. Directly calling session.begin() must raise InvalidRequestError
        with pytest.raises(InvalidRequestError, match="A transaction is already begun on this Session"):
            async with session.begin():
                pass

        # Clean up
        if session.in_transaction():
            await session.rollback()


@pytest.mark.asyncio
async def test_execute_seed_transaction_resolves_autobegin_and_commits():
    """Verifies that execute_seed_transaction clears the prior read transaction and commits atomically."""
    async with async_session_factory() as session:
        test_biz = await create_isolated_test_business(session)
        test_biz_id = test_biz.id

        # Simulate pre-existing verification queries that leave an open read transaction
        await session.execute(text("SELECT 1"))
        assert session.in_transaction() is True

        items = [
            {
                "id": 1,
                "category": "services",
                "language": "en",
                "question": f"Question 1 {uuid.uuid4().hex[:6]}?",
                "answer": "Answer 1 for test.",
                "tags": ["test"],
            },
            {
                "id": 2,
                "category": "services",
                "language": "en",
                "question": f"Question 2 {uuid.uuid4().hex[:6]}?",
                "answer": "Answer 2 for test.",
                "tags": ["test"],
            },
        ]
        checked_faqs = [(items[0], False, None), (items[1], False, None)]

        # This should succeed without raising InvalidRequestError
        inserted, skipped = await execute_seed_transaction(
            session=session,
            business_id=test_biz_id,
            checked_faqs=checked_faqs,
            verbose=False,
        )

        assert inserted == 2
        assert skipped == 0

        # Verify both entries were actually committed in the database
        stmt = select(func.count(KnowledgeBaseEntry.id)).where(
            KnowledgeBaseEntry.business_id == test_biz_id
        )
        count = (await session.execute(stmt)).scalar()
        assert count == 2


@pytest.mark.asyncio
async def test_execute_seed_transaction_atomicity_and_rollback_on_failure():
    """Verifies that if any FAQ creation fails, the entire transaction rolls back."""
    async with async_session_factory() as session:
        test_biz = await create_isolated_test_business(session)
        test_biz_id = test_biz.id

        # Simulate prior SELECT
        await session.execute(text("SELECT 1"))
        assert session.in_transaction() is True

        items = [
            {
                "id": 1,
                "category": "services",
                "language": "en",
                "question": f"Question 1 {uuid.uuid4().hex[:6]}?",
                "answer": "Answer 1 for rollback test.",
                "tags": ["test"],
            },
            {
                "id": 2,
                "category": "services",
                "language": "en",
                "question": f"Question 2 {uuid.uuid4().hex[:6]}?",
                "answer": "Answer 2 for rollback test.",
                "tags": ["test"],
            },
        ]
        checked_faqs = [(items[0], False, None), (items[1], False, None)]

        # Simulate a failure on the second entry during create_faq
        call_count = 0
        original_create_faq = knowledge_service.create_faq

        async def mock_create_faq(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Simulated embedding/provider failure on second entry")
            return await original_create_faq(*args, **kwargs)

        with patch.object(knowledge_service, "create_faq", side_effect=mock_create_faq):
            with pytest.raises(RuntimeError, match="Simulated embedding/provider failure"):
                await execute_seed_transaction(
                    session=session,
                    business_id=test_biz_id,
                    checked_faqs=checked_faqs,
                    verbose=False,
                )

        # Verify atomic rollback: Entry 1 must NOT be in the database
        stmt = select(func.count(KnowledgeBaseEntry.id)).where(
            KnowledgeBaseEntry.business_id == test_biz_id
        )
        count = (await session.execute(stmt)).scalar()
        assert count == 0, f"Expected 0 entries due to atomic rollback, found {count}"


@pytest.mark.asyncio
async def test_execute_seed_transaction_skips_duplicates():
    """Verifies that execute_seed_transaction skips items marked as duplicates."""
    async with async_session_factory() as session:
        test_biz = await create_isolated_test_business(session)
        test_biz_id = test_biz.id

        items = [
            {
                "id": 1,
                "category": "services",
                "language": "en",
                "question": f"New Question {uuid.uuid4().hex[:6]}?",
                "answer": "New Answer.",
                "tags": ["test"],
            },
            {
                "id": 2,
                "category": "services",
                "language": "en",
                "question": "Duplicate Question?",
                "answer": "Duplicate Answer.",
                "tags": ["test"],
            },
        ]
        existing_id = uuid.uuid4()
        checked_faqs = [
            (items[0], False, None),
            (items[1], True, existing_id),
        ]

        inserted, skipped = await execute_seed_transaction(
            session=session,
            business_id=test_biz_id,
            checked_faqs=checked_faqs,
            verbose=False,
        )

        assert inserted == 1
        assert skipped == 1

        stmt = select(func.count(KnowledgeBaseEntry.id)).where(
            KnowledgeBaseEntry.business_id == test_biz_id
        )
        count = (await session.execute(stmt)).scalar()
        assert count == 1


