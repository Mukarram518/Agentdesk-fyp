"""API Integration tests for AgentDesk Knowledge File Endpoints (Phase 5A).

Tests all 27 required scenarios:
1. Valid PDF upload (202 Accepted, pending status, safe metadata).
2. Valid DOCX upload (202 Accepted, pending status, safe metadata).
3. Empty file rejection (422 Unprocessable Entity).
4. Oversized file rejection (> 5 MB streaming check, 422 Unprocessable Entity).
5. Unsupported extension rejection (.sh, .exe, .txt, 422).
6. Invalid MIME type rejection (mismatched MIME vs extension, 422).
7. Mismatched file signature rejection (disguised text/html file, 422).
8. Successful file listing (200 OK, paginated list scoped to business).
9. Pagination (limit, offset parameters honored, total count returned).
10. Successful file status retrieval (200 OK, safe metadata).
11. Missing file returns 404.
12. Foreign-tenant file status and delete return 404 (zero information leakage).
13. Unauthenticated requests return 401 across all file endpoints.
14. Non-owner upload/deletion returns 403 (member can list/get, cannot upload/delete).
15. Successful file deletion (204 No Content, empty body).
16. Associated document chunk cascade deletion (chunks deleted, FAQs preserved).
17. Physical storage deletion on file delete.
18. ARQ enqueueing (verifies process_knowledge_file job dispatched).
19. ARQ enqueue failure handling (marks failed, returns 202).
20. Storage failure handling on upload and deletion (returns 500, no corrupted state).
21. Existing FAQ CRUD regression test (verifies FAQ endpoints intact).
22. Existing semantic search regression and chunk metadata support.
23. Commit-before-enqueue verification: record visible to independent worker session.
24. Immediate worker claim verification: worker can claim enqueued file.
25. Database commit failure: never dispatches job and cleans up storage.
26. Enqueue failure after commit: updates record to failed and durably persists.
27. Worker not found and deletion behavior preserved.
"""

import io
import uuid
import zipfile
from typing import Tuple
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.knowledge import KnowledgeBaseEntry, KnowledgeSourceType, KnowledgeLanguage
from app.models.knowledge_file import KnowledgeFile, KnowledgeFileStatus
from app.providers.storage import get_storage_provider

settings = get_settings()

VALID_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n120\n%%EOF"
)


def make_valid_docx_bytes() -> bytes:
    """Constructs minimal valid DOCX OpenXML archive bytes."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<?xml version='1.0'?><Types></Types>")
        zf.writestr(
            "word/document.xml",
            "<?xml version='1.0'?><w:document><w:body><w:p><w:r><w:t>AgentDesk Test Content</w:t></w:r></w:p></w:body></w:document>",
        )
    return bio.getvalue()


async def create_authenticated_user(
    async_client: AsyncClient, name: str = "Test User"
) -> Tuple[dict, str]:
    """Registers, logs in, and returns (user_data, session_token)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"

    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": name},
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()["user"]

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    session_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    async_client.cookies.clear()

    return user_data, session_token


async def create_owner_with_business(
    async_client: AsyncClient, biz_name: str = "File Test Biz"
) -> Tuple[dict, str, dict]:
    """Creates an authenticated user and onboards a new business as owner."""
    user, token = await create_authenticated_user(async_client, name="Owner User")
    biz_res = await async_client.post(
        "/api/v1/businesses",
        json={"name": f"{biz_name} {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert biz_res.status_code == 201
    business_data = biz_res.json()
    return user, token, business_data


async def add_member_to_business(
    business_id: uuid.UUID, user_id: uuid.UUID, role: str = MemberRole.MEMBER.value
) -> None:
    """Directly adds a user as a member to an existing business in the database."""
    async with async_session_factory() as db:
        member = BusinessMember(
            business_id=business_id,
            user_id=user_id,
            role=role,
        )
        db.add(member)
        await db.commit()


# ============================================================================
# 1. Valid PDF Upload (202 Accepted)
# ============================================================================

@pytest.mark.asyncio
async def test_upload_pdf_success(async_client: AsyncClient):
    """Verifies successful upload of a valid PDF document with safe metadata response."""
    _, token, biz = await create_owner_with_business(async_client)

    files = {"file": ("manual.pdf", VALID_PDF_BYTES, "application/pdf")}
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 202
    data = res.json()

    assert "id" in data
    assert data["business_id"] == biz["id"]
    assert data["filename"] == "manual.pdf"
    assert data["size_bytes"] == len(VALID_PDF_BYTES)
    assert data["mime_type"] == "application/pdf"
    assert data["processing_status"] in ("pending", "failed")
    assert "created_at" in data

    # Verify no private storage keys or lease tokens exposed
    assert "storage_key" not in data
    assert "processing_token" not in data
    assert "embedding" not in data


# ============================================================================
# 2. Valid DOCX Upload (202 Accepted)
# ============================================================================

@pytest.mark.asyncio
async def test_upload_docx_success(async_client: AsyncClient):
    """Verifies successful upload of a valid DOCX document."""
    _, token, biz = await create_owner_with_business(async_client)
    docx_bytes = make_valid_docx_bytes()

    files = {
        "file": (
            "handbook.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 202
    data = res.json()

    assert data["filename"] == "handbook.docx"
    assert data["mime_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert data["size_bytes"] == len(docx_bytes)


# ============================================================================
# 3. Empty File Rejection (422)
# ============================================================================

@pytest.mark.asyncio
async def test_upload_empty_file_rejected(async_client: AsyncClient):
    """Verifies that an empty (0-byte) file is rejected with HTTP 422."""
    _, token, _ = await create_owner_with_business(async_client)

    files = {"file": ("empty.pdf", b"", "application/pdf")}
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "empty" in res.json()["detail"].lower()


# ============================================================================
# 4. Oversized File Rejection (> 5 MB streaming check, 422)
# ============================================================================

@pytest.mark.asyncio
async def test_upload_oversized_file_rejected(async_client: AsyncClient):
    """Verifies that an oversized file (> 5 MB) is aborted and rejected with HTTP 422."""
    _, token, _ = await create_owner_with_business(async_client)

    oversized_bytes = b"%PDF-" + b"0" * (5 * 1024 * 1024 + 1024)
    files = {"file": ("huge.pdf", oversized_bytes, "application/pdf")}
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "5 mb" in res.json()["detail"].lower()


# ============================================================================
# 5. Unsupported Extension Rejection (422)
# ============================================================================

@pytest.mark.asyncio
async def test_upload_unsupported_extension_rejected(async_client: AsyncClient):
    """Verifies that unsupported file extensions are rejected with HTTP 422."""
    _, token, _ = await create_owner_with_business(async_client)

    files = {"file": ("malicious.exe", b"MZ\x90\x00", "application/x-msdownload")}
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "unsupported file extension" in res.json()["detail"].lower()


# ============================================================================
# 6. Invalid MIME Type Rejection (422)
# ============================================================================

@pytest.mark.asyncio
async def test_upload_invalid_mime_type_rejected(async_client: AsyncClient):
    """Verifies that extension-to-MIME mismatch is rejected with HTTP 422."""
    _, token, _ = await create_owner_with_business(async_client)

    files = {"file": ("report.pdf", VALID_PDF_BYTES, "image/png")}
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "mime type mismatch" in res.json()["detail"].lower()


# ============================================================================
# 7. Mismatched File Signature Rejection (422)
# ============================================================================

@pytest.mark.asyncio
async def test_upload_mismatched_signature_rejected(async_client: AsyncClient):
    """Verifies that a file with mismatched magic bytes is rejected with HTTP 422."""
    _, token, _ = await create_owner_with_business(async_client)

    fake_pdf = b"<html><body>Not a PDF</body></html>"
    files = {"file": ("fake.pdf", fake_pdf, "application/pdf")}
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "signature" in res.json()["detail"].lower() or "pdf" in res.json()["detail"].lower()


# ============================================================================
# 8. Successful File Listing (200 OK)
# ============================================================================

@pytest.mark.asyncio
async def test_list_files_success(async_client: AsyncClient):
    """Verifies listing uploaded files for the authenticated business."""
    _, token, biz = await create_owner_with_business(async_client)

    # Upload two files
    for name in ("doc1.pdf", "doc2.pdf"):
        files = {"file": (name, VALID_PDF_BYTES, "application/pdf")}
        up_res = await async_client.post(
            "/api/v1/knowledge/files",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert up_res.status_code == 202

    res = await async_client.get(
        "/api/v1/knowledge/files",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2
    filenames = [f["filename"] for f in data["items"]]
    assert "doc1.pdf" in filenames
    assert "doc2.pdf" in filenames


# ============================================================================
# 9. Pagination Parameters (200 OK)
# ============================================================================

@pytest.mark.asyncio
async def test_list_files_pagination(async_client: AsyncClient):
    """Verifies that limit and offset parameters are properly applied."""
    _, token, biz = await create_owner_with_business(async_client)

    for i in range(3):
        files = {"file": (f"page_doc_{i}.pdf", VALID_PDF_BYTES, "application/pdf")}
        await async_client.post(
            "/api/v1/knowledge/files",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    # Limit 2, Offset 0
    res1 = await async_client.get(
        "/api/v1/knowledge/files?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 3
    assert len(data1["items"]) == 2
    assert data1["limit"] == 2
    assert data1["offset"] == 0

    # Limit 2, Offset 2
    res2 = await async_client.get(
        "/api/v1/knowledge/files?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 1
    assert data2["offset"] == 2


# ============================================================================
# 10. Successful File Status Retrieval (200 OK)
# ============================================================================

@pytest.mark.asyncio
async def test_get_file_status_success(async_client: AsyncClient):
    """Verifies retrieving status and metadata of an existing file."""
    _, token, biz = await create_owner_with_business(async_client)

    files = {"file": ("status_check.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    file_id = up_res.json()["id"]

    res = await async_client.get(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == file_id
    assert data["filename"] == "status_check.pdf"
    assert "processing_status" in data


# ============================================================================
# 11. Missing File Returns 404
# ============================================================================

@pytest.mark.asyncio
async def test_get_missing_file_returns_404(async_client: AsyncClient):
    """Verifies that requesting a nonexistent file ID returns HTTP 404."""
    _, token, _ = await create_owner_with_business(async_client)
    random_id = uuid.uuid4()

    res = await async_client.get(
        f"/api/v1/knowledge/files/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# ============================================================================
# 12. Cross-Tenant Isolation (404 on GET and DELETE)
# ============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_file_isolation(async_client: AsyncClient):
    """Verifies that a tenant cannot access or delete files belonging to another tenant."""
    # Tenant A
    _, token_a, biz_a = await create_owner_with_business(async_client, biz_name="Tenant A")
    files = {"file": ("tenant_a.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    file_id_a = up_res.json()["id"]

    # Tenant B
    _, token_b, biz_b = await create_owner_with_business(async_client, biz_name="Tenant B")

    # Tenant B tries to get Tenant A's file
    get_res = await async_client.get(
        f"/api/v1/knowledge/files/{file_id_a}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_res.status_code == 404

    # Tenant B tries to delete Tenant A's file
    del_res = await async_client.delete(
        f"/api/v1/knowledge/files/{file_id_a}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_res.status_code == 404


# ============================================================================
# 13. Unauthenticated Requests Return 401
# ============================================================================

@pytest.mark.asyncio
async def test_unauthenticated_requests_return_401(async_client: AsyncClient):
    """Verifies that unauthenticated requests to all file endpoints return HTTP 401."""
    random_id = uuid.uuid4()

    # Upload
    res_upload = await async_client.post("/api/v1/knowledge/files")
    assert res_upload.status_code == 401

    # List
    res_list = await async_client.get("/api/v1/knowledge/files")
    assert res_list.status_code == 401

    # Get
    res_get = await async_client.get(f"/api/v1/knowledge/files/{random_id}")
    assert res_get.status_code == 401

    # Delete
    res_del = await async_client.delete(f"/api/v1/knowledge/files/{random_id}")
    assert res_del.status_code == 401


# ============================================================================
# 14. Non-Owner Permissions (403 for upload/delete, 200 for list/get)
# ============================================================================

@pytest.mark.asyncio
async def test_non_owner_permissions(async_client: AsyncClient):
    """Verifies that non-owner members can read files but cannot upload or delete."""
    # Create owner and business
    _, owner_token, biz = await create_owner_with_business(async_client)

    # Owner uploads a file
    files = {"file": ("shared.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    file_id = up_res.json()["id"]

    # Create regular member in same business
    member_user, member_token = await create_authenticated_user(async_client, name="Member User")
    await add_member_to_business(
        business_id=uuid.UUID(biz["id"]),
        user_id=uuid.UUID(member_user["id"]),
        role=MemberRole.MEMBER.value,
    )

    # Member tries to upload -> 403
    files_member = {"file": ("unauthorized.pdf", VALID_PDF_BYTES, "application/pdf")}
    res_up = await async_client.post(
        "/api/v1/knowledge/files",
        files=files_member,
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res_up.status_code == 403

    # Member tries to delete -> 403
    res_del = await async_client.delete(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res_del.status_code == 403

    # Member tries to list -> 200
    res_list = await async_client.get(
        "/api/v1/knowledge/files",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res_list.status_code == 200
    assert len(res_list.json()["items"]) == 1

    # Member tries to get single file -> 200
    res_get = await async_client.get(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res_get.status_code == 200


# ============================================================================
# 15. Successful File Deletion (204 No Content)
# ============================================================================

@pytest.mark.asyncio
async def test_delete_file_success(async_client: AsyncClient):
    """Verifies that an owner can delete a file, returning 204 No Content."""
    _, token, biz = await create_owner_with_business(async_client)

    files = {"file": ("to_delete.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    file_id = up_res.json()["id"]

    del_res = await async_client.delete(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204
    assert len(del_res.content) == 0

    # Confirm it is no longer found
    get_res = await async_client.get(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 404


# ============================================================================
# 16. Cascade Deletion of Document Chunks
# ============================================================================

@pytest.mark.asyncio
async def test_delete_file_cascades_chunks(async_client: AsyncClient):
    """Verifies that deleting a file cascades to its document chunks without touching FAQs."""
    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    # 1. Upload file
    files = {"file": ("chunk_test.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    file_id = uuid.UUID(up_res.json()["id"])

    # 2. Insert a document chunk and an FAQ in the database
    async with async_session_factory() as db:
        chunk_entry = KnowledgeBaseEntry(
            business_id=biz_id,
            answer="This is chunk text from document.",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=file_id,
            chunk_index=0,
            page_number=1,
            section_title="Intro",
            language=KnowledgeLanguage.EN.value,
        )
        faq_entry = KnowledgeBaseEntry(
            business_id=biz_id,
            question="What is this?",
            answer="This is a persistent FAQ.",
            source_type=KnowledgeSourceType.FAQ.value,
            language=KnowledgeLanguage.EN.value,
        )
        db.add(chunk_entry)
        db.add(faq_entry)
        await db.commit()
        chunk_id = chunk_entry.id
        faq_id = faq_entry.id

    # 3. Delete file
    del_res = await async_client.delete(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # 4. Verify chunk was cascade-deleted, but FAQ remains
    async with async_session_factory() as db:
        chunk_in_db = (
            await db.execute(select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == chunk_id))
        ).scalar_one_or_none()
        assert chunk_in_db is None

        faq_in_db = (
            await db.execute(select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.id == faq_id))
        ).scalar_one_or_none()
        assert faq_in_db is not None


# ============================================================================
# 17. Physical Storage Deletion
# ============================================================================

@pytest.mark.asyncio
async def test_delete_file_removes_physical_storage(async_client: AsyncClient):
    """Verifies that physical file in storage provider is removed upon file deletion."""
    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    files = {"file": ("physical_test.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    file_id = uuid.UUID(up_res.json()["id"])

    # Locate storage_key from DB
    async with async_session_factory() as db:
        kfile = (
            await db.execute(select(KnowledgeFile).where(KnowledgeFile.id == file_id))
        ).scalar_one()
        storage_key = kfile.storage_key

    storage = get_storage_provider()
    assert await storage.exists(storage_key) is True

    # Delete via API
    del_res = await async_client.delete(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # Verify physical file deleted
    assert await storage.exists(storage_key) is False


# ============================================================================
# 18. ARQ Enqueueing on Upload
# ============================================================================

@pytest.mark.asyncio
async def test_arq_enqueue_on_upload(async_client: AsyncClient):
    """Verifies that an ARQ job is dispatched when an ARQ pool is available."""
    _, token, _ = await create_owner_with_business(async_client)

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=None)

    from app.main import app
    app.state.arq_pool = mock_pool

    try:
        files = {"file": ("arq_test.pdf", VALID_PDF_BYTES, "application/pdf")}
        res = await async_client.post(
            "/api/v1/knowledge/files",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 202
        file_id = res.json()["id"]

        mock_pool.enqueue_job.assert_called_once_with("process_knowledge_file", str(file_id))
        assert res.json()["processing_status"] == "pending"
    finally:
        app.state.arq_pool = None


# ============================================================================
# 19. ARQ Enqueue Failure Handling
# ============================================================================

@pytest.mark.asyncio
async def test_arq_enqueue_failure_handling(async_client: AsyncClient):
    """Verifies that an ARQ enqueue failure marks the file as failed and records the error."""
    _, token, _ = await create_owner_with_business(async_client)

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=Exception("Redis connection refused"))

    from app.main import app
    app.state.arq_pool = mock_pool

    files = {"file": ("enqueue_fail.pdf", VALID_PDF_BYTES, "application/pdf")}
    res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 202
    data = res.json()
    assert data["processing_status"] == "failed"
    assert "Background processing queue unavailable" in data["error_message"]

    # Restore app state
    app.state.arq_pool = None


# ============================================================================
# 20. Storage Failure Handling (Upload & Delete)
# ============================================================================

@pytest.mark.asyncio
async def test_storage_failure_handling(async_client: AsyncClient):
    """Verifies that storage failures return HTTP 500 without leaving corrupted DB state."""
    _, token, biz = await create_owner_with_business(async_client)

    # 1. Upload storage failure
    with patch("app.providers.storage.local.LocalStorageProvider.upload", side_effect=IOError("Disk write error")):
        files = {"file": ("storage_fail.pdf", VALID_PDF_BYTES, "application/pdf")}
        res_up = await async_client.post(
            "/api/v1/knowledge/files",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_up.status_code == 500

    # 2. Delete storage failure
    # First upload successfully
    files = {"file": ("valid_for_del.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_ok = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert up_ok.status_code == 202
    file_id = up_ok.json()["id"]

    # Mock delete failure
    with patch("app.providers.storage.local.LocalStorageProvider.delete", side_effect=IOError("Disk delete error")):
        del_res = await async_client.delete(
            f"/api/v1/knowledge/files/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_res.status_code == 500


# ============================================================================
# 21. Existing FAQ CRUD Regression Test
# ============================================================================

@pytest.mark.asyncio
async def test_faq_crud_regression(async_client: AsyncClient):
    """Verifies that existing FAQ CRUD continues working seamlessly with files present."""
    _, token, _ = await create_owner_with_business(async_client)

    # Create FAQ
    create_res = await async_client.post(
        "/api/v1/knowledge",
        json={"question": "What is our policy?", "answer": "Return within 30 days."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 201
    faq_id = create_res.json()["id"]

    # List FAQs
    list_res = await async_client.get(
        "/api/v1/knowledge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # Delete FAQ
    del_res = await async_client.delete(
        f"/api/v1/knowledge/{faq_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204


# ============================================================================
# 22. Existing Semantic Search Regression & Chunk Metadata
# ============================================================================

@pytest.mark.asyncio
async def test_semantic_search_regression_and_chunk_metadata(async_client: AsyncClient):
    """Verifies semantic search returns both FAQ and document chunk entries with chunk metadata."""
    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    # Create one document chunk directly with valid unit embedding
    # Note: multilingual-e5 uses 384-dimensional unit vector
    embedding_vec = [1.0] + [0.0] * 383

    async with async_session_factory() as db:
        kfile = KnowledgeFile(
            business_id=biz_id,
            filename="hours.pdf",
            storage_key="test/hours.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            processing_status=KnowledgeFileStatus.READY.value,
        )
        db.add(kfile)
        await db.flush()

        chunk_entry = KnowledgeBaseEntry(
            business_id=biz_id,
            answer="This is a chunk about opening hours.",
            source_type=KnowledgeSourceType.DOCUMENT_CHUNK.value,
            source_file_id=kfile.id,
            chunk_index=3,
            page_number=5,
            section_title="Operating Hours",
            language=KnowledgeLanguage.EN.value,
            embedding=embedding_vec,
            embedding_stale=False,
            embedding_model="intfloat/multilingual-e5-small",
        )
        db.add(chunk_entry)
        await db.commit()
        kfile_id = kfile.id

    # Perform search
    search_res = await async_client.post(
        "/api/v1/knowledge/search",
        json={"query": "When are you open?", "top_k": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert search_res.status_code == 200
    data = search_res.json()
    assert "results" in data
    assert len(data["results"]) >= 1

    result_item = data["results"][0]
    assert result_item["source_type"] == "document_chunk"
    assert result_item["chunk_index"] == 3
    assert result_item["page_number"] == 5
    assert result_item["section_title"] == "Operating Hours"
    assert result_item["source_file_id"] == str(kfile_id)


# ============================================================================
# 23. Commit-Before-Enqueue Verification: Record Visible to Worker
# ============================================================================

@pytest.mark.asyncio
async def test_record_committed_and_visible_before_worker_receives_job(
    async_client: AsyncClient,
):
    """Verifies KnowledgeFile is durably committed and visible in an independent session
    before the ARQ worker receives the enqueued job invocation.
    """
    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    observed_in_independent_session = False
    enqueued_file_id = None

    async def mock_enqueue_job(task_name: str, file_id_str: str):
        nonlocal observed_in_independent_session, enqueued_file_id
        enqueued_file_id = uuid.UUID(file_id_str)
        # Query database through a completely separate session to verify cross-transaction visibility
        async with async_session_factory() as verify_db:
            stmt = select(KnowledgeFile).where(
                KnowledgeFile.id == enqueued_file_id,
                KnowledgeFile.business_id == biz_id,
            )
            res = await verify_db.execute(stmt)
            record = res.scalar_one_or_none()
            if record is not None and record.processing_status == KnowledgeFileStatus.PENDING.value:
                observed_in_independent_session = True

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=mock_enqueue_job)

    from app.main import app
    app.state.arq_pool = mock_pool

    try:
        files = {"file": ("visible_test.pdf", VALID_PDF_BYTES, "application/pdf")}
        res = await async_client.post(
            "/api/v1/knowledge/files",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 202
        data = res.json()
        assert data["processing_status"] == "pending"
        assert mock_pool.enqueue_job.call_count == 1
        assert observed_in_independent_session is True
        assert uuid.UUID(data["id"]) == enqueued_file_id
    finally:
        app.state.arq_pool = None


# ============================================================================
# 24. Immediate Worker Claim Verification: Worker Can Claim Enqueued File
# ============================================================================

@pytest.mark.asyncio
async def test_worker_can_immediately_claim_enqueued_file(
    async_client: AsyncClient,
):
    """Verifies that an ARQ worker executing immediately upon job receipt
    can successfully claim the KnowledgeFile and transition its status to 'processing'.
    """
    from app.services.document_processing_service import (
        DocumentProcessingService,
        ProcessingResultStatus,
    )

    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    claim_status = None
    claimed_file_id = None

    async def mock_enqueue_job(task_name: str, file_id_str: str):
        nonlocal claim_status, claimed_file_id
        target_uuid = uuid.UUID(file_id_str)
        # Simulate worker executing immediately on job arrival
        doc_service = DocumentProcessingService(session_factory=async_session_factory)
        status, claim_data = await doc_service._claim_file(target_uuid)
        claim_status = status
        if claim_data:
            claimed_file_id = claim_data.file_id

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=mock_enqueue_job)

    from app.main import app
    app.state.arq_pool = mock_pool

    try:
        files = {"file": ("claim_test.pdf", VALID_PDF_BYTES, "application/pdf")}
        res = await async_client.post(
            "/api/v1/knowledge/files",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 202
        data = res.json()
        file_id = uuid.UUID(data["id"])

        assert claim_status == ProcessingResultStatus.READY
        assert claimed_file_id == file_id

        # Verify the database state shows processing status claimed
        async with async_session_factory() as verify_db:
            stmt = select(KnowledgeFile).where(KnowledgeFile.id == file_id)
            kfile = (await verify_db.execute(stmt)).scalar_one()
            assert kfile.processing_status == KnowledgeFileStatus.PROCESSING.value
            assert kfile.processing_token is not None
    finally:
        app.state.arq_pool = None


# ============================================================================
# 25. Database Commit Failure: Never Dispatches Job and Cleans Up Storage
# ============================================================================

@pytest.mark.asyncio
async def test_database_commit_failure_does_not_dispatch_job(
    async_client: AsyncClient,
):
    """Verifies that if database commit fails:
    1. ARQ enqueue_job is never called.
    2. Any written physical storage file is deleted.
    3. HTTP 500 is returned.
    4. No orphan pending record remains in the database.
    """
    from sqlalchemy.exc import SQLAlchemyError

    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    from app.main import app
    app.state.arq_pool = mock_pool

    from app.services.knowledge_service import knowledge_service
    storage = knowledge_service.storage_provider
    uploaded_keys = []
    original_upload = storage.upload

    async def tracking_upload(key: str, data: bytes):
        uploaded_keys.append(key)
        await original_upload(key, data)

    # Patch upload to capture storage key, and patch commit in knowledge_service to fail
    with patch.object(storage, "upload", side_effect=tracking_upload):
        with patch(
            "app.services.knowledge_service.AsyncSession.commit",
            side_effect=SQLAlchemyError("Simulated DB commit error"),
        ):
            files = {"file": ("db_fail.pdf", VALID_PDF_BYTES, "application/pdf")}
            res = await async_client.post(
                "/api/v1/knowledge/files",
                files=files,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 500
            assert mock_pool.enqueue_job.call_count == 0

            # Verify physical storage file was cleaned up
            assert len(uploaded_keys) == 1
            storage_exists = await storage.exists(uploaded_keys[0])
            assert storage_exists is False

    # Restore app state
    app.state.arq_pool = None

    # Verify no orphan record exists for this business
    async with async_session_factory() as verify_db:
        stmt = select(KnowledgeFile).where(
            KnowledgeFile.business_id == biz_id,
            KnowledgeFile.filename == "db_fail.pdf",
        )
        orphan = (await verify_db.execute(stmt)).scalar_one_or_none()
        assert orphan is None


# ============================================================================
# 26. Enqueue Failure After Commit: Updates Record to Failed and Durably Persists
# ============================================================================

@pytest.mark.asyncio
async def test_arq_enqueue_failure_after_commit_handled_safely(
    async_client: AsyncClient,
):
    """Verifies that if ARQ enqueue fails after database commit:
    1. The API returns HTTP 202 Accepted.
    2. Response body shows status='failed' with error_message='Background processing queue unavailable'.
    3. The database record is durably committed with status='failed'.
    """
    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=Exception("Redis connection timed out"))

    from app.main import app
    app.state.arq_pool = mock_pool

    try:
        files = {"file": ("enqueue_err.pdf", VALID_PDF_BYTES, "application/pdf")}
        res = await async_client.post(
            "/api/v1/knowledge/files",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 202
        data = res.json()
        file_id = uuid.UUID(data["id"])
        assert data["processing_status"] == "failed"
        assert "Background processing queue unavailable" in data["error_message"]

        # Verify through an independent database session that failure status was committed
        async with async_session_factory() as verify_db:
            stmt = select(KnowledgeFile).where(KnowledgeFile.id == file_id)
            kfile = (await verify_db.execute(stmt)).scalar_one()
            assert kfile.processing_status == KnowledgeFileStatus.FAILED.value
            assert kfile.error_message == "Background processing queue unavailable"
    finally:
        app.state.arq_pool = None


# ============================================================================
# 27. Worker Not Found & Deletion Behavior Preserved
# ============================================================================

@pytest.mark.asyncio
async def test_worker_not_found_and_deletion_behavior_preserved(
    async_client: AsyncClient,
):
    """Verifies that deleting a file via API cascades and that an ARQ worker
    attempting to process the deleted file cleanly returns status='not_found'
    without raising Retry or error.
    """
    from app.worker.tasks import process_knowledge_file

    _, token, biz = await create_owner_with_business(async_client)
    biz_id = uuid.UUID(biz["id"])

    # 1. Upload file
    files = {"file": ("to_be_deleted.pdf", VALID_PDF_BYTES, "application/pdf")}
    up_res = await async_client.post(
        "/api/v1/knowledge/files",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert up_res.status_code == 202
    file_id = uuid.UUID(up_res.json()["id"])

    # 2. Delete file via API
    del_res = await async_client.delete(
        f"/api/v1/knowledge/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # 3. Simulate ARQ worker executing on the deleted file
    ctx = {
        "job_id": "test_job_deleted",
        "job_try": 1,
        "storage_provider": get_storage_provider(),
        "session_factory": async_session_factory,
    }
    worker_result = await process_knowledge_file(ctx, file_id)

    assert worker_result["status"] == "not_found"
    assert worker_result["file_id"] == str(file_id)
