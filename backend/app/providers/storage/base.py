"""Abstract interface for storage providers in AgentDesk.

Defines the asynchronous interface for storing, retrieving, checking, and deleting
files in private tenant-isolated storage (local filesystem, S3/MinIO, etc.).
"""

from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstract base class for storage providers in AgentDesk.

    All storage providers must implement this interface to guarantee provider-independence
    across local disk storage, S3-compatible cloud storage, and testing mocks.
    """

    @abstractmethod
    def validate_key(self, key: str) -> None:
        """Validates that a storage key is well-formed and safe against directory traversal attacks.

        Args:
            key: Relative POSIX-style storage key.

        Raises:
            ValueError: If the key is empty, absolute, contains directory traversal sequences
                        (e.g., '..', null bytes), or has invalid formatting.
        """
        pass

    @abstractmethod
    async def upload(self, key: str, data: bytes, overwrite: bool = False) -> str:
        """Stores file data at the specified storage key asynchronously.

        Args:
            key: Tenant-scoped relative storage key.
            data: Raw file bytes to write.
            overwrite: Whether to overwrite an existing file. If False and the file exists,
                       raises FileExistsError. Defaults to False.

        Returns:
            The normalized storage key of the stored file.

        Raises:
            ValueError: If the key is invalid or data is not bytes.
            FileExistsError: If overwrite is False and a file already exists at the key.
            RuntimeError: If the underlying storage operation fails.
        """
        pass

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Retrieves file bytes stored at the specified storage key asynchronously.

        Args:
            key: Tenant-scoped relative storage key.

        Returns:
            Raw file bytes.

        Raises:
            ValueError: If the key is invalid.
            FileNotFoundError: If no file exists at the specified key.
            RuntimeError: If retrieval fails.
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Deletes a file stored at the specified key asynchronously.

        Args:
            key: Tenant-scoped relative storage key.

        Returns:
            True if the file was found and deleted, False if it did not exist.

        Raises:
            ValueError: If the key is invalid.
            RuntimeError: If deletion fails.
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Checks whether a file exists at the specified storage key asynchronously.

        Args:
            key: Tenant-scoped relative storage key.

        Returns:
            True if the file exists, False otherwise.

        Raises:
            ValueError: If the key is invalid.
        """
        pass
