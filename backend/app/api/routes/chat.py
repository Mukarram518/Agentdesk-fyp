"""AgentDesk Web Chat API Routes (Phase 7 - Step 5F).

Provides public chat endpoint for embeddable web chat widgets:
- POST /api/v1/chat/messages: Submits a chat message turn with verified widget token.

Security guarantees:
- Derives tenant identity strictly from verified widget authentication claims.
- Accepts tokens exclusively via headers (X-Widget-Token or Authorization: Bearer).
- Rejects tokens supplied in query parameters with HTTP 401.
- Enforces Origin header validation for POST requests with HTTP 403 (no Referer fallback).
- Rejects unauthorized origins with HTTP 403.
- Enforces turnkey request idempotency and distributed lock coordination via ChatService.
- Safe error mapping (404 for missing conversations, 503 for lock/Redis issues, 500 for unexpected).
- Zero leakage of internal prompts, RAG sources, provider metadata, or credentials.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.widget import get_verified_widget_business
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ServiceUnavailableError
from app.core.widget_auth import generate_widget_token
from app.models.business import Business
from app.models.business_member import MemberRole
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatPreviewTokenRequest,
    ChatPreviewTokenResponse,
)
from app.services.business_service import business_service
from app.services.chat_service import (
    ChatLeaseLostError,
    ChatLockTimeoutError,
    ChatService,
    chat_service,
    ConversationNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =====================================================================
# Strict Widget Security Dependency Composition
# =====================================================================

def enforce_widget_request_security(request: Request) -> None:
    """Enforces chat-specific widget transport and origin constraints.

    Guarantees:
    1. Rejects widget tokens supplied in query parameters with HTTP 401.
    2. Requires widget tokens strictly via approved request headers:
       - Primary: X-Widget-Token: <token>
       - Secondary: Authorization: Bearer <token>
    3. Requires explicit, non-empty Origin header on POST requests with HTTP 403 (no Referer fallback).
    """
    # 1. Reject tokens in query parameters
    if "widget_token" in request.query_params:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Widget token in query parameter is not allowed. Tokens must be sent via headers.",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    # 2. Enforce token from approved headers only (reject if missing from headers)
    header_token = request.headers.get("X-Widget-Token")
    if not (header_token and header_token.strip()):
        auth_header = request.headers.get("Authorization", "").strip()
        parts = auth_header.split(None, 1)
        if not (len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing widget authentication token in request headers.",
                headers={"WWW-Authenticate": 'Bearer error="missing_token"'},
            )

    # 3. Require explicit, non-empty Origin header (disallow Referer fallback)
    origin = request.headers.get("Origin")
    if not origin or not origin.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid request origin header.",
        )


async def get_chat_widget_business(
    _: None = Depends(enforce_widget_request_security),
    business: Business = Depends(get_verified_widget_business),
) -> Business:
    """Authenticates and authorizes the Business tenant for web chat turns.

    Composes:
    - enforce_widget_request_security: Rejects query-string tokens and enforces Origin header.
    - get_verified_widget_business: Validates cryptographic JWT claims, resolves the active
      business tenant, and authorizes the origin against allowed_origins.
    """
    return business


# =====================================================================
# Preview Token Endpoint
# =====================================================================

@router.post(
    "/preview-token",
    response_model=ChatPreviewTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Issue short-lived widget preview token for dashboard chat preview",
)
async def create_preview_token(
    payload: Optional[ChatPreviewTokenRequest] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatPreviewTokenResponse:
    """Issues a short-lived widget preview token for authenticated business owners and admins.

    Security Guarantees:
    - Authenticates strictly via user session (get_current_user).
    - Resolves business and membership via business_service.get_current_user_business().
    - Never trusts payload.business_id: verifies caller is an active member with owner/admin role.
    - Rejects regular 'member' role with HTTP 403.
    - Generates signed HMAC token with is_preview=True and short expiration.
    - Never logs or exposes the signing secret or complete raw token.
    """
    target_business_id = payload.business_id if payload else None

    # Resolve business and membership using existing business_service
    result = await business_service.get_current_user_business(
        db=db,
        user_id=user.id,
        business_id=target_business_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found or access denied.",
        )

    business, membership = result

    # Check authorized roles: owner and admin only (reject regular members)
    if membership.role not in (MemberRole.OWNER.value, MemberRole.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners and admins are authorized to obtain preview tokens.",
        )

    # Calculate expiration and issue preview token
    settings = get_settings()
    validity_minutes = settings.WIDGET_TOKEN_EXPIRE_MINUTES or 15
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=validity_minutes)

    token = generate_widget_token(
        business_id=business.id,
        expire_minutes=validity_minutes,
        issued_at=now,
        is_preview=True,
    )

    logger.info(
        f"Issued chat preview token for business_id={business.id} "
        f"to user_id={user.id} role={membership.role}"
    )

    return ChatPreviewTokenResponse(
        token=token,
        expires_at=expires_at,
    )


# =====================================================================
# Chat Endpoint
# =====================================================================

@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a chat message turn via web chat widget",
)
async def send_chat_message(
    payload: ChatMessageRequest,
    business: Business = Depends(get_chat_widget_business),
    db: AsyncSession = Depends(get_db),
    service: ChatService = Depends(lambda: chat_service),
) -> ChatMessageResponse:
    """Processes a conversational chat turn for an authenticated web chat widget.

    Coordinates:
    - Distributed locking per (business_id, request_id)
    - Conversation creation or thread ownership validation
    - Idempotent user message persistence (Transaction 1)
    - Multi-agent AI Orchestration (non-transactional inference)
    - Lease-loss verification
    - Idempotent assistant reply persistence (Transaction 2)
    - Sanitized ChatMessageResponse matching documented public contract
    """
    try:
        response = await service.handle_chat_turn(
            db=db,
            business_id=business.id,
            request=payload,
            business=business,
        )
        return response
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc.message or "Conversation not found or access denied."),
        ) from exc
    except (ChatLockTimeoutError, ChatLeaseLostError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc.message or "Chat coordination temporarily unavailable. Please retry shortly."),
            headers={"Retry-After": "2"},
        ) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service temporarily unavailable. Please retry shortly.",
            headers={"Retry-After": "5"},
        ) from exc
    except HTTPException:
        # Re-raise explicit HTTP exceptions without alteration
        raise
    except Exception as exc:
        logger.error(
            f"Unexpected error processing chat turn for business={business.id}: {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your chat request.",
        ) from exc
