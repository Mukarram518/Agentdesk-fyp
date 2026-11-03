"""Upload validation and secure storage key generation for AgentDesk.

Enforces:
- 5MB maximum file size limit.
- Rejection of 0-byte (empty) files.
- Supported file types: PDF (.pdf) and DOCX (.docx).
- Magic bytes / signature verification for PDF (%PDF-) and DOCX (PK\x03\x04 + WordML structure).
- Defense against disguised executables, invalid archives, and zip bombs.
- Cross-validation between file extension, MIME type, and binary signature.
- Server-side tenant-isolated storage key generation preventing directory traversal.
"""

from dataclasses import dataclass
import io
from pathlib import Path
import re
from typing import Optional, Set, Tuple, Union
import uuid
import zipfile

from app.core.exceptions import AgentDeskException

# Constants
MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
MAX_DOCX_UNCOMPRESSED_BYTES: int = 50 * 1024 * 1024  # 50 MB safety limit for uncompressed DOCX
MAX_DOCX_ENTRIES: int = 1000  # Maximum file count inside zip archive

MIME_PDF: str = "application/pdf"
MIME_DOCX: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ALLOWED_EXTENSIONS: Set[str] = {"pdf", "docx"}

ALLOWED_MIME_TYPES: Set[str] = {
    MIME_PDF,
    MIME_DOCX,
}

EXTENSION_TO_MIME = {
    "pdf": MIME_PDF,
    "docx": MIME_DOCX,
}

# Signatures
PDF_MAGIC_BYTES: bytes = b"%PDF-"
ZIP_MAGIC_BYTES: bytes = b"PK\x03\x04"


class UploadValidationError(ValueError, AgentDeskException):
    """Raised when an uploaded file violates security policies, format rules, or size limits."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedUpload:
    """Immutable metadata container for a validated file upload."""

    filename: str
    extension: str
    mime_type: str
    size_bytes: int


def _validate_docx_zip_structure(data: bytes) -> None:
    """Verifies that byte data is a legitimate DOCX OpenXML package and not a zip bomb or executable."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # Check for zip bomb / malicious archive attributes
            infolist = zf.infolist()
            if len(infolist) > MAX_DOCX_ENTRIES:
                raise UploadValidationError(
                    f"Invalid DOCX: archive contains too many files ({len(infolist)} > {MAX_DOCX_ENTRIES})."
                )

            total_uncompressed = 0
            names = set()

            for info in infolist:
                # Check path traversal inside zip archive
                if info.filename.startswith("/") or info.filename.startswith("\\") or ".." in info.filename:
                    raise UploadValidationError("Invalid DOCX: archive contains unsafe file paths.")

                total_uncompressed += info.file_size
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise UploadValidationError(
                        f"Invalid DOCX: uncompressed size exceeds limit of {MAX_DOCX_UNCOMPRESSED_BYTES} bytes."
                    )

                names.add(info.filename)

            # OpenXML DOCX packages MUST contain [Content_Types].xml and word/document.xml
            if "[Content_Types].xml" not in names:
                raise UploadValidationError("Invalid DOCX: missing '[Content_Types].xml' manifest.")

            if "word/document.xml" not in names:
                raise UploadValidationError("Invalid DOCX: missing 'word/document.xml' content stream.")

    except zipfile.BadZipFile as e:
        raise UploadValidationError(f"Invalid DOCX: corrupted or invalid ZIP archive: {str(e)}")


def validate_upload(
    data: bytes,
    filename: str,
    content_type: Optional[str] = None,
) -> ValidatedUpload:
    """Validates an uploaded file against size, extension, MIME, and magic-byte constraints.

    Args:
        data: Raw file byte content.
        filename: Original file name provided by the client.
        content_type: Optional MIME type reported in the HTTP upload header.

    Returns:
        ValidatedUpload dataclass with verified metadata.

    Raises:
        UploadValidationError: If validation fails.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise UploadValidationError("Uploaded file content must be bytes.")

    size_bytes = len(data)

    # 1. Size Validation
    if size_bytes == 0:
        raise UploadValidationError("Uploaded file is empty (0 bytes).")

    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise UploadValidationError(
            f"File size ({size_bytes} bytes) exceeds maximum allowed limit of 5 MB ({MAX_FILE_SIZE_BYTES} bytes)."
        )

    # 2. Filename & Extension Validation
    if not isinstance(filename, str) or not filename.strip():
        raise UploadValidationError("Filename cannot be empty.")

    clean_filename = Path(filename).name.strip()
    if not clean_filename:
        raise UploadValidationError("Invalid filename.")

    # Extract extension (after final period)
    if "." not in clean_filename:
        raise UploadValidationError(f"File '{clean_filename}' is missing an extension.")

    raw_ext = clean_filename.rsplit(".", 1)[-1].lower()
    if raw_ext not in ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UploadValidationError(
            f"Unsupported file extension '.{raw_ext}'. Allowed extensions are: {allowed_list}."
        )

    expected_mime = EXTENSION_TO_MIME[raw_ext]

    # 3. Content Type Cross-Validation
    if content_type:
        normalized_mime = content_type.lower().split(";")[0].strip()
        # Disallow explicit mismatch (e.g., claiming image/png or text/plain for a pdf)
        generic_mimes = {"application/octet-stream", "binary/octet-stream"}
        if normalized_mime not in generic_mimes and normalized_mime != expected_mime:
            raise UploadValidationError(
                f"MIME type mismatch: extension '.{raw_ext}' expects '{expected_mime}', "
                f"but received '{normalized_mime}'."
            )

    # 4. Binary Signature / Magic Bytes Validation
    if raw_ext == "pdf":
        if not data.startswith(PDF_MAGIC_BYTES):
            raise UploadValidationError("Invalid PDF: missing '%PDF-' header signature.")
    elif raw_ext == "docx":
        if not data.startswith(ZIP_MAGIC_BYTES):
            raise UploadValidationError("Invalid DOCX: missing standard ZIP header signature.")
        _validate_docx_zip_structure(data)

    return ValidatedUpload(
        filename=clean_filename,
        extension=raw_ext,
        mime_type=expected_mime,
        size_bytes=size_bytes,
    )


def generate_storage_key(
    business_id: Union[uuid.UUID, str],
    file_id: Union[uuid.UUID, str],
    extension: str,
) -> str:
    """Generates a secure, tenant-scoped storage key for an uploaded file.

    Format:
        business/{business_id}/knowledge/{file_id}/{random_uuid}.{extension}

    Security guarantees:
    - Never embeds user-supplied original filenames in keys.
    - Validates business_id and file_id as valid UUIDs.
    - Validates extension against approved types ('pdf', 'docx').
    - Produces normalized POSIX-style relative path.

    Args:
        business_id: UUID of the owning business.
        file_id: UUID of the KnowledgeFile database record.
        extension: File extension ('pdf' or 'docx').

    Returns:
        Safe relative storage key string.

    Raises:
        ValueError: If UUIDs are invalid or extension is not allowed.
    """
    # Validate business_id UUID
    try:
        biz_uuid = uuid.UUID(str(business_id))
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"Invalid business_id: '{business_id}' is not a valid UUID.")

    # Validate file_id UUID
    try:
        file_uuid = uuid.UUID(str(file_id))
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"Invalid file_id: '{file_id}' is not a valid UUID.")

    # Validate extension
    if not isinstance(extension, str):
        raise ValueError(f"Invalid extension: expected string, got {type(extension)}.")

    norm_ext = extension.lstrip(".").lower().strip()
    if norm_ext not in ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file extension '{extension}'. Allowed: {allowed_list}.")

    random_filename = uuid.uuid4().hex

    return f"business/{biz_uuid}/knowledge/{file_uuid}/{random_filename}.{norm_ext}"
