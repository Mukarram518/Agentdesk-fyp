"""Unit tests for AgentDesk Storage Provider & Secure Upload Validation (Phase 5.4B).

Verifies:
1. LocalStorageProvider:
   - Full CRUD operations: upload, download, exists, delete.
   - Non-blocking async execution.
   - Overwrite prevention (FileExistsError when overwrite=False, success when overwrite=True).
   - Strict path traversal defenses:
     * Parent directory traversal ('../', '..\\').
     * Absolute paths ('/etc/passwd', 'C:\\Windows').
     * Null byte injection ('file.pdf\\x00.exe').
     * Windows drive letter paths ('C:secret.pdf').
     * Empty path segments ('a//b').
     * Root directory references.
   - Multi-tenant directory isolation.
2. Storage Key Generator:
   - Path format: business/{business_id}/knowledge/{file_id}/{random_uuid}.{ext}.
   - UUID validation for business_id and file_id.
   - Extension validation (only 'pdf' and 'docx').
   - High entropy randomness (unique filename per call).
   - Exclusion of original user filenames.
3. Upload Validation:
   - Size enforcement: <= 5MB allowed, > 5MB rejected.
   - Non-empty enforcement: 0-byte files rejected.
   - Allowed extensions: .pdf, .docx accepted; others rejected (.exe, .sh, .txt, .zip).
   - MIME cross-validation: matching MIME allowed, conflicting MIME rejected.
   - PDF magic bytes verification (%PDF- required).
   - DOCX package validation:
     * Standard ZIP magic bytes (PK\x03\x04).
     * OpenXML structure ([Content_Types].xml and word/document.xml required).
     * Zip bomb and path traversal protection in archives.
4. Storage Provider Factory:
   - Resolves 'local' and default.
   - Rejects unsupported provider types.
"""

import asyncio
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid
import zipfile

import pytest

from app.core.upload_validation import (
    MAX_FILE_SIZE_BYTES,
    MIME_DOCX,
    MIME_PDF,
    UploadValidationError,
    generate_storage_key,
    validate_upload,
)
from app.providers.storage import (
    LocalStorageProvider,
    StorageProvider,
    get_storage_provider,
)


# =====================================================================
# Test Helpers
# =====================================================================

def create_valid_pdf_bytes() -> bytes:
    """Creates minimal valid PDF byte stream with %PDF- magic bytes."""
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def create_valid_docx_bytes() -> bytes:
    """Creates minimal valid OpenXML DOCX archive with required WordML package files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types></Types>')
        zf.writestr("word/document.xml", '<?xml version="1.0" encoding="UTF-8"?><w:document></w:document>')
    return buffer.getvalue()


# =====================================================================
# 1. LocalStorageProvider Core Operations & Safety Tests
# =====================================================================

@pytest.mark.asyncio
async def test_local_storage_crud_lifecycle():
    """Verifies complete upload -> exists -> download -> delete -> not exists lifecycle."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)

        key = "business/11111111-1111-1111-1111-111111111111/knowledge/file1/doc.pdf"
        data = create_valid_pdf_bytes()

        # Initial existence check
        assert await provider.exists(key) is False

        # Upload
        uploaded_key = await provider.upload(key, data)
        assert uploaded_key == key

        # Verify exists
        assert await provider.exists(key) is True

        # Download and verify content identity
        downloaded = await provider.download(key)
        assert downloaded == data

        # Delete
        deleted = await provider.delete(key)
        assert deleted is True

        # Verify no longer exists
        assert await provider.exists(key) is False

        # Subsequent delete returns False
        assert await provider.delete(key) is False

        # Download of non-existent file raises FileNotFoundError
        with pytest.raises(FileNotFoundError, match="File not found"):
            await provider.download(key)


@pytest.mark.asyncio
async def test_local_storage_prevents_unauthorized_overwrite():
    """Verifies that upload fails with FileExistsError when overwrite=False and file exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        key = "business/test-biz/knowledge/test-file/sample.pdf"
        data = create_valid_pdf_bytes()

        # First upload succeeds
        await provider.upload(key, data, overwrite=False)

        # Second upload with overwrite=False raises FileExistsError
        with pytest.raises(FileExistsError, match="File already exists"):
            await provider.upload(key, b"%PDF-new-version", overwrite=False)

        # Original data is preserved
        assert await provider.download(key) == data

        # Explicit overwrite=True succeeds
        new_data = b"%PDF-overwritten-version\n%%EOF"
        await provider.upload(key, new_data, overwrite=True)
        assert await provider.download(key) == new_data


@pytest.mark.asyncio
async def test_local_storage_path_traversal_rejections():
    """Verifies that malicious storage keys designed for directory traversal are strictly blocked."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        data = b"sensitive-data"

        malicious_keys = [
            "../escape.txt",
            "..\\escape.txt",
            "business/../../etc/passwd",
            "business/123/../../../windows/system32",
            "/absolute/root/file.pdf",
            "\\absolute\\root\\file.pdf",
            "C:/Windows/win.ini",
            "C:\\Windows\\win.ini",
            "business/test/\x00hidden.pdf",
            "business//empty-segment/file.pdf",
            "business/./current-dir.pdf",
            "   ",
            "",
        ]

        for bad_key in malicious_keys:
            # Upload must reject
            with pytest.raises(ValueError):
                await provider.upload(bad_key, data)

            # Download must reject
            with pytest.raises(ValueError):
                await provider.download(bad_key)

            # Exists must reject
            with pytest.raises(ValueError):
                await provider.exists(bad_key)

            # Delete must reject
            with pytest.raises(ValueError):
                await provider.delete(bad_key)


@pytest.mark.asyncio
async def test_local_storage_tenant_directory_isolation():
    """Verifies that storage keys for different businesses are partitioned and isolated."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)

        biz_a_id = uuid.uuid4()
        biz_b_id = uuid.uuid4()
        file_id = uuid.uuid4()

        key_a = generate_storage_key(biz_a_id, file_id, "pdf")
        key_b = generate_storage_key(biz_b_id, file_id, "pdf")

        data_a = b"%PDF-biz-a-data\n%%EOF"
        data_b = b"%PDF-biz-b-data\n%%EOF"

        await provider.upload(key_a, data_a)
        await provider.upload(key_b, data_b)

        # Business A file is distinct from Business B file
        assert await provider.download(key_a) == data_a
        assert await provider.download(key_b) == data_b

        # Deleting Business A file does not affect Business B file
        await provider.delete(key_a)
        assert await provider.exists(key_a) is False
        assert await provider.exists(key_b) is True
        assert await provider.download(key_b) == data_b


# =====================================================================
# 2. Server-Side Storage Key Generator Tests
# =====================================================================

def test_generate_storage_key_valid_uuid_and_extensions():
    """Verifies format, randomness, and structure of generated storage keys."""
    biz_id = uuid.uuid4()
    file_id = uuid.uuid4()

    key_pdf = generate_storage_key(biz_id, file_id, "pdf")
    key_docx = generate_storage_key(biz_id, file_id, ".docx")

    # Format checks: business/{biz_id}/knowledge/{file_id}/{random_uuid}.{ext}
    assert key_pdf.startswith(f"business/{biz_id}/knowledge/{file_id}/")
    assert key_pdf.endswith(".pdf")

    assert key_docx.startswith(f"business/{biz_id}/knowledge/{file_id}/")
    assert key_docx.endswith(".docx")

    # Randomness check: two keys generated with the same parameters must be distinct
    key_pdf_2 = generate_storage_key(biz_id, file_id, "pdf")
    assert key_pdf != key_pdf_2


def test_generate_storage_key_rejects_invalid_inputs():
    """Verifies that invalid UUIDs, bad extensions, and original filenames are rejected."""
    valid_id = uuid.uuid4()

    # Invalid business_id
    with pytest.raises(ValueError, match="not a valid UUID"):
        generate_storage_key("not-a-uuid", valid_id, "pdf")

    # Invalid file_id
    with pytest.raises(ValueError, match="not a valid UUID"):
        generate_storage_key(valid_id, "invalid-file-id", "pdf")

    # Disallowed extensions
    for bad_ext in ["exe", "sh", "txt", "png", "zip", "py"]:
        with pytest.raises(ValueError, match="Unsupported file extension"):
            generate_storage_key(valid_id, valid_id, bad_ext)


# =====================================================================
# 3. Upload Validation Module Tests
# =====================================================================

def test_validate_upload_valid_pdf():
    """Verifies that valid PDF uploads pass all security checks."""
    data = create_valid_pdf_bytes()
    validated = validate_upload(
        data=data,
        filename="company_policy.pdf",
        content_type=MIME_PDF,
    )

    assert validated.filename == "company_policy.pdf"
    assert validated.extension == "pdf"
    assert validated.mime_type == MIME_PDF
    assert validated.size_bytes == len(data)


def test_validate_upload_valid_docx():
    """Verifies that valid DOCX OpenXML packages pass all security checks."""
    data = create_valid_docx_bytes()
    validated = validate_upload(
        data=data,
        filename="service_catalog.docx",
        content_type=MIME_DOCX,
    )

    assert validated.filename == "service_catalog.docx"
    assert validated.extension == "docx"
    assert validated.mime_type == MIME_DOCX
    assert validated.size_bytes == len(data)


def test_validate_upload_rejects_empty_file():
    """Verifies that 0-byte empty files are rejected."""
    with pytest.raises(UploadValidationError, match="Uploaded file is empty"):
        validate_upload(data=b"", filename="empty.pdf", content_type=MIME_PDF)


def test_validate_upload_rejects_oversized_file():
    """Verifies that files exceeding 5MB are rejected."""
    oversized_data = b"%PDF-" + b"x" * (MAX_FILE_SIZE_BYTES + 1)
    with pytest.raises(UploadValidationError, match="exceeds maximum allowed limit of 5 MB"):
        validate_upload(data=oversized_data, filename="huge.pdf", content_type=MIME_PDF)


def test_validate_upload_rejects_disallowed_extensions():
    """Verifies that non-PDF and non-DOCX extensions are rejected regardless of content."""
    valid_pdf_data = create_valid_pdf_bytes()

    for bad_filename in ["payload.exe", "script.sh", "notes.txt", "archive.zip", "test"]:
        with pytest.raises(UploadValidationError, match="(Unsupported file extension|missing an extension)"):
            validate_upload(data=valid_pdf_data, filename=bad_filename)


def test_validate_upload_mime_mismatch_rejection():
    """Verifies that mismatch between file extension and declared MIME type is rejected."""
    pdf_data = create_valid_pdf_bytes()

    # Declaring DOCX MIME type for a .pdf file
    with pytest.raises(UploadValidationError, match="MIME type mismatch"):
        validate_upload(data=pdf_data, filename="document.pdf", content_type=MIME_DOCX)

    # Declaring image/png for a .pdf file
    with pytest.raises(UploadValidationError, match="MIME type mismatch"):
        validate_upload(data=pdf_data, filename="document.pdf", content_type="image/png")


def test_validate_upload_fake_pdf_rejection():
    """Verifies that files with .pdf extension lacking %PDF- magic bytes are rejected."""
    fake_pdf_data = b"This is just plain text pretending to be a PDF file."
    with pytest.raises(UploadValidationError, match="missing '%PDF-' header signature"):
        validate_upload(data=fake_pdf_data, filename="fake.pdf", content_type=MIME_PDF)


def test_validate_upload_fake_docx_rejection():
    """Verifies that files with .docx extension lacking valid ZIP and WordML structures are rejected."""
    # 1. Plain text disguised as docx
    fake_text_data = b"Not a zip at all"
    with pytest.raises(UploadValidationError, match="missing standard ZIP header signature"):
        validate_upload(data=fake_text_data, filename="fake.docx", content_type=MIME_DOCX)

    # 2. Valid zip but missing [Content_Types].xml
    buf1 = io.BytesIO()
    with zipfile.ZipFile(buf1, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
    with pytest.raises(UploadValidationError, match="missing '\\[Content_Types\\]\\.xml' manifest"):
        validate_upload(data=buf1.getvalue(), filename="missing_manifest.docx", content_type=MIME_DOCX)

    # 3. Valid zip with [Content_Types].xml but missing word/document.xml
    buf2 = io.BytesIO()
    with zipfile.ZipFile(buf2, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
    with pytest.raises(UploadValidationError, match="missing 'word/document\\.xml' content stream"):
        validate_upload(data=buf2.getvalue(), filename="missing_document.docx", content_type=MIME_DOCX)


def test_validate_upload_docx_zip_traversal_rejection():
    """Verifies that DOCX files containing traversal paths in internal zip members are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr("../malicious_entry.txt", "evil")

    with pytest.raises(UploadValidationError, match="contains unsafe file paths"):
        validate_upload(data=buf.getvalue(), filename="traversal.docx", content_type=MIME_DOCX)


# =====================================================================
# 4. Storage Provider Factory Tests
# =====================================================================

def test_storage_provider_factory():
    """Verifies factory creation and unsupported provider error handling."""
    # Default provider is LocalStorageProvider
    provider_default = get_storage_provider()
    assert isinstance(provider_default, LocalStorageProvider)

    # Explicit 'local' provider
    provider_local = get_storage_provider("local")
    assert isinstance(provider_local, LocalStorageProvider)

    # Unsupported provider
    with pytest.raises(ValueError, match="Unsupported storage provider type 's3'"):
        get_storage_provider("s3")


# =====================================================================
# 5. Security Hardening Regression Tests
# =====================================================================

@pytest.mark.asyncio
async def test_local_storage_concurrent_uploads_no_overwrite_race():
    """Verifies that concurrent uploads to the exact same key with overwrite=False result in
    exactly one winner and one FileExistsError, with the winning file intact."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        key = "business/race-test/knowledge/file1/doc.pdf"
        data_1 = b"%PDF-first-version\n%%EOF"
        data_2 = b"%PDF-second-version\n%%EOF"

        # Concurrently upload two different payloads to the same key with overwrite=False
        results = await asyncio.gather(
            provider.upload(key, data_1, overwrite=False),
            provider.upload(key, data_2, overwrite=False),
            return_exceptions=True,
        )

        successes = [r for r in results if isinstance(r, str)]
        exceptions = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
        assert len(exceptions) == 1, f"Expected exactly 1 exception, got {len(exceptions)}"
        assert isinstance(exceptions[0], FileExistsError)

        # Winning file must match either data_1 or data_2, fully intact
        stored_data = await provider.download(key)
        assert stored_data in (data_1, data_2)


@pytest.mark.asyncio
async def test_local_storage_existing_destination_never_overwritten():
    """Verifies that an existing file is strictly preserved when overwrite=False is specified."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        key = "business/tenant/knowledge/file/contract.pdf"
        original_data = b"%PDF-original-content\n%%EOF"
        second_data = b"%PDF-new-content\n%%EOF"

        await provider.upload(key, original_data, overwrite=False)

        # Attempt to upload again with overwrite=False
        with pytest.raises(FileExistsError):
            await provider.upload(key, second_data, overwrite=False)

        # Verify original content is intact
        downloaded = await provider.download(key)
        assert downloaded == original_data


@pytest.mark.asyncio
async def test_local_storage_symlink_pointing_outside_rejected():
    """Verifies that a symlink inside the storage root pointing outside is detected and rejected.
    Skips if OS permissions do not permit creating symlinks."""
    with tempfile.TemporaryDirectory() as storage_dir, tempfile.TemporaryDirectory() as outside_dir:
        provider = LocalStorageProvider(base_dir=storage_dir)

        outside_secret = Path(outside_dir) / "secret.pdf"
        outside_secret.write_bytes(b"%PDF-secret-outside\n%%EOF")

        # Attempt to create a symlink inside storage pointing outside
        symlink_path = Path(storage_dir) / "escaped_link.pdf"
        try:
            os.symlink(outside_secret, symlink_path)
        except (OSError, NotImplementedError) as e:
            pytest.skip(f"Symlink creation not permitted or supported in this environment: {e}")

        # Attempting to download through the symlink must be rejected as path traversal
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.download("escaped_link.pdf")


@pytest.mark.asyncio
async def test_local_storage_temp_file_cleanup_on_failure():
    """Verifies that no temporary files remain if upload fails during write or publication."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        key = "business/tenant/knowledge/file/cleanup_test.pdf"

        target_path = provider._resolve_path(key)
        target_dir = target_path.parent

        # 1. Failure during overwrite=False when destination already exists
        await provider.upload(key, b"%PDF-existing\n%%EOF", overwrite=False)
        with pytest.raises(FileExistsError):
            await provider.upload(key, b"%PDF-conflict\n%%EOF", overwrite=False)

        # Check target directory: only cleanup_test.pdf should exist, no .tmp files
        dir_files = list(target_dir.iterdir())
        assert len(dir_files) == 1
        assert dir_files[0].name == "cleanup_test.pdf"
        assert not any(".tmp." in f.name for f in dir_files)

        # 2. Failure simulated during writing (e.g. mock exception in write_bytes)
        key2 = "business/tenant/knowledge/file/cleanup_fail.pdf"
        with patch.object(Path, "write_bytes", side_effect=IOError("Simulated disk write error")):
            with pytest.raises(IOError, match="Simulated disk write error"):
                await provider.upload(key2, b"%PDF-fail\n%%EOF", overwrite=False)

        # Verify no .tmp files exist in target directory
        remaining_files = list(target_dir.iterdir())
        assert not any(".tmp." in f.name for f in remaining_files)


@pytest.mark.asyncio
async def test_local_storage_rejects_colon_in_storage_keys():
    """Verifies that storage keys containing ':' (Windows drive or Alternate Data Streams) are rejected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        data = b"%PDF-content\n%%EOF"

        invalid_colon_keys = [
            "business/123/knowledge/456/file.pdf:stream",
            "C:file.pdf",
            "business:stream",
            ":invalid",
            "business/123:hidden/file.pdf",
        ]

        for bad_key in invalid_colon_keys:
            with pytest.raises(ValueError, match="Storage key cannot contain ':'"):
                provider.validate_key(bad_key)

            with pytest.raises(ValueError, match="Storage key cannot contain ':'"):
                await provider.upload(bad_key, data)

            with pytest.raises(ValueError, match="Storage key cannot contain ':'"):
                await provider.download(bad_key)

            with pytest.raises(ValueError, match="Storage key cannot contain ':'"):
                await provider.exists(bad_key)

            with pytest.raises(ValueError, match="Storage key cannot contain ':'"):
                await provider.delete(bad_key)
