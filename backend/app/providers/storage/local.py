"""Local filesystem storage provider implementation for AgentDesk.

Stores files in a secure, configurable directory outside the public web root.
Enforces strict path traversal defenses and atomic file writes.
"""

import asyncio
import os
from pathlib import Path
import re
from typing import Optional, Union
import uuid

from app.core.config import get_settings
from app.providers.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider for AgentDesk.

    Features:
    - Root directory configured via application settings (`STORAGE_LOCAL_DIR`).
    - Robust path traversal prevention (rejects '..', absolute paths, Windows drives, null bytes).
    - Enforces that destination paths strictly resolve inside the configured storage root.
    - Prevents overwriting existing files unless explicitly requested.
    - Atomic writes via temporary files to avoid partial or corrupted writes.
    - Non-blocking I/O through `asyncio.to_thread`.
    """

    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        """Initializes the LocalStorageProvider.

        Args:
            base_dir: Optional custom storage root path. If not provided,
                      uses `STORAGE_LOCAL_DIR` from application settings.
        """
        raw_base = base_dir or get_settings().STORAGE_LOCAL_DIR
        self.base_path = Path(raw_base).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def validate_key(self, key: str) -> None:
        """Validates that a storage key is well-formed and safe against path traversal.

        Args:
            key: Relative POSIX-style storage key.

        Raises:
            ValueError: If the key is empty, absolute, contains traversal sequences
                        (e.g., '..', null bytes), or has invalid formatting.
        """
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Storage key cannot be empty or whitespace-only.")

        # Check for null bytes
        if "\x00" in key:
            raise ValueError("Storage key contains invalid characters (null byte).")

        # Check for Windows alternate data streams or drive letters
        if ":" in key:
            raise ValueError("Storage key cannot contain ':' (Windows drive or alternate data stream indicator).")

        # Check for leading slashes / absolute paths
        if key.startswith(("/", "\\")):
            raise ValueError("Storage key must be a relative path, not absolute.")

        # Check for Windows drive letters (e.g., C:, D:)
        if re.match(r"^[a-zA-Z]:", key):
            raise ValueError("Storage key must be a relative path, not a Windows drive path.")

        # Check components for traversal or empty segments
        segments = key.replace("\\", "/").split("/")
        for seg in segments:
            if seg in ("..", "."):
                raise ValueError("Storage key cannot contain directory traversal segments ('..' or '.').")
            if seg == "":
                raise ValueError("Storage key cannot contain empty path segments.")

    def _resolve_path(self, key: str) -> Path:
        """Resolves a storage key to an absolute filesystem Path and verifies confinement.

        Args:
            key: Relative storage key.

        Returns:
            Resolved absolute Path strictly within self.base_path.

        Raises:
            ValueError: If traversal is detected or key resolves outside base_path.
        """
        self.validate_key(key)
        normalized_key = key.replace("\\", "/").strip("/")
        target_path = (self.base_path / normalized_key).resolve()

        try:
            target_path.relative_to(self.base_path)
        except ValueError:
            raise ValueError("Path traversal detected: storage key resolves outside storage root.")

        if target_path == self.base_path:
            raise ValueError("Storage key cannot resolve directly to the storage root directory.")

        return target_path

    async def upload(self, key: str, data: bytes, overwrite: bool = False) -> str:
        """Stores file data at the specified storage key asynchronously.

        Args:
            key: Relative storage key.
            data: Raw file bytes.
            overwrite: Whether to allow overwriting an existing file. Defaults to False.

        Returns:
            The normalized storage key of the stored file.

        Raises:
            ValueError: If key is invalid or data is not bytes.
            FileExistsError: If overwrite is False and destination already exists.
            RuntimeError: If writing to disk fails.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("Upload data must be bytes or bytearray.")

        target_path = self._resolve_path(key)

        def _sync_write() -> None:
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically to a temporary file in the target directory
            temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp.{uuid.uuid4().hex}")
            try:
                temp_path.write_bytes(data)

                if overwrite:
                    # Atomic replace when overwrite is explicitly permitted
                    os.replace(temp_path, target_path)
                else:
                    # Atomic no-replace publication via hard link on the same filesystem
                    try:
                        os.link(temp_path, target_path)
                    except FileExistsError:
                        raise FileExistsError(f"File already exists at storage key: '{key}'")
                    except OSError as e:
                        # Catch WinError 183 / EEXIST mapped through OSError
                        if getattr(e, "winerror", None) == 183 or getattr(e, "errno", None) == 17:
                            raise FileExistsError(f"File already exists at storage key: '{key}'")
                        raise RuntimeError(
                            f"Atomic publication failed for storage key '{key}': {e}. "
                            "Local storage requires an operating system and filesystem supporting atomic links."
                        ) from e
                    finally:
                        # Clean up temporary link after publication or failed link attempt
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except OSError:
                                pass
            except Exception:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                raise

        await asyncio.to_thread(_sync_write)
        return key.replace("\\", "/").strip("/")

    async def download(self, key: str) -> bytes:
        """Retrieves file bytes stored at the specified storage key asynchronously.

        Args:
            key: Relative storage key.

        Returns:
            Raw file bytes.

        Raises:
            ValueError: If key is invalid.
            FileNotFoundError: If the file does not exist.
        """
        target_path = self._resolve_path(key)

        def _sync_read() -> bytes:
            if not target_path.is_file():
                raise FileNotFoundError(f"File not found at storage key: '{key}'")
            return target_path.read_bytes()

        return await asyncio.to_thread(_sync_read)

    async def delete(self, key: str) -> bool:
        """Deletes a file stored at the specified key asynchronously.

        Args:
            key: Relative storage key.

        Returns:
            True if file was deleted, False if file did not exist.

        Raises:
            ValueError: If key is invalid or points to a directory.
        """
        target_path = self._resolve_path(key)

        def _sync_delete() -> bool:
            if not target_path.exists():
                return False
            if not target_path.is_file():
                raise ValueError(f"Path is not a regular file: '{key}'")
            target_path.unlink()
            return True

        return await asyncio.to_thread(_sync_delete)

    async def exists(self, key: str) -> bool:
        """Checks whether a file exists at the specified storage key asynchronously.

        Args:
            key: Relative storage key.

        Returns:
            True if file exists and is a regular file, False otherwise.
        """
        target_path = self._resolve_path(key)

        def _sync_exists() -> bool:
            return target_path.is_file()

        return await asyncio.to_thread(_sync_exists)
