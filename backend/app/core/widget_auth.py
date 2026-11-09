"""Cryptographic and origin validation utilities for public web widget authentication.

Security guarantees:
- Token generation uses HMAC-SHA256 with a dedicated signing secret (WIDGET_TOKEN_SECRET).
- Never reuses owner session tokens or authentication secrets.
- Tokens are time-bounded (default 15 minutes) and tamper-resistant.
- Verification uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
- RFC 6454-compliant origin normalization and exact equality matching against business allowed_origins.
- Suffix attacks, substring matching, paths, queries, and wildcard origins are rejected by default.
"""

import base64
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import secrets
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings


class WidgetSecurityError(Exception):
    """Base exception for widget security and authentication errors."""
    pass


class WidgetTokenError(WidgetSecurityError):
    """Raised when a widget token is malformed, invalid, or cannot be parsed."""
    pass


class WidgetTokenConfigurationError(WidgetSecurityError):
    """Raised when the widget signing secret is missing or misconfigured."""
    pass


class WidgetTokenExpiredError(WidgetTokenError):
    """Raised when a widget token's expiry timestamp has passed."""
    pass


class WidgetTokenInvalidSignatureError(WidgetTokenError):
    """Raised when a widget token signature is invalid or tampered with."""
    pass


class WidgetOriginError(WidgetSecurityError):
    """Raised when an origin is unauthorized, invalid, or missing when required."""
    pass


class WidgetTokenPayload(BaseModel):
    """Verified payload extracted from a signed widget token."""

    model_config = ConfigDict(frozen=True)

    business_id: uuid.UUID = Field(..., description="UUID identity of the owning business tenant.")
    issued_at: datetime = Field(..., description="Timestamp when the token was issued.")
    expires_at: datetime = Field(..., description="Timestamp when the token expires.")
    jti: str = Field(..., description="Unique cryptographic nonce/identifier for the token.")
    token_type: str = Field(default="widget", description="Token scope identifier.")
    is_preview: bool = Field(default=False, description="Whether token was issued for dashboard preview.")


MIN_WIDGET_SECRET_LENGTH = 32


def _validate_signing_secret(secret: Optional[str]) -> str:
    """Validates presence and minimum entropy of the widget signing secret."""
    settings = get_settings()
    signing_secret = secret if secret is not None else settings.WIDGET_TOKEN_SECRET

    if not signing_secret or not signing_secret.strip():
        raise WidgetTokenConfigurationError(
            "Widget signing secret is required but not configured. Set WIDGET_TOKEN_SECRET."
        )

    stripped = signing_secret.strip()
    if len(stripped) < MIN_WIDGET_SECRET_LENGTH:
        raise WidgetTokenConfigurationError(
            f"Widget signing secret is too weak (length {len(stripped)}). "
            f"Must be at least {MIN_WIDGET_SECRET_LENGTH} characters for HMAC-SHA256 security."
        )
    return stripped


def _b64url_encode(data: bytes) -> str:
    """Encodes bytes into URL-safe Base64 string without trailing padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    """Decodes a URL-safe Base64 string, restoring padding as necessary."""
    padding_needed = (4 - len(raw) % 4) % 4
    padded = raw + ("=" * padding_needed)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def generate_widget_token(
    business_id: uuid.UUID,
    secret: Optional[str] = None,
    expire_minutes: Optional[int] = None,
    issued_at: Optional[datetime] = None,
    is_preview: bool = False,
) -> str:
    """Generates a cryptographically signed HMAC-SHA256 JWT widget token.

    Parameters:
        business_id: UUID of the business tenant.
        secret: Dedicated signing secret (defaults to WIDGET_TOKEN_SECRET from settings).
        expire_minutes: Token validity in minutes (defaults to WIDGET_TOKEN_EXPIRE_MINUTES or 15).
        issued_at: Optional explicit issue time (defaults to current UTC time).
        is_preview: Whether the token is scoped for dashboard preview.

    Returns:
        Compact URL-safe JWT string: header.payload.signature
    """
    settings = get_settings()
    signing_secret = _validate_signing_secret(secret)

    validity_minutes = (
        expire_minutes
        if expire_minutes is not None
        else (settings.WIDGET_TOKEN_EXPIRE_MINUTES or 15)
    )
    if validity_minutes <= 0:
        raise WidgetTokenConfigurationError(
            f"Token validity must be a positive integer, got {validity_minutes}."
        )

    now = issued_at or datetime.now(timezone.utc)
    exp = now + timedelta(minutes=validity_minutes)

    header: Dict[str, Any] = {"alg": "HS256", "typ": "JWT"}
    payload: Dict[str, Any] = {
        "sub": str(business_id),
        "business_id": str(business_id),
        "type": "widget",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(16),
    }
    if is_preview:
        payload["is_preview"] = True

    header_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    header_b64 = _b64url_encode(header_bytes)
    payload_b64 = _b64url_encode(payload_bytes)

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_widget_token(
    token: str,
    secret: Optional[str] = None,
    leeway_seconds: int = 10,
    current_time: Optional[datetime] = None,
) -> WidgetTokenPayload:
    """Verifies a signed HMAC-SHA256 widget token and returns the business identity.

    Parameters:
        token: Raw compact JWT string.
        secret: Dedicated signing secret (defaults to WIDGET_TOKEN_SECRET from settings).
        leeway_seconds: Allowed clock skew in seconds (default 10s).
        current_time: Optional explicit timestamp for testing expiry.

    Returns:
        WidgetTokenPayload containing validated business_id and token metadata.

    Raises:
        WidgetTokenConfigurationError: If signing secret is missing.
        WidgetTokenError: If token is malformed, has invalid claims, or wrong type.
        WidgetTokenInvalidSignatureError: If signature verification fails.
        WidgetTokenExpiredError: If token has expired.
    """
    settings = get_settings()
    signing_secret = _validate_signing_secret(secret)

    if not token or not isinstance(token, str):
        raise WidgetTokenError("Widget token must be a non-empty string.")

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise WidgetTokenError(
            f"Malformed widget token: expected 3 dot-separated segments, got {len(parts)}."
        )

    header_b64, payload_b64, sig_b64 = parts

    # 1. Decode signature
    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception as e:
        raise WidgetTokenError(f"Malformed widget token signature encoding: {e}") from e

    # 2. Verify signature with constant-time equality check
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        signing_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(actual_sig, expected_sig):
        raise WidgetTokenInvalidSignatureError(
            "Invalid widget token signature. Token may have been tampered with or signed with a different key."
        )

    # 3. Decode and validate header
    try:
        header_bytes = _b64url_decode(header_b64)
        header = json.loads(header_bytes.decode("utf-8"))
    except Exception as e:
        raise WidgetTokenError(f"Malformed widget token header: {e}") from e

    if not isinstance(header, dict) or header.get("alg") != "HS256" or header.get("typ") != "JWT" or len(header) != 2:
        raise WidgetTokenError("Invalid token header. Only HS256 JWT tokens with standard header are supported.")

    # 4. Decode and validate payload
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        raise WidgetTokenError(f"Malformed widget token payload: {e}") from e

    if not isinstance(payload, dict):
        raise WidgetTokenError("Invalid widget token payload: must be a JSON object.")

    if payload.get("type") != "widget":
        raise WidgetTokenError(
            f"Invalid token type: expected 'widget', got '{payload.get('type')}'."
        )

    # 5. Verify timing and expiration
    now = current_time or datetime.now(timezone.utc)
    now_ts = now.timestamp()

    exp_ts = payload.get("exp")
    if exp_ts is None or type(exp_ts) not in (int, float) or isinstance(exp_ts, bool) or exp_ts <= 0:
        raise WidgetTokenError("Missing or invalid 'exp' claim in widget token.")

    iat_ts = payload.get("iat")
    if iat_ts is None or type(iat_ts) not in (int, float) or isinstance(iat_ts, bool) or iat_ts <= 0:
        raise WidgetTokenError("Missing or invalid 'iat' claim in widget token.")

    if exp_ts <= iat_ts:
        raise WidgetTokenError("Invalid token lifetime: 'exp' must be strictly greater than 'iat'.")

    if exp_ts < (now_ts - leeway_seconds):
        raise WidgetTokenExpiredError(
            f"Widget token has expired at {datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()}."
        )

    if iat_ts > (now_ts + leeway_seconds):
        raise WidgetTokenError("Widget token issue time 'iat' is in the future.")

    # 6. Extract business identity and verify sub/business_id consistency
    raw_biz = payload.get("business_id")
    raw_sub = payload.get("sub")
    if not raw_biz or not isinstance(raw_biz, str):
        raise WidgetTokenError("Missing or invalid 'business_id' claim in widget token.")
    if not raw_sub or not isinstance(raw_sub, str):
        raise WidgetTokenError("Missing or invalid 'sub' claim in widget token.")
    if raw_biz != raw_sub:
        raise WidgetTokenError("Token claims conflict: 'business_id' does not match 'sub'.")

    try:
        business_id = uuid.UUID(raw_biz)
    except (ValueError, TypeError) as e:
        raise WidgetTokenError(f"Invalid business UUID in widget token: {raw_biz}") from e

    # 7. Check 'jti' nonce claim (must be non-empty string)
    jti = payload.get("jti")
    if not jti or not isinstance(jti, str) or not jti.strip():
        raise WidgetTokenError("Missing or invalid 'jti' nonce claim in widget token.")

    # 8. Check 'is_preview' claim if present (must be strict boolean)
    raw_is_preview = payload.get("is_preview")
    if raw_is_preview is not None:
        if type(raw_is_preview) is not bool:
            raise WidgetTokenError(
                f"Invalid 'is_preview' claim: expected boolean, got {type(raw_is_preview).__name__}."
            )
        is_preview = raw_is_preview
    else:
        is_preview = False

    return WidgetTokenPayload(
        business_id=business_id,
        issued_at=datetime.fromtimestamp(iat_ts, tz=timezone.utc),
        expires_at=datetime.fromtimestamp(exp_ts, tz=timezone.utc),
        jti=jti.strip(),
        token_type="widget",
        is_preview=is_preview,
    )


def normalize_origin(origin: Optional[str]) -> Optional[str]:
    """Normalizes an HTTP origin to standard RFC 6454 format (scheme://host[:port]).

    Security and normalization rules:
    - Rejects None, non-string, whitespace-only, 'null', and '*' origins.
    - Strips leading and trailing whitespace.
    - Lowers case of scheme and hostname.
    - Removes trailing slashes.
    - Omit standard default ports (:80 for http, :443 for https).
    - Preserves non-standard explicit ports (e.g. :3000, :8443).
    - Rejects origins with paths, query strings, fragments, or userinfo.
    - Rejects origins containing wildcards ('*') or spaces.
    """
    if not origin or not isinstance(origin, str):
        return None

    cleaned = origin.strip()
    if not cleaned or cleaned.lower() in ("null", "*") or any(c.isspace() or not c.isprintable() or c == "\x00" for c in cleaned):
        return None

    try:
        parsed = urlsplit(cleaned)

        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            return None

        hostname = (parsed.hostname or "").lower()
        if not hostname or "*" in hostname or "/" in hostname or "\\" in hostname:
            return None

        # RFC 6454 origins do not contain paths, queries, fragments, or credentials
        if parsed.path and parsed.path != "/":
            return None
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            return None

        # Normalize default ports
        port = parsed.port
        port_str = ""
        if port is not None:
            if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
                port_str = ""
            else:
                port_str = f":{port}"

        return f"{scheme}://{hostname}{port_str}"
    except (ValueError, TypeError, AttributeError):
        return None


def validate_business_origin(
    candidate_origin: Optional[str],
    allowed_origins: Optional[List[str]],
    allow_wildcard: bool = False,
) -> bool:
    """Validates candidate origin against the list of permitted business origins.

    Security guarantees:
    - Candidate origin must normalize successfully to standard RFC 6454 scheme://host[:port].
    - Missing or empty candidate origin returns False.
    - Missing or empty allowed_origins returns False (closed/deny-by-default).
    - Wildcard origins ('*') are rejected by default unless allow_wildcard=True.
    - Matches normalized candidate origin strictly against normalized allowed origins using exact string equality.
    - Prevents substring matching, prefix matching, or suffix attacks (e.g. 'evil-example.com' matching 'example.com').
    """
    if not candidate_origin or not isinstance(candidate_origin, str):
        return False

    normalized_candidate = normalize_origin(candidate_origin)
    if not normalized_candidate:
        return False

    if not allowed_origins or not isinstance(allowed_origins, list):
        return False

    for entry in allowed_origins:
        if not entry or not isinstance(entry, str):
            continue

        stripped_entry = entry.strip()
        if stripped_entry == "*":
            if allow_wildcard:
                return True
            continue

        normalized_allowed = normalize_origin(stripped_entry)
        if normalized_allowed and normalized_allowed == normalized_candidate:
            return True

    return False


def get_trusted_dashboard_origins() -> List[str]:
    """Returns normalized server-configured trusted dashboard origins from FRONTEND_URL and CORS_ORIGINS."""
    settings = get_settings()
    raw_candidates: List[str] = []

    frontend_url = getattr(settings, "FRONTEND_URL", None)
    if frontend_url and isinstance(frontend_url, str):
        raw_candidates.append(frontend_url)

    cors = getattr(settings, "CORS_ORIGINS", None)
    if cors:
        if isinstance(cors, list):
            raw_candidates.extend(cors)
        elif isinstance(cors, str):
            raw_candidates.extend([o.strip() for o in cors.split(",") if o.strip()])

    trusted: List[str] = []
    for origin in raw_candidates:
        normalized = normalize_origin(origin)
        if normalized and normalized not in trusted:
            trusted.append(normalized)

    return trusted


def validate_preview_origin(candidate_origin: Optional[str]) -> bool:
    """Validates that candidate origin matches a server-configured trusted dashboard origin.

    Security guarantees:
    - Fails closed if candidate origin is missing, malformed, or untrusted.
    - Fails closed if trusted dashboard origins list is empty or misconfigured.
    - Wildcard ('*') origins are strictly rejected.
    - Uses exact string equality between normalized candidate and normalized trusted dashboard origins.
    """
    if not candidate_origin or not isinstance(candidate_origin, str):
        return False

    normalized_candidate = normalize_origin(candidate_origin)
    if not normalized_candidate:
        return False

    trusted_origins = get_trusted_dashboard_origins()
    if not trusted_origins:
        return False

    return normalized_candidate in trusted_origins
