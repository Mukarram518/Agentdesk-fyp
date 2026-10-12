"""Cryptographic and password security utilities for AgentDesk."""

import hashlib
import re
import secrets
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash, Argon2Error

# Argon2id password hasher instance with recommended parameters
_password_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

# Precomputed dummy hash for constant-time comparison when an email does not exist
# Prevents user enumeration via timing attacks
_DUMMY_ARGON2_HASH = _password_hasher.hash("dummy_constant_time_salt_password_12345!")


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash safely."""
    if not hashed_password or not plain_password:
        return False
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHash, Argon2Error):
        return False


def dummy_verify_password() -> None:
    """Performs a dummy Argon2id verification to equalize response timing."""
    try:
        _password_hasher.verify(_DUMMY_ARGON2_HASH, "incorrect_dummy_guess")
    except (VerifyMismatchError, VerificationError, InvalidHash, Argon2Error):
        pass


def validate_password_strength(password: str) -> Optional[str]:
    """Validates password against complexity and safety policies.

    Requirements:
    - Minimum length: 8 characters
    - Maximum length: 128 characters (DoS protection against expensive hashes)
    - Not whitespace-only
    - At least one letter
    - At least one number or special character
    """
    if not password or len(password.strip()) == 0:
        return "Password cannot be empty or contain only whitespace."
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if len(password) > 128:
        return "Password must not exceed 128 characters."
    if not re.search(r"[a-zA-Z]", password):
        return "Password must contain at least one letter."
    if not re.search(r"[0-9!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\/`~]", password):
        return "Password must contain at least one number or special character."
    return None


def generate_session_token() -> str:
    """Generates a cryptographically secure 256-bit random URL-safe session token."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Computes SHA-256 digest of a session token for secure database persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
