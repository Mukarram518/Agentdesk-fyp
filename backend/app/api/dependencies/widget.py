"""Widget authentication and origin verification dependencies for public chat endpoints."""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.widget_auth import (
    WidgetTokenConfigurationError,
    WidgetTokenError,
    WidgetTokenExpiredError,
    WidgetTokenInvalidSignatureError,
    WidgetTokenPayload,
    normalize_origin,
    verify_widget_token,
)
from app.models.business import Business
from app.repositories.business_repository import business_repository


def get_widget_token(request: Request) -> str:
    """Extracts widget token from X-Widget-Token header, Bearer Authorization, or query param.

    Raises:
        HTTPException 401: If no widget token is present in the request.
    """
    # 1. Primary: Dedicated X-Widget-Token header
    token = request.headers.get("X-Widget-Token")
    if token and token.strip():
        return token.strip()

    # 2. Secondary: Authorization: Bearer <token> (case-insensitive scheme)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.strip():
        parts = auth_header.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            bearer_token = parts[1].strip()
            if bearer_token:
                return bearer_token

    # 3. Tertiary fallback: query param (useful for WebSocket handshake or iframe transport)
    query_token = request.query_params.get("widget_token")
    if query_token and query_token.strip():
        return query_token.strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing widget authentication token.",
        headers={"WWW-Authenticate": "Bearer error=\"missing_token\""},
    )


def get_widget_origin(request: Request) -> Optional[str]:
    """Extracts and normalizes the request origin from Origin or Referer header.

    Security rules:
    - If the Origin header is present in the request, it MUST be valid. Never fall back
      to Referer if Origin was supplied, preventing spoofed Referer bypass attacks.
    - Only fall back to Referer when the Origin header is completely absent from the request.
    """
    if "Origin" in request.headers:
        origin_header = request.headers.get("Origin")
        if not origin_header or not origin_header.strip():
            return None
        return normalize_origin(origin_header)

    referer_header = request.headers.get("Referer")
    if referer_header and referer_header.strip():
        try:
            from urllib.parse import urlsplit

            parsed = urlsplit(referer_header.strip())
            if parsed.scheme and parsed.netloc:
                origin_from_referer = f"{parsed.scheme}://{parsed.netloc}"
                return normalize_origin(origin_from_referer)
        except Exception:
            pass

    return None


async def get_verified_widget_payload(
    token: str = Depends(get_widget_token),
) -> WidgetTokenPayload:
    """Verifies the widget token signature and expiration, returning verified claims.

    Guarantees:
    - Verifies HMAC-SHA256 signature against WIDGET_TOKEN_SECRET.
    - Verifies token has not expired and was not issued in the future.
    - Derives business_id strictly from the cryptographic token claims.
    """
    try:
        return verify_widget_token(token)
    except WidgetTokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Widget token has expired.",
            headers={"WWW-Authenticate": "Bearer error=\"token_expired\""},
        ) from e
    except WidgetTokenInvalidSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid widget token signature.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from e
    except WidgetTokenConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Widget authentication is misconfigured on the server.",
        ) from e
    except WidgetTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed or invalid widget token.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from e


def verify_business_origin(
    candidate_origin: Optional[str],
    business: Business,
    is_preview: bool = False,
) -> None:
    """Verifies that the candidate origin is explicitly permitted for the business or preview.

    Raises:
        HTTPException 403: If origin is missing, malformed, or unauthorized.
    """
    if not candidate_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid request origin header.",
        )

    if is_preview:
        from app.core.widget_auth import validate_preview_origin

        if not validate_preview_origin(candidate_origin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin is not authorized for preview.",
            )
    else:
        if not business.is_origin_allowed(candidate_origin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin is not authorized for this business.",
            )


async def get_verified_widget_business(
    request: Request,
    payload: WidgetTokenPayload = Depends(get_verified_widget_payload),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Resolves and authorizes the Business tenant for a widget request.

    Security guarantees:
    - Resolves business strictly from the verified token's business_id claim.
    - Verifies the business exists and is active.
    - Enforces origin validation against the business's allowed_origins (or trusted dashboard origins if preview).
    - Never trusts an unverified client-supplied business ID.
    """
    business = await business_repository.get_by_id(
        db=db,
        business_id=payload.business_id,
        only_active=True,
    )
    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found or inactive.",
        )

    candidate_origin = get_widget_origin(request)
    verify_business_origin(candidate_origin, business, is_preview=payload.is_preview)

    return business
