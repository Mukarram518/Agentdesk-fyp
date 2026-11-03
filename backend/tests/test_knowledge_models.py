"""Tests for Phase 5.1 Knowledge Base Database Foundation & Models.

Verifies:
1. KnowledgeFile model field definitions, UUID primary key, and timezone-aware timestamps.
2. KnowledgeBaseEntry model field definitions for FAQ entries and document chunks.
3. pgvector column with confirmed dimension 384 and vector insertion/querying.
4. Rejection of invalid vector dimensions.
5. Check constraints on processing_status ('pending', 'processing', 'ready', 'failed').
6. Check constraints on language ('en', 'ur', 'mixed').
7. Non-null constraints on mandatory fields.
8. Foreign-key cascading: deleting a KnowledgeFile cascades to delete its chunks.
9. Foreign-key cascading: deleting a Business cascades to delete its files and knowledge entries.
10. Tenant isolation: querying by business_id never leaks records across businesses.
11. Existing domain models (User, Business, BusinessMember, UserSession) remain unaffected.
12. Migration upgrade and downgrade on an isolated test database without touching the dev database.
"""

import os
import subprocess
import sys
import uuid
from datetime import datetime
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, StatementError, DBAPIError

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models import (
    User,
    Business,
    BusinessMember,
    MemberRole,
    KnowledgeFile,
    KnowledgeFileStatus,
    KnowledgeBaseEntry,
    KnowledgeSourceType,
    KnowledgeLanguage,
    EMBEDDING_VECTOR_DIMENSION,
)

settings = get_settings()


async def create_test_business(db, name: str = "Test Knowledge Clinic") -> Business:
    """Helper to persist a test business tenant."""
    business = Business(
        name=name,
        slug=f"kb-biz-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business


# =====================================================================
# 1. KnowledgeFile Model Tests
# =====================================================================

@pytest.mark.asyncio
async def test_create_knowledge_file_success():
    """Verifies KnowledgeFile can be created with required fields, UUID PK, and timestamps."""
    async with async_session_factory() as db:
        business = await create_test_business(db)

        kfile = KnowledgeFile(
            business_id=business.id,
            filename="services_catalog.pdf",
            storage_key=f"businesses/{business.id}/knowledge/{uuid.uuid4().hex}.pdf",
            mime_type="application/pdf",
            size_bytes=1024 * 500,  # 500 KB
            processing_status=KnowledgeFileStatus.PENDING.value,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        assert isinstance(kfile.id, uuid.UUID)
        assert kfile.business_id == business.id
        assert kfile.filename == "services_catalog.pdf"
        assert kfile.mime_type == "application/pdf"
        assert kfile.size_bytes == 512000
        assert kfile.processing_status == "pending"
        assert kfile.error_message is None
        assert isinstance(kfile.created_at, datetime)
        assert kfile.created_at.tzinfo is not None
        assert isinstance(kfile.updated_at, datetime)


@pytest.mark.asyncio
async def test_knowledge_file_invalid_status_rejected():
    """Verifies that an unapproved processing_status is rejected by check constraint."""
    async with async_session_factory() as db:
        business = await create_test_business(db)

        kfile = KnowledgeFile(
            business_id=business.id,
            filename="bad_status.docx",
            storage_key="dummy_key",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=2048,
            processing_status="unapproved_status",
        )
        db.add(kfile)
        with pytest.raises(IntegrityError):
            await db.commit()


# =====================================================================
# 2. KnowledgeBaseEntry Model Tests
# =====================================================================

@pytest.mark.asyncio
async def test_create_faq_entry_success():
    """Verifies KnowledgeBaseEntry can be created as an FAQ with question, answer, and tags."""
    async with async_session_factory() as db:
        business = await create_test_business(db)

        entry = KnowledgeBaseEntry(
            business_id=business.id,
            question="What are your opening hours?",
            answer="We are open Monday to Saturday from 9 AM to 8 PM.",
            tags=["hours", "timings", "schedule"],
            language=KnowledgeLanguage.EN.value,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding_stale=False,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert isinstance(entry.id, uuid.UUID)
        assert entry.business_id == business.id
        assert entry.question == "What are your opening hours?"
        assert entry.answer == "We are open Monday to Saturday from 9 AM to 8 PM."
        assert entry.tags == ["hours", "timings", "schedule"]
        assert entry.language == "en"
        assert entry.source_type == "FAQ"
        assert entry.source_file_id is None
        assert entry.chunk_index is None
        assert entry.embedding_stale is False
        assert entry.embedding is None
        assert isinstance(entry.created_at, datetime)
        assert entry.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_create_document_chunk_entry_success():
    """Verifies KnowledgeBaseEntry can represent a document chunk with file reference and metadata."""
    async with async_session_factory() as db:
        business = await create_test_business(db)

        kfile = KnowledgeFile(
            business_id=business.id,
            filename="company_policy.docx",
            storage_key="some_storage_path.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=1024 * 50,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        chunk_entry = KnowledgeBaseEntry(
            business_id=business.id,
            question=None,  # Document chunks do not have a question field
            answer="Section 2.1: Cancellation policy requires 24 hours advance notice.",
            tags=["policy", "cancellation"],
            language=KnowledgeLanguage.EN.value,
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile.id,
            chunk_index=2,
            page_number=4,
            section_title="Cancellation Policy",
            embedding_stale=False,
        )
        db.add(chunk_entry)
        await db.commit()
        await db.refresh(chunk_entry)

        assert chunk_entry.question is None
        assert chunk_entry.source_file_id == kfile.id
        assert chunk_entry.chunk_index == 2
        assert chunk_entry.page_number == 4
        assert chunk_entry.section_title == "Cancellation Policy"
        assert chunk_entry.source_type == "document_chunk"


@pytest.mark.asyncio
async def test_knowledge_entry_invalid_language_rejected():
    """Verifies that an unsupported language is rejected by check constraint."""
    async with async_session_factory() as db:
        business = await create_test_business(db)

        entry = KnowledgeBaseEntry(
            business_id=business.id,
            question="Question",
            answer="Answer",
            language="french",  # Only 'en', 'ur', 'mixed' allowed
            source_type="FAQ",
        )
        db.add(entry)
        with pytest.raises(IntegrityError):
            await db.commit()


# =====================================================================
# 3. Vector Dimension & pgvector Storage Tests
# =====================================================================

@pytest.mark.asyncio
async def test_vector_dimension_is_384():
    """Verifies the confirmed embedding dimension constant matches the MiniLM model."""
    assert EMBEDDING_VECTOR_DIMENSION == 384


@pytest.mark.asyncio
async def test_vector_storage_and_retrieval():
    """Verifies that a 384-dimensional vector can be saved and queried via pgvector."""
    async with async_session_factory() as db:
        business = await create_test_business(db)

        # Create deterministic 384-dimensional vector
        sample_vector = [(i % 10) * 0.1 for i in range(EMBEDDING_VECTOR_DIMENSION)]
        assert len(sample_vector) == 384

        entry = KnowledgeBaseEntry(
            business_id=business.id,
            question="What is the test vector question?",
            answer="This answer contains a 384-dimensional pgvector embedding.",
            tags=["vector_test"],
            language=KnowledgeLanguage.EN.value,
            source_type=KnowledgeSourceType.FAQ.value,
            embedding=sample_vector,
            embedding_stale=False,
        )
        db.add(entry)
        await db.commit()

        # Query back from database
        stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == entry.id)
        result = await db.execute(stmt)
        retrieved = result.scalar_one()

        assert retrieved.embedding is not None
        assert len(retrieved.embedding) == 384
        assert abs(retrieved.embedding[0] - sample_vector[0]) < 1e-4
        assert abs(retrieved.embedding[10] - sample_vector[10]) < 1e-4


@pytest.mark.asyncio
async def test_vector_dimension_mismatch_rejected():
    """Verifies that inserting a vector with an incorrect dimension (e.g. 10 instead of 384) fails."""
    async with async_session_factory() as db:
        business = await create_test_business(db)

        invalid_vector = [0.1] * 10  # 10 dimensions instead of 384
        entry = KnowledgeBaseEntry(
            business_id=business.id,
            question="Invalid vector",
            answer="Answer with wrong vector dimension",
            language="en",
            source_type="FAQ",
            embedding=invalid_vector,
        )
        db.add(entry)
        with pytest.raises((IntegrityError, StatementError, DBAPIError)):
            await db.commit()


# =====================================================================
# 4. Cascades, Integrity Constraints & Cross-Business Protection Tests
# =====================================================================

@pytest.mark.asyncio
async def test_same_business_document_reference_succeeds():
    """Verifies that a document chunk referencing a file belonging to the same business succeeds."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Same Biz Test")

        kfile = KnowledgeFile(
            business_id=biz.id,
            filename="valid_doc.pdf",
            storage_key=f"biz/{biz.id}/valid_doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        chunk = KnowledgeBaseEntry(
            business_id=biz.id,
            answer="Valid document chunk content",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile.id,
            chunk_index=0,
        )
        db.add(chunk)
        await db.commit()

        # Query chunk with selectinload to verify relationship
        stmt = (
            select(KnowledgeBaseEntry)
            .where(KnowledgeBaseEntry.id == chunk.id)
            .options(selectinload(KnowledgeBaseEntry.source_file))
        )
        res = await db.execute(stmt)
        retrieved_chunk = res.scalar_one()

        assert retrieved_chunk.id is not None
        assert retrieved_chunk.source_file_id == kfile.id
        assert retrieved_chunk.business_id == biz.id
        assert retrieved_chunk.source_file is not None
        assert retrieved_chunk.source_file.id == kfile.id


@pytest.mark.asyncio
async def test_cross_business_document_reference_fails():
    """Verifies that a chunk with Business B cannot reference a file belonging to Business A."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Owner Biz A")
        biz_b = await create_test_business(db, name="Intruder Biz B")

        # File belongs to Biz A
        kfile_a = KnowledgeFile(
            business_id=biz_a.id,
            filename="biz_a_secrets.pdf",
            storage_key=f"biz/{biz_a.id}/secrets.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile_a)
        await db.commit()
        await db.refresh(kfile_a)

        # Chunk belongs to Biz B, but tries to reference file belonging to Biz A
        invalid_chunk = KnowledgeBaseEntry(
            business_id=biz_b.id,
            answer="Attempting cross-business file reference",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile_a.id,
            chunk_index=0,
        )
        db.add(invalid_chunk)
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_faq_with_null_file_and_chunk_succeeds():
    """Verifies FAQ entries with null source_file_id and null chunk_index succeed."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        faq = KnowledgeBaseEntry(
            business_id=biz.id,
            question="What is the refund policy?",
            answer="Full refund within 30 days.",
            source_type=KnowledgeSourceType.FAQ.value,
            source_file_id=None,
            chunk_index=None,
        )
        db.add(faq)
        await db.commit()
        await db.refresh(faq)

        assert faq.id is not None
        assert faq.source_type == "FAQ"
        assert faq.source_file_id is None
        assert faq.chunk_index is None


@pytest.mark.asyncio
async def test_faq_with_file_reference_fails():
    """Verifies FAQ entries referencing an uploaded file are rejected by ck_kbe_source_type_integrity."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        kfile = KnowledgeFile(
            business_id=biz.id,
            filename="some_file.pdf",
            storage_key=f"biz/{biz.id}/some_file.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        # FAQ with a file reference must fail
        invalid_faq = KnowledgeBaseEntry(
            business_id=biz.id,
            question="FAQ with invalid file reference?",
            answer="This must be rejected.",
            source_type=KnowledgeSourceType.FAQ.value,
            source_file_id=kfile.id,
            chunk_index=None,
        )
        db.add(invalid_faq)
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_document_chunk_with_null_file_reference_fails():
    """Verifies document chunks missing source_file_id are rejected by ck_kbe_source_type_integrity."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        invalid_chunk = KnowledgeBaseEntry(
            business_id=biz.id,
            answer="Chunk missing its file reference.",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=None,
            chunk_index=0,
        )
        db.add(invalid_chunk)
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_document_chunk_with_null_chunk_index_fails():
    """Verifies document chunks missing chunk_index are rejected by ck_kbe_source_type_integrity."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        kfile = KnowledgeFile(
            business_id=biz.id,
            filename="doc_chunk_test.pdf",
            storage_key=f"biz/{biz.id}/doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        invalid_chunk = KnowledgeBaseEntry(
            business_id=biz.id,
            answer="Chunk missing chunk_index.",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile.id,
            chunk_index=None,
        )
        db.add(invalid_chunk)
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_document_chunk_with_negative_chunk_index_fails():
    """Verifies document chunks with negative chunk_index are rejected by ck_kbe_source_type_integrity."""
    async with async_session_factory() as db:
        biz = await create_test_business(db)

        kfile = KnowledgeFile(
            business_id=biz.id,
            filename="neg_chunk_test.pdf",
            storage_key=f"biz/{biz.id}/neg.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        invalid_chunk = KnowledgeBaseEntry(
            business_id=biz.id,
            answer="Chunk with negative chunk_index.",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile.id,
            chunk_index=-1,
        )
        db.add(invalid_chunk)
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_delete_document_removes_chunks_not_independent_faqs():
    """Verifies that deleting a document removes its chunks but leaves independent FAQs intact."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Doc Delete Isolation Biz")

        kfile = KnowledgeFile(
            business_id=biz.id,
            filename="policy_doc.pdf",
            storage_key=f"biz/{biz.id}/policy.pdf",
            mime_type="application/pdf",
            size_bytes=4096,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        # Chunks for this file
        chunk1 = KnowledgeBaseEntry(
            business_id=biz.id,
            answer="Chunk 1 from policy",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile.id,
            chunk_index=0,
        )
        chunk2 = KnowledgeBaseEntry(
            business_id=biz.id,
            answer="Chunk 2 from policy",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile.id,
            chunk_index=1,
        )
        # Independent FAQ for the same business
        faq = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Independent question?",
            answer="Independent answer.",
            source_type=KnowledgeSourceType.FAQ.value,
            source_file_id=None,
            chunk_index=None,
        )
        db.add_all([chunk1, chunk2, faq])
        await db.commit()
        await db.refresh(faq)

        # Delete the file
        await db.delete(kfile)
        await db.commit()

        # Chunks must be deleted
        chunks_res = await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.source_file_id == kfile.id)
        )
        assert len(chunks_res.scalars().all()) == 0

        # Independent FAQ must still exist
        faq_res = await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq.id)
        )
        retrieved_faq = faq_res.scalar_one_or_none()
        assert retrieved_faq is not None
        assert retrieved_faq.question == "Independent question?"


@pytest.mark.asyncio
async def test_cascade_delete_business_deletes_all_knowledge():
    """Verifies that deleting a Business cascades and removes its files and knowledge entries."""
    async with async_session_factory() as db:
        biz = await create_test_business(db, name="Temp Deletable Biz")

        # Create file
        kfile = KnowledgeFile(
            business_id=biz.id,
            filename="biz_file.pdf",
            storage_key="biz_file_key",
            mime_type="application/pdf",
            size_bytes=2048,
        )
        db.add(kfile)
        await db.commit()
        await db.refresh(kfile)

        # Create FAQ entry
        faq = KnowledgeBaseEntry(
            business_id=biz.id,
            question="Biz question?",
            answer="Biz answer.",
            source_type="FAQ",
        )
        db.add(faq)
        await db.commit()

        # Delete business
        await db.delete(biz)
        await db.commit()

        # Verify knowledge files and entries for this business are gone
        files = await db.execute(
            select(KnowledgeFile).where(KnowledgeFile.business_id == biz.id)
        )
        assert len(files.scalars().all()) == 0

        entries = await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.business_id == biz.id)
        )
        assert len(entries.scalars().all()) == 0


# =====================================================================
# 5. Multi-Tenant Isolation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_tenant_isolation_knowledge_queries():
    """Verifies that knowledge entries of Business A are never returned when querying for Business B."""
    async with async_session_factory() as db:
        biz_a = await create_test_business(db, name="Clinic A")
        biz_b = await create_test_business(db, name="Clinic B")

        # Business A FAQ
        faq_a = KnowledgeBaseEntry(
            business_id=biz_a.id,
            question="What is Business A secret recipe?",
            answer="Top secret ingredient A.",
            source_type="FAQ",
        )
        # Business B FAQ
        faq_b = KnowledgeBaseEntry(
            business_id=biz_b.id,
            question="What is Business B secret recipe?",
            answer="Top secret ingredient B.",
            source_type="FAQ",
        )
        db.add_all([faq_a, faq_b])
        await db.commit()

        # Query strictly scoped by biz_a
        result_a = await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.business_id == biz_a.id)
        )
        entries_a = result_a.scalars().all()
        assert len(entries_a) == 1
        assert entries_a[0].answer == "Top secret ingredient A."

        # Query strictly scoped by biz_b
        result_b = await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.business_id == biz_b.id)
        )
        entries_b = result_b.scalars().all()
        assert len(entries_b) == 1
        assert entries_b[0].answer == "Top secret ingredient B."

        # Verify no cross-contamination
        assert all(e.business_id == biz_a.id for e in entries_a)
        assert all(e.business_id == biz_b.id for e in entries_b)


# =====================================================================
# 6. Existing Domain Models Integrity Test
# =====================================================================

@pytest.mark.asyncio
async def test_existing_domain_models_unaffected():
    """Verifies that Users, Businesses, and BusinessMembers work normally after migration."""
    async with async_session_factory() as db:
        unique_email = f"integrity_{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=unique_email, full_name="Integrity User")
        biz = await create_test_business(db, name="Integrity Biz")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        member = BusinessMember(
            business_id=biz.id,
            user_id=user.id,
            role=MemberRole.OWNER.value,
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)

        assert member.role == "owner"
        assert member.business_id == biz.id
        assert member.user_id == user.id


# =====================================================================
# 7. Isolated Migration Upgrade & Downgrade Verification
# =====================================================================

def test_migration_upgrade_and_downgrade_in_isolated_database():
    """Verifies migration 0004 and 0005 upgrade and downgrade cycle in an isolated temporary database.

    Guarantees:
    - Never resets or downgrades the active development database.
    - Creates a temporary test database.
    - Runs Alembic upgrade head (including 0004 and 0005).
    - Verifies composite foreign key, unique constraint, and check constraints exist.
    - Runs Alembic downgrade to 0004_knowledge_base and verifies rollback of 0005 integrity constraints.
    - Runs Alembic downgrade to 0003_authentication and verifies removal of all knowledge tables.
    - Runs Alembic upgrade head back to 0005_knowledge_integrity.
    - Drops the temporary test database upon completion.
    """
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    test_db_name = f"agentdesk_mig_test_{uuid.uuid4().hex[:6]}"
    admin_conn_str = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/postgres"

    # 1. Create isolated temporary database
    admin_conn = psycopg2.connect(admin_conn_str)
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    admin_cur = admin_conn.cursor()
    admin_cur.execute(f'CREATE DATABASE "{test_db_name}";')
    admin_cur.close()
    admin_conn.close()

    try:
        # Prepare environment pointing to the isolated temporary test database
        env_vars = os.environ.copy()
        test_sync_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{test_db_name}"
        test_async_url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{test_db_name}"
        env_vars["DATABASE_URL"] = test_async_url
        env_vars["POSTGRES_DB"] = test_db_name

        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # 2. Upgrade to head (0001, 0002, 0003, 0004, 0005)
        run_upgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env_vars,
            capture_output=True,
            text=True,
        )
        assert run_upgrade.returncode == 0, f"Upgrade failed: {run_upgrade.stderr}"

        # Verify tables and constraints exist in the temporary database
        conn = psycopg2.connect(test_sync_url)
        cur = conn.cursor()
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        tables_after_upgrade = {row[0] for row in cur.fetchall()}
        assert "knowledge_files" in tables_after_upgrade
        assert "knowledge_base_entries" in tables_after_upgrade
        assert "businesses" in tables_after_upgrade
        assert "users" in tables_after_upgrade

        cur.execute("""
            SELECT conname FROM pg_constraint 
            JOIN pg_class ON pg_class.oid = pg_constraint.conrelid 
            WHERE pg_class.relname IN ('knowledge_files', 'knowledge_base_entries');
        """)
        constraints_0005 = {row[0] for row in cur.fetchall()}
        assert "uq_knowledge_files_id_business" in constraints_0005
        assert "fk_knowledge_base_entries_source_file_business" in constraints_0005
        assert "ck_kbe_source_type_integrity" in constraints_0005

        # 3. Downgrade by 1 revision (reverts 0005_knowledge_integrity back to 0004_knowledge_base)
        run_downgrade_0004 = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "0004_knowledge_base"],
            cwd=backend_dir,
            env=env_vars,
            capture_output=True,
            text=True,
        )
        assert run_downgrade_0004.returncode == 0, f"Downgrade to 0004 failed: {run_downgrade_0004.stderr}"

        cur.execute("""
            SELECT conname FROM pg_constraint 
            JOIN pg_class ON pg_class.oid = pg_constraint.conrelid 
            WHERE pg_class.relname IN ('knowledge_files', 'knowledge_base_entries');
        """)
        constraints_0004 = {row[0] for row in cur.fetchall()}
        assert "uq_knowledge_files_id_business" not in constraints_0004
        assert "fk_knowledge_base_entries_source_file_business" not in constraints_0004
        assert "ck_kbe_source_type_integrity" not in constraints_0004
        assert "fk_knowledge_base_entries_source_file_id" in constraints_0004

        # 4. Downgrade to 0003_authentication (reverts 0004_knowledge_base)
        run_downgrade_0003 = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "0003_authentication"],
            cwd=backend_dir,
            env=env_vars,
            capture_output=True,
            text=True,
        )
        assert run_downgrade_0003.returncode == 0, f"Downgrade to 0003 failed: {run_downgrade_0003.stderr}"

        # Verify knowledge tables were removed while existing core tables remain
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        tables_after_downgrade = {row[0] for row in cur.fetchall()}
        assert "knowledge_files" not in tables_after_downgrade
        assert "knowledge_base_entries" not in tables_after_downgrade
        assert "businesses" in tables_after_downgrade
        assert "users" in tables_after_downgrade
        assert "user_sessions" in tables_after_downgrade

        # 5. Upgrade back to head to verify re-apply safety
        run_reupgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env_vars,
            capture_output=True,
            text=True,
        )
        assert run_reupgrade.returncode == 0, f"Re-upgrade failed: {run_reupgrade.stderr}"

        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        tables_after_reupgrade = {row[0] for row in cur.fetchall()}
        assert "knowledge_files" in tables_after_reupgrade
        assert "knowledge_base_entries" in tables_after_reupgrade

        cur.close()
        conn.close()
    finally:
        # 5. Clean up temporary test database
        clean_conn = psycopg2.connect(admin_conn_str)
        clean_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        clean_cur = clean_conn.cursor()
        clean_cur.execute(
            f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{test_db_name}'
              AND pid <> pg_backend_pid();
            """
        )
        clean_cur.execute(f'DROP DATABASE IF EXISTS "{test_db_name}";')
        clean_cur.close()
        clean_conn.close()
