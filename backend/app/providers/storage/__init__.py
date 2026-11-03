"""Storage providers package for AgentDesk."""

from typing import Optional

from app.core.upload_validation import generate_storage_key
from app.providers.storage.base import StorageProvider
from app.providers.storage.local import LocalStorageProvider

__all__ = [
    "StorageProvider",
    "LocalStorageProvider",
    "get_storage_provider",
    "generate_storage_key",
]


def get_storage_provider(provider_type: Optional[str] = None) -> StorageProvider:
    """Factory returning configured storage provider instance.

    Args:
        provider_type: Optional string ('local'). If None, defaults to 'local'.

    Returns:
        Instance of StorageProvider.

    Raises:
        ValueError: If an unsupported provider type is requested.
    """
    selected_type = (provider_type or "local").lower().strip()

    if selected_type == "local":
        return LocalStorageProvider()
    else:
        raise ValueError(
            f"Unsupported storage provider type '{provider_type}'. "
            "Supported types are: 'local'."
        )
