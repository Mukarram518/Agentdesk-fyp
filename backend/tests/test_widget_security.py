"""Tests for Public Widget Security Foundation (Phase 7 - Step 3).

Verifies:
1. Valid widget token generation and verification.
2. Invalid signature rejection (tampered token or wrong key).
3. Expired token rejection.
4. Malformed token rejection (invalid structure, non-JWT, wrong claims, invalid UUID).
5. Missing signing secret configuration handling.
6. Valid configured origin matching.
7. Unauthorized origin rejection.
8. Missing and empty origin rejection.
9. RFC 6454 origin normalization (case-insensitivity, trailing slashes, default ports).
10. Rejection of wildcard and unsafe origin matching (suffix, prefix, path, query attacks).
11. Tenant identity derivation from verified token.
12. FastAPI dependency integration (get_widget_token, get_widget_origin, get_verified_widget_business).
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.widget_auth import (
    WidgetSecurityError,
    WidgetTokenConfigurationError,
    WidgetTokenError,
    WidgetTokenExpiredError,
    WidgetTokenInvalidSignatureError,
    WidgetTokenPayload,
    generate_widget_token,
    normalize_origin,
    validate_business_origin,
    verify_widget_token,
)
from app.api.dependencies.widget import (
    get_verified_widget_business,
    get_verified_widget_payload,
    get_widget_origin,
    get_widget_token,
    verify_business_origin,
)
from app.models.business import Business


TEST_WIDGET_SECRET = "super-secret-widget-signing-key-for-tests-32b!"


# =====================================================================
# 1. Token Generation and Verification Tests
# =====================================================================

def test_valid_widget_token():
    """Verifies that a generated widget token contains valid claims and verifies successfully."""
    biz_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    token = generate_widget_token(
        business_id=biz_id,
        secret=TEST_WIDGET_SECRET,
        expire_minutes=15,
        issued_at=now,
    )

    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    payload = verify_widget_token(
        token=token,
        secret=TEST_WIDGET_SECRET,
        current_time=now + timedelta(minutes=5),
    )

    assert isinstance(payload, WidgetTokenPayload)
    assert payload.business_id == biz_id
    assert payload.token_type == "widget"
    assert payload.jti != ""
    assert int(payload.issued_at.timestamp()) == int(now.timestamp())
    assert int(payload.expires_at.timestamp()) == int((now + timedelta(minutes=15)).timestamp())


def test_invalid_signature():
    """Verifies rejection when token is verified with wrong secret or signature is tampered."""
    biz_id = uuid.uuid4()
    token = generate_widget_token(business_id=biz_id, secret=TEST_WIDGET_SECRET)

    # 1. Verification with wrong secret fails
    with pytest.raises(WidgetTokenInvalidSignatureError, match="Invalid widget token signature"):
        verify_widget_token(token, secret="wrong-secret-key-that-does-not-match!")

    # 2. Tampered signature fails
    header_b64, payload_b64, sig_b64 = token.split(".")
    tampered_sig = ("A" if sig_b64[0] != "A" else "B") + sig_b64[1:]
    tampered_token = f"{header_b64}.{payload_b64}.{tampered_sig}"

    with pytest.raises(WidgetTokenInvalidSignatureError, match="Invalid widget token signature"):
        verify_widget_token(tampered_token, secret=TEST_WIDGET_SECRET)


def test_expired_token():
    """Verifies rejection when token expiry time has passed."""
    biz_id = uuid.uuid4()
    past_time = datetime.now(timezone.utc) - timedelta(minutes=30)

    # Token issued 30 minutes ago with 15-minute validity (expired 15 mins ago)
    token = generate_widget_token(
        business_id=biz_id,
        secret=TEST_WIDGET_SECRET,
        expire_minutes=15,
        issued_at=past_time,
    )

    with pytest.raises(WidgetTokenExpiredError, match="Widget token has expired"):
        verify_widget_token(token, secret=TEST_WIDGET_SECRET)


def test_malformed_token():
    """Verifies rejection of non-string, empty, wrong segment count, and non-JWT tokens."""
    # 1. Non-string / empty
    with pytest.raises(WidgetTokenError, match="non-empty string"):
        verify_widget_token("", secret=TEST_WIDGET_SECRET)

    # 2. Wrong dot-separated segment counts
    with pytest.raises(WidgetTokenError, match="expected 3 dot-separated segments"):
        verify_widget_token("only.two", secret=TEST_WIDGET_SECRET)

    with pytest.raises(WidgetTokenError, match="expected 3 dot-separated segments"):
        verify_widget_token("one.two.three.four", secret=TEST_WIDGET_SECRET)

    # 3. Invalid base64 signature
    with pytest.raises(WidgetTokenError):
        verify_widget_token("validheader.validpayload.???notb64???", secret=TEST_WIDGET_SECRET)

    # 4. Token issued in the future beyond leeway
    future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    future_token = generate_widget_token(
        business_id=uuid.uuid4(),
        secret=TEST_WIDGET_SECRET,
        issued_at=future_time,
    )
    with pytest.raises(WidgetTokenError, match="in the future"):
        verify_widget_token(future_token, secret=TEST_WIDGET_SECRET)


def test_missing_signing_secret():
    """Verifies that missing or blank signing secrets raise WidgetTokenConfigurationError."""
    biz_id = uuid.uuid4()

    # Generator with explicit blank secret
    with pytest.raises(WidgetTokenConfigurationError, match="secret is required"):
        generate_widget_token(business_id=biz_id, secret="")

    with pytest.raises(WidgetTokenConfigurationError, match="secret is required"):
        generate_widget_token(business_id=biz_id, secret="   ")

    # Verifier with explicit blank secret
    with pytest.raises(WidgetTokenConfigurationError, match="secret is required"):
        verify_widget_token("some.fake.token", secret="")


def test_tenant_identity_from_verified_token():
    """Verifies that business_id is extracted strictly and immutably from verified token."""
    biz_a = uuid.uuid4()
    biz_b = uuid.uuid4()

    token_a = generate_widget_token(business_id=biz_a, secret=TEST_WIDGET_SECRET)
    payload = verify_widget_token(token_a, secret=TEST_WIDGET_SECRET)

    assert payload.business_id == biz_a
    assert payload.business_id != biz_b


# =====================================================================
# 2. Origin Normalization and Validation Tests
# =====================================================================

def test_origin_normalization_valid():
    """Verifies RFC 6454 normalization of valid candidate HTTP origins."""
    # Trailing slash dropped
    assert normalize_origin("https://example.com/") == "https://example.com"

    # Lowercasing
    assert normalize_origin("HTTPS://EXAMPLE.COM") == "https://example.com"
    assert normalize_origin("https://Sub.Domain.PK/") == "https://sub.domain.pk"

    # Default ports dropped (:80 for http, :443 for https)
    assert normalize_origin("http://example.com:80") == "http://example.com"
    assert normalize_origin("https://example.com:443") == "https://example.com"

    # Custom non-default ports preserved
    assert normalize_origin("http://localhost:3000") == "http://localhost:3000"
    assert normalize_origin("https://secure.example.com:8443/") == "https://secure.example.com:8443"


def test_origin_normalization_invalid():
    """Verifies that malformed or non-origin strings normalize to None."""
    assert normalize_origin(None) is None
    assert normalize_origin("") is None
    assert normalize_origin("   ") is None
    assert normalize_origin("null") is None
    assert normalize_origin("*") is None

    # Origins cannot have paths
    assert normalize_origin("https://example.com/some/path") is None

    # Origins cannot have queries or fragments
    assert normalize_origin("https://example.com?query=1") is None
    assert normalize_origin("https://example.com#fragment") is None

    # Unsupported schemes
    assert normalize_origin("ftp://example.com") is None
    assert normalize_origin("file:///C:/test") is None
    assert normalize_origin("javascript:alert(1)") is None

    # Spaces or credentials
    assert normalize_origin("https://user:pass@example.com") is None
    assert normalize_origin("https://example .com") is None


def test_valid_configured_origin():
    """Verifies exact matching of valid candidate origin against allowed_origins."""
    allowed = ["https://mybusiness.com", "https://portal.mybusiness.com/"]

    assert validate_business_origin("https://mybusiness.com", allowed) is True
    assert validate_business_origin("https://mybusiness.com/", allowed) is True
    assert validate_business_origin("HTTPS://MYBUSINESS.COM", allowed) is True
    assert validate_business_origin("https://portal.mybusiness.com", allowed) is True


def test_unauthorized_origin():
    """Verifies rejection of origins not in the allowed list."""
    allowed = ["https://mybusiness.com"]

    assert validate_business_origin("https://attacker.com", allowed) is False
    assert validate_business_origin("https://otherbusiness.com", allowed) is False


def test_missing_and_empty_origin():
    """Verifies rejection when origin is missing, empty, or allowed list is empty."""
    assert validate_business_origin(None, ["https://mybusiness.com"]) is False
    assert validate_business_origin("", ["https://mybusiness.com"]) is False
    assert validate_business_origin("   ", ["https://mybusiness.com"]) is False

    # Empty allowed_origins list denies all
    assert validate_business_origin("https://mybusiness.com", []) is False
    assert validate_business_origin("https://mybusiness.com", None) is False


def test_rejection_of_wildcard_and_unsafe_origin_matching():
    """Verifies rejection of wildcard origins and suffix/prefix attack strings."""
    allowed = ["https://mybusiness.com"]

    # Suffix attack
    assert validate_business_origin("https://mybusiness.com.evil.com", allowed) is False

    # Prefix attack
    assert validate_business_origin("https://evil-mybusiness.com", allowed) is False

    # Subdomain mismatch (unless explicitly configured)
    assert validate_business_origin("https://sub.mybusiness.com", allowed) is False

    # Path traversal attack
    assert validate_business_origin("https://mybusiness.com/admin", allowed) is False

    # Wildcard origin rejected by default
    wildcard_allowed = ["*"]
    assert validate_business_origin("https://any-site.com", wildcard_allowed) is False
    assert validate_business_origin("https://any-site.com", wildcard_allowed, allow_wildcard=False) is False


def test_business_model_is_origin_allowed_integration():
    """Verifies Business.is_origin_allowed delegates cleanly to validate_business_origin."""
    biz = Business(
        name="Apex Clinic",
        slug=f"apex-{uuid.uuid4().hex[:8]}",
        allowed_origins=["https://apexclinic.pk", "https://booking.apexclinic.pk/"],
    )

    assert biz.is_origin_allowed("https://apexclinic.pk") is True
    assert biz.is_origin_allowed("https://apexclinic.pk/") is True
    assert biz.is_origin_allowed("HTTPS://APEXCLINIC.PK") is True
    assert biz.is_origin_allowed("https://booking.apexclinic.pk") is True

    # Denials
    assert biz.is_origin_allowed("https://evil-apexclinic.pk") is False
    assert biz.is_origin_allowed("https://apexclinic.pk.evil.com") is False
    assert biz.is_origin_allowed("") is False
    assert biz.is_origin_allowed(None) is False


# =====================================================================
# 3. FastAPI Dependencies Tests
# =====================================================================

def test_get_widget_token_dependency():
    """Verifies token extraction from X-Widget-Token, Authorization Bearer, and query params."""
    # 1. From X-Widget-Token
    req1 = MagicMock()
    req1.headers = {"X-Widget-Token": "token-from-header"}
    req1.query_params = {}
    assert get_widget_token(req1) == "token-from-header"

    # 2. From Authorization: Bearer
    req2 = MagicMock()
    req2.headers = {"Authorization": "Bearer token-from-bearer"}
    req2.query_params = {}
    assert get_widget_token(req2) == "token-from-bearer"

    # 3. From query params
    req3 = MagicMock()
    req3.headers = {}
    req3.query_params = {"widget_token": "token-from-query"}
    assert get_widget_token(req3) == "token-from-query"

    # 4. Missing token raises 401
    req4 = MagicMock()
    req4.headers = {}
    req4.query_params = {}
    with pytest.raises(HTTPException) as exc_info:
        get_widget_token(req4)
    assert exc_info.value.status_code == 401
    assert "Missing widget authentication token" in exc_info.value.detail


def test_get_widget_origin_dependency():
    """Verifies origin extraction from Origin and Referer headers."""
    # From Origin header
    req1 = MagicMock()
    req1.headers = {"Origin": "https://client-site.com/"}
    assert get_widget_origin(req1) == "https://client-site.com"

    # Fallback to Referer header
    req2 = MagicMock()
    req2.headers = {"Referer": "https://referer-site.com:8080/page"}
    assert get_widget_origin(req2) == "https://referer-site.com:8080"

    # Missing origin and referer returns None
    req3 = MagicMock()
    req3.headers = {}
    assert get_widget_origin(req3) is None


@pytest.mark.asyncio
async def test_get_verified_widget_business_success():
    """Verifies that get_verified_widget_business authorizes valid token and matching origin."""
    async with async_session_factory() as db:
        # Create active test business with allowed origin
        biz = Business(
            name="Authorized Widget Biz",
            slug=f"w-biz-{uuid.uuid4().hex[:8]}",
            is_active=True,
            allowed_origins=["https://widget-client.com"],
        )
        db.add(biz)
        await db.commit()
        await db.refresh(biz)

        # Generate valid token
        token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET)
        payload = verify_widget_token(token, secret=TEST_WIDGET_SECRET)

        # Mock request with matching origin
        req = MagicMock()
        req.headers = {"Origin": "https://widget-client.com"}

        authorized_biz = await get_verified_widget_business(
            request=req,
            payload=payload,
            db=db,
        )

        assert authorized_biz.id == biz.id
        assert authorized_biz.name == "Authorized Widget Biz"


@pytest.mark.asyncio
async def test_get_verified_widget_business_unauthorized_origin():
    """Verifies HTTP 403 Forbidden when origin does not match business allowed_origins."""
    async with async_session_factory() as db:
        biz = Business(
            name="Restricted Widget Biz",
            slug=f"r-biz-{uuid.uuid4().hex[:8]}",
            is_active=True,
            allowed_origins=["https://widget-client.com"],
        )
        db.add(biz)
        await db.commit()
        await db.refresh(biz)

        token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET)
        payload = verify_widget_token(token, secret=TEST_WIDGET_SECRET)

        # Mock request with untrusted origin
        req = MagicMock()
        req.headers = {"Origin": "https://malicious-site.com"}

        with pytest.raises(HTTPException) as exc_info:
            await get_verified_widget_business(
                request=req,
                payload=payload,
                db=db,
            )
        assert exc_info.value.status_code == 403
        assert "Origin is not authorized" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_verified_widget_business_inactive():
    """Verifies HTTP 404 Not Found when business exists but is inactive."""
    async with async_session_factory() as db:
        biz = Business(
            name="Inactive Widget Biz",
            slug=f"inact-biz-{uuid.uuid4().hex[:8]}",
            is_active=False,
            allowed_origins=["https://widget-client.com"],
        )
        db.add(biz)
        await db.commit()
        await db.refresh(biz)

        token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET)
        payload = verify_widget_token(token, secret=TEST_WIDGET_SECRET)

        req = MagicMock()
        req.headers = {"Origin": "https://widget-client.com"}

        with pytest.raises(HTTPException) as exc_info:
            await get_verified_widget_business(
                request=req,
                payload=payload,
                db=db,
            )
        assert exc_info.value.status_code == 404
        assert "Business not found or inactive" in exc_info.value.detail


# =====================================================================
# 4. Deep Security Audit Tests (Step 3A)
# =====================================================================

def _make_custom_token(header_dict, payload_dict, secret=TEST_WIDGET_SECRET):
    """Helper to craft custom signed tokens for testing malformed/tampered claims."""
    import base64
    import hashlib
    import hmac
    import json

    def b64_encode(d):
        raw = json.dumps(d, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    h_b64 = b64_encode(header_dict)
    p_b64 = b64_encode(payload_dict)
    sig = hmac.new(secret.encode("utf-8"), f"{h_b64}.{p_b64}".encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"{h_b64}.{p_b64}.{sig_b64}"


def test_rejection_of_wrong_jwt_algorithm():
    """Verifies that non-HS256 algorithms (none, RS256, HS384) are rejected."""
    biz_id = str(uuid.uuid4())
    now = int(datetime.now(timezone.utc).timestamp())
    valid_payload = {
        "sub": biz_id,
        "business_id": biz_id,
        "type": "widget",
        "iat": now,
        "exp": now + 900,
        "jti": "valid-jti-12345678",
    }

    # 1. alg: "none"
    token_none = _make_custom_token({"alg": "none", "typ": "JWT"}, valid_payload)
    with pytest.raises(WidgetTokenError, match="Only HS256 JWT tokens"):
        verify_widget_token(token_none, secret=TEST_WIDGET_SECRET)

    # 2. alg: "RS256"
    token_rs = _make_custom_token({"alg": "RS256", "typ": "JWT"}, valid_payload)
    with pytest.raises(WidgetTokenError, match="Only HS256 JWT tokens"):
        verify_widget_token(token_rs, secret=TEST_WIDGET_SECRET)

    # 3. alg: "HS384"
    token_hs384 = _make_custom_token({"alg": "HS384", "typ": "JWT"}, valid_payload)
    with pytest.raises(WidgetTokenError, match="Only HS256 JWT tokens"):
        verify_widget_token(token_hs384, secret=TEST_WIDGET_SECRET)


def test_rejection_of_modified_or_unsupported_header():
    """Verifies that unexpected header keys, invalid typ, or missing fields are rejected."""
    biz_id = str(uuid.uuid4())
    now = int(datetime.now(timezone.utc).timestamp())
    valid_payload = {
        "sub": biz_id,
        "business_id": biz_id,
        "type": "widget",
        "iat": now,
        "exp": now + 900,
        "jti": "valid-jti-12345678",
    }

    # Wrong typ
    t1 = _make_custom_token({"alg": "HS256", "typ": "NOT_JWT"}, valid_payload)
    with pytest.raises(WidgetTokenError, match="Only HS256 JWT tokens"):
        verify_widget_token(t1, secret=TEST_WIDGET_SECRET)

    # Extra header parameters (e.g. crit, jku)
    t2 = _make_custom_token({"alg": "HS256", "typ": "JWT", "crit": ["b64"]}, valid_payload)
    with pytest.raises(WidgetTokenError, match="Only HS256 JWT tokens"):
        verify_widget_token(t2, secret=TEST_WIDGET_SECRET)


def test_rejection_of_missing_required_claims():
    """Verifies that missing sub, business_id, jti, iat, or exp claims are rejected."""
    biz_id = str(uuid.uuid4())
    now = int(datetime.now(timezone.utc).timestamp())

    # Missing 'sub'
    p_no_sub = {"business_id": biz_id, "type": "widget", "iat": now, "exp": now + 900, "jti": "jti1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'sub'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_no_sub), secret=TEST_WIDGET_SECRET)

    # Missing 'business_id'
    p_no_biz = {"sub": biz_id, "type": "widget", "iat": now, "exp": now + 900, "jti": "jti1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'business_id'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_no_biz), secret=TEST_WIDGET_SECRET)

    # Missing 'jti'
    p_no_jti = {"sub": biz_id, "business_id": biz_id, "type": "widget", "iat": now, "exp": now + 900}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'jti'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_no_jti), secret=TEST_WIDGET_SECRET)

    # Missing 'iat'
    p_no_iat = {"sub": biz_id, "business_id": biz_id, "type": "widget", "exp": now + 900, "jti": "jti1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'iat'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_no_iat), secret=TEST_WIDGET_SECRET)

    # Missing 'exp'
    p_no_exp = {"sub": biz_id, "business_id": biz_id, "type": "widget", "iat": now, "jti": "jti1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'exp'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_no_exp), secret=TEST_WIDGET_SECRET)


def test_rejection_of_incorrect_claim_types():
    """Verifies that non-numeric or boolean iat/exp, non-string jti/sub/business_id are rejected."""
    biz_id = str(uuid.uuid4())
    now = int(datetime.now(timezone.utc).timestamp())

    # exp is boolean True (which is an int subclass in Python!)
    p_bool_exp = {"sub": biz_id, "business_id": biz_id, "type": "widget", "iat": now, "exp": True, "jti": "j1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'exp'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_bool_exp), secret=TEST_WIDGET_SECRET)

    # iat is string
    p_str_iat = {"sub": biz_id, "business_id": biz_id, "type": "widget", "iat": "not-a-number", "exp": now + 900, "jti": "j1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'iat'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_str_iat), secret=TEST_WIDGET_SECRET)

    # sub is int
    p_int_sub = {"sub": 12345, "business_id": biz_id, "type": "widget", "iat": now, "exp": now + 900, "jti": "j1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'sub'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_int_sub), secret=TEST_WIDGET_SECRET)

    # Conflicting sub and business_id
    p_conflict = {"sub": str(uuid.uuid4()), "business_id": str(uuid.uuid4()), "type": "widget", "iat": now, "exp": now + 900, "jti": "j1"}
    with pytest.raises(WidgetTokenError, match="Token claims conflict"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_conflict), secret=TEST_WIDGET_SECRET)


def test_rejection_of_invalid_business_uuid():
    """Verifies that an invalid business UUID string raises WidgetTokenError."""
    now = int(datetime.now(timezone.utc).timestamp())
    p_bad_uuid = {
        "sub": "not-a-valid-uuid-format",
        "business_id": "not-a-valid-uuid-format",
        "type": "widget",
        "iat": now,
        "exp": now + 900,
        "jti": "jti-12345",
    }
    with pytest.raises(WidgetTokenError, match="Invalid business UUID"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_bad_uuid), secret=TEST_WIDGET_SECRET)


def test_rejection_of_invalid_token_lifetime_and_negative_timestamps():
    """Verifies that exp <= iat or negative timestamps are rejected."""
    biz_id = str(uuid.uuid4())
    now = int(datetime.now(timezone.utc).timestamp())

    # exp <= iat
    p_exp_less = {"sub": biz_id, "business_id": biz_id, "type": "widget", "iat": now, "exp": now - 10, "jti": "j1"}
    with pytest.raises(WidgetTokenError, match="must be strictly greater than 'iat'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_exp_less), secret=TEST_WIDGET_SECRET)

    # Negative timestamp
    p_neg = {"sub": biz_id, "business_id": biz_id, "type": "widget", "iat": -100, "exp": now + 900, "jti": "j1"}
    with pytest.raises(WidgetTokenError, match="Missing or invalid 'iat'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_neg), secret=TEST_WIDGET_SECRET)


def test_rejection_of_wrong_token_type():
    """Verifies that token with type != 'widget' is rejected."""
    biz_id = str(uuid.uuid4())
    now = int(datetime.now(timezone.utc).timestamp())
    p_user = {"sub": biz_id, "business_id": biz_id, "type": "user_session", "iat": now, "exp": now + 900, "jti": "j1"}
    with pytest.raises(WidgetTokenError, match="expected 'widget'"):
        verify_widget_token(_make_custom_token({"alg": "HS256", "typ": "JWT"}, p_user), secret=TEST_WIDGET_SECRET)


def test_weak_signing_secret_entropy_enforcement():
    """Verifies that secrets shorter than 32 characters are rejected as weak."""
    biz_id = uuid.uuid4()
    with pytest.raises(WidgetTokenConfigurationError, match="too weak"):
        generate_widget_token(business_id=biz_id, secret="short-secret-16b")

    with pytest.raises(WidgetTokenConfigurationError, match="too weak"):
        verify_widget_token("token.segment.mock", secret="short-secret-16b")


def test_invalid_expiry_minutes_configuration():
    """Verifies that non-positive expire_minutes values raise configuration error."""
    biz_id = uuid.uuid4()
    with pytest.raises(WidgetTokenConfigurationError, match="positive integer"):
        generate_widget_token(business_id=biz_id, secret=TEST_WIDGET_SECRET, expire_minutes=0)

    with pytest.raises(WidgetTokenConfigurationError, match="positive integer"):
        generate_widget_token(business_id=biz_id, secret=TEST_WIDGET_SECRET, expire_minutes=-5)


def test_origin_port_error_handling_and_special_chars():
    """Verifies that malformed ports, backslashes, and special characters do not crash the parser."""
    assert normalize_origin("http://example.com:notanumber") is None
    assert normalize_origin("http://example.com:99999999999999999999999") is None
    assert normalize_origin("http://example.com\\evil.com") is None
    assert normalize_origin("http://example.com\x00") is None


def test_origin_bypass_with_referer_spoofing_prevented():
    """Verifies that when Origin is provided, Referer fallback CANNOT bypass origin validation."""
    # Request provides an unauthorized Origin AND an authorized Referer
    req = MagicMock()
    req.headers = {
        "Origin": "https://malicious-attacker.com",
        "Referer": "https://widget-client.com/allowed-page",
    }
    # get_widget_origin must return the Origin (not the Referer)
    assert get_widget_origin(req) == "https://malicious-attacker.com"

    # Request provides an invalid Origin header (empty or malformed) AND an authorized Referer
    req_malicious = MagicMock()
    req_malicious.headers = {
        "Origin": "",
        "Referer": "https://widget-client.com/allowed-page",
    }
    # Must return None (denied), never falling back to Referer
    assert get_widget_origin(req_malicious) is None


@pytest.mark.asyncio
async def test_get_verified_widget_business_nonexistent_business():
    """Verifies HTTP 404 when a validly signed token contains a nonexistent business UUID."""
    async with async_session_factory() as db:
        nonexistent_id = uuid.uuid4()
        token = generate_widget_token(business_id=nonexistent_id, secret=TEST_WIDGET_SECRET)
        payload = verify_widget_token(token, secret=TEST_WIDGET_SECRET)

        req = MagicMock()
        req.headers = {"Origin": "https://widget-client.com"}

        with pytest.raises(HTTPException) as exc_info:
            await get_verified_widget_business(request=req, payload=payload, db=db)
        assert exc_info.value.status_code == 404
        assert "Business not found or inactive" in exc_info.value.detail


def test_get_widget_token_case_insensitive_bearer_and_unsupported_scheme():
    """Verifies case-insensitive 'bearer <token>' and rejection of non-bearer schemes."""
    # Lowercase 'bearer '
    req1 = MagicMock()
    req1.headers = {"Authorization": "bearer my-valid-token"}
    req1.query_params = {}
    assert get_widget_token(req1) == "my-valid-token"

    # Mixed case 'Bearer '
    req2 = MagicMock()
    req2.headers = {"Authorization": "BEARER my-valid-token-2"}
    req2.query_params = {}
    assert get_widget_token(req2) == "my-valid-token-2"

    # Basic auth scheme rejected
    req3 = MagicMock()
    req3.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
    req3.query_params = {}
    with pytest.raises(HTTPException) as exc_info:
        get_widget_token(req3)
    assert exc_info.value.status_code == 401


def test_no_circular_dependencies():
    """Verifies that widget modules and dependencies can be cleanly imported."""
    import app.core.widget_auth
    import app.api.dependencies.widget
    import app.api.dependencies

    assert hasattr(app.core.widget_auth, "verify_widget_token")
    assert hasattr(app.api.dependencies.widget, "get_verified_widget_business")
    assert hasattr(app.api.dependencies, "get_verified_widget_business")
