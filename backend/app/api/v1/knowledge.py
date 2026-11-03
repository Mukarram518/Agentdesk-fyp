"""Knowledge Base API routes for AgentDesk FAQ management, updates, and semantic search."""

from typing import List, Optional, Tuple
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.business import (
    get_current_business_membership,
    require_business_owner,
)
from app.core.database import get_db
from app.models.business import Business
from app.models.business_member import BusinessMember
from app.schemas.knowledge import (
    FAQCreate,
    FAQUpdate,
    FAQResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResultItem,
    KnowledgeSearchResponse,
)
from app.services.knowledge_service import knowledge_service

router = APIRouter()


@router.post(
    "",
    response_model=FAQResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new FAQ entry",
)
async def create_faq(
    payload: FAQCreate,
    business_and_member: Tuple[Business, BusinessMember] = Depends(require_business_owner),
    db: AsyncSession = Depends(get_db),
) -> FAQResponse:
    """Creates a new FAQ entry for the authenticated business.

    Guarantees:
    - Restricted to the business owner only (403 for non-owners).
    - Derives business_id strictly from the authenticated business context.
    - Generates 384-dimensional vector embedding from the answer text.
    - Gracefully saves with embedding=None and embedding_stale=True if provider fails.
    - Never exposes raw embedding vectors in the response.
    """
    business, _ = business_and_member

    try:
        entry = await knowledge_service.create_faq(
            db=db,
            business_id=business.id,
            question=payload.question,
            answer=payload.answer,
            tags=payload.tags,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return FAQResponse.from_orm_entry(entry)


@router.get(
    "",
    response_model=List[FAQResponse],
    status_code=status.HTTP_200_OK,
    summary="List FAQ entries for current business",
)
async def list_faqs(
    language: Optional[str] = Query(None, description="Filter by language ('en', 'ur', 'mixed')"),
    limit: int = Query(50, ge=1, le=100, description="Max entries to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
    business_and_member: Tuple[Business, BusinessMember] = Depends(get_current_business_membership),
    db: AsyncSession = Depends(get_db),
) -> List[FAQResponse]:
    """Retrieves paginated FAQ entries for the authenticated business.

    Guarantees:
    - Accessible to all active business members.
    - Strictly scoped to the authenticated tenant (never returns other businesses' FAQs).
    - Ordered by newest first.
    """
    business, _ = business_and_member

    try:
        entries = await knowledge_service.list_faqs(
            db=db,
            business_id=business.id,
            language=language,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return [FAQResponse.from_orm_entry(e) for e in entries]


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search across business knowledge",
)
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    business_and_member: Tuple[Business, BusinessMember] = Depends(get_current_business_membership),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSearchResponse:
    """Performs tenant-scoped semantic vector search using pgvector cosine distance.

    Guarantees:
    - Accessible to all active business members.
    - Registered BEFORE /{knowledge_id} to prevent path conflict.
    - Generates query embedding and searches strictly within the authenticated business.
    - Excludes entries where embedding is NULL or embedding_stale is True.
    - Returns results ordered by cosine distance ascending (0.0 = identical; lower is closer).
    """
    business, _ = business_and_member

    try:
        search_results = await knowledge_service.search_knowledge(
            db=db,
            business_id=business.id,
            query=payload.query,
            top_k=payload.top_k,
            score_threshold=payload.score_threshold,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    items = [
        KnowledgeSearchResultItem(
            entry=FAQResponse.from_orm_entry(entry),
            score=round(distance, 6),
            score_metric="cosine_distance",
        )
        for entry, distance in search_results
    ]

    return KnowledgeSearchResponse(
        query=payload.query,
        results=items,
        total_results=len(items),
    )


@router.get(
    "/{knowledge_id}",
    response_model=FAQResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single FAQ entry by ID",
)
async def get_faq(
    knowledge_id: uuid.UUID,
    business_and_member: Tuple[Business, BusinessMember] = Depends(get_current_business_membership),
    db: AsyncSession = Depends(get_db),
) -> FAQResponse:
    """Retrieves an FAQ entry by UUID for the authenticated business.

    Security Guarantees:
    - Accessible to all active business members.
    - Returns 404 if the entry does not exist or belongs to another business.
    - Never leaks existence of other tenants' records.
    """
    business, _ = business_and_member

    entry = await knowledge_service.get_faq(
        db=db,
        business_id=business.id,
        entry_id=knowledge_id,
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found.",
        )

    return FAQResponse.from_orm_entry(entry)


@router.patch(
    "/{knowledge_id}",
    response_model=FAQResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an existing FAQ entry",
)
async def update_faq(
    knowledge_id: uuid.UUID,
    payload: FAQUpdate,
    business_and_member: Tuple[Business, BusinessMember] = Depends(require_business_owner),
    db: AsyncSession = Depends(get_db),
) -> FAQResponse:
    """Updates FAQ fields for the authenticated business.

    Guarantees:
    - Restricted to the business owner only (403 for non-owners).
    - If question or answer text changes, regenerates vector embedding from the target answer.
    - If embedding fails, persists updated content and marks embedding_stale=True.
    - If only tags or language change, preserves existing embedding without re-encoding.
    - Returns 404 if entry does not exist or belongs to another business.
    """
    business, _ = business_and_member

    update_kwargs = {}
    if payload.question is not None or "question" in payload.model_fields_set:
        update_kwargs["question"] = payload.question
    if payload.answer is not None:
        update_kwargs["answer"] = payload.answer
    if payload.tags is not None:
        update_kwargs["tags"] = payload.tags
    if payload.language is not None:
        update_kwargs["language"] = payload.language

    try:
        entry = await knowledge_service.update_faq(
            db=db,
            business_id=business.id,
            entry_id=knowledge_id,
            **update_kwargs,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found.",
        )

    return FAQResponse.from_orm_entry(entry)


@router.delete(
    "/{knowledge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an FAQ entry",
)
async def delete_faq(
    knowledge_id: uuid.UUID,
    business_and_member: Tuple[Business, BusinessMember] = Depends(require_business_owner),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Deletes an FAQ entry strictly within the authenticated business scope.

    Guarantees:
    - Restricted to the business owner only (403 for non-owners).
    - Returns HTTP 204 No Content with an empty response body on success.
    - Returns 404 if entry does not exist or belongs to another business.
    """
    business, _ = business_and_member

    deleted = await knowledge_service.delete_faq(
        db=db,
        business_id=business.id,
        entry_id=knowledge_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)

