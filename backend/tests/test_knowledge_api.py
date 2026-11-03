"""API Integration tests for AgentDesk Knowledge Base Endpoints (Phase 5.3).

Tests:
1. Authentication verification for every endpoint (401).
2. Owner vs non-owner permissions (403 for non-owner mutations; 200 for reads).
3. FAQ creation with full payload and answer-only payload (201).
4. Validation errors: empty answer, blank strings, invalid language, invalid tags (422).
5. Listing, pagination (limit, offset), and language filtering (200).
6. Single-entry retrieval (200 and 404).
7. Cross-tenant GET, PATCH, and DELETE attempts (404 isolation).
8. Content updates regenerating embeddings (200).
9. Metadata-only updates preserving embeddings without regeneration (200).
10. Successful deletion returning empty HTTP 204 No Content.
11. Semantic vector search and cosine distance representation (200).
12. Semantic search tenant isolation (never returns other businesses' entries).
13. Path and parameter validation: invalid UUIDs and invalid top_k (422).
14. Vector array privacy: no raw embedding array in any API response.
15. Route ordering: /search resolves without UUID path conflict.
"""

import uuid
from typing import Tuple
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.knowledge import KnowledgeBaseEntry

settings = get_settings()


async def create_authenticated_user(
    async_client: AsyncClient, name: str = "Test User"
) -> Tuple[dict, str]:
    """Registers, logs in, and returns (user_data, session_token)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"

    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": name},
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()["user"]

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    session_token = login_res.cookies[settings.SESSION_COOKIE_NAME]
    async_client.cookies.clear()

    return user_data, session_token


async def create_owner_with_business(
    async_client: AsyncClient, biz_name: str = "Knowledge Test Biz"
) -> Tuple[dict, str, dict]:
    """Creates an authenticated user and onboards a new business as owner."""
    user, token = await create_authenticated_user(async_client, name="Owner User")
    biz_res = await async_client.post(
        "/api/v1/businesses",
        json={"name": f"{biz_name} {uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert biz_res.status_code == 201
    business_data = biz_res.json()
    return user, token, business_data


async def add_member_to_business(
    business_id: uuid.UUID, user_id: uuid.UUID, role: str = MemberRole.MEMBER.value
) -> None:
    """Directly adds a user as a member to an existing business in the database."""
    async with async_session_factory() as db:
        member = BusinessMember(
            business_id=business_id,
            user_id=user_id,
            role=role,
        )
        db.add(member)
        await db.commit()


# ============================================================================
# 1. Authentication Tests (401)
# ============================================================================

@pytest.mark.asyncio
async def test_knowledge_endpoints_require_authentication(async_client: AsyncClient):
    """Verifies that all knowledge endpoints reject unauthenticated requests with 401."""
    random_id = uuid.uuid4()

    # POST /api/v1/knowledge
    res = await async_client.post("/api/v1/knowledge", json={"answer": "Test answer"})
    assert res.status_code == 401

    # GET /api/v1/knowledge
    res = await async_client.get("/api/v1/knowledge")
    assert res.status_code == 401

    # GET /api/v1/knowledge/{id}
    res = await async_client.get(f"/api/v1/knowledge/{random_id}")
    assert res.status_code == 401

    # PATCH /api/v1/knowledge/{id}
    res = await async_client.patch(f"/api/v1/knowledge/{random_id}", json={"answer": "New answer"})
    assert res.status_code == 401

    # DELETE /api/v1/knowledge/{id}
    res = await async_client.delete(f"/api/v1/knowledge/{random_id}")
    assert res.status_code == 401

    # POST /api/v1/knowledge/search
    res = await async_client.post("/api/v1/knowledge/search", json={"query": "test query"})
    assert res.status_code == 401


# ============================================================================
# 2. Owner vs Non-Owner Permissions (403 vs 200)
# ============================================================================

@pytest.mark.asyncio
async def test_owner_and_non_owner_permissions(async_client: AsyncClient):
    """Verifies owner can mutate, whereas non-owner member can only read (403 on mutations)."""
    # 1. Create owner and business
    owner_user, owner_token, biz = await create_owner_with_business(async_client, "Perms Biz")
    biz_id = uuid.UUID(biz["id"])

    # 2. Owner creates an FAQ
    create_res = await async_client.post(
        "/api/v1/knowledge",
        json={"question": "Doctor's schedule?", "answer": "Available Monday to Thursday."},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_res.status_code == 201
    faq_data = create_res.json()
    faq_id = faq_data["id"]

    # 3. Create a second user and attach as non-owner 'member'
    member_user, member_token = await create_authenticated_user(async_client, name="Staff Member")
    await add_member_to_business(business_id=biz_id, user_id=uuid.UUID(member_user["id"]), role=MemberRole.MEMBER.value)

    member_headers = {"Authorization": f"Bearer {member_token}"}

    # 4. Member reads FAQ -> 200 OK
    get_res = await async_client.get(f"/api/v1/knowledge/{faq_id}", headers=member_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == faq_id

    # 5. Member lists FAQs -> 200 OK
    list_res = await async_client.get("/api/v1/knowledge", headers=member_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 6. Member searches FAQs -> 200 OK
    search_res = await async_client.post(
        "/api/v1/knowledge/search",
        json={"query": "doctor schedule timing"},
        headers=member_headers,
    )
    assert search_res.status_code == 200

    # 7. Member attempts POST (create) -> 403 Forbidden
    post_res = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Unauthorized FAQ creation"},
        headers=member_headers,
    )
    assert post_res.status_code == 403
    assert "Only the business owner is authorized" in post_res.json()["detail"]

    # 8. Member attempts PATCH -> 403 Forbidden
    patch_res = await async_client.patch(
        f"/api/v1/knowledge/{faq_id}",
        json={"answer": "Unauthorized update"},
        headers=member_headers,
    )
    assert patch_res.status_code == 403

    # 9. Member attempts DELETE -> 403 Forbidden
    del_res = await async_client.delete(f"/api/v1/knowledge/{faq_id}", headers=member_headers)
    assert del_res.status_code == 403


# ============================================================================
# 3. FAQ Creation (Full Payload & Answer-Only)
# ============================================================================

@pytest.mark.asyncio
async def test_create_faq_success_and_answer_only(async_client: AsyncClient):
    """Verifies FAQ creation with full payload and answer-only payload."""
    _, token, _ = await create_owner_with_business(async_client, "Creation Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Full payload with question, answer, tags, language
    full_res = await async_client.post(
        "/api/v1/knowledge",
        json={
            "question": "What payment methods do you accept?",
            "answer": "We accept cash, credit cards, and bank transfers.",
            "tags": ["payment", "billing"],
            "language": "en",
        },
        headers=headers,
    )
    assert full_res.status_code == 201
    data = full_res.json()
    assert data["question"] == "What payment methods do you accept?"
    assert data["answer"] == "We accept cash, credit cards, and bank transfers."
    assert data["tags"] == ["payment", "billing"]
    assert data["language"] == "en"
    assert data["source_type"] == "FAQ"
    assert data["has_embedding"] is True
    assert data["embedding_stale"] is False
    assert "embedding" not in data  # Never expose raw vectors

    # 2. Answer-only payload (question omitted)
    answer_only_res = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Patients should arrive 10 minutes prior to scheduled appointment."},
        headers=headers,
    )
    assert answer_only_res.status_code == 201
    ao_data = answer_only_res.json()
    assert ao_data["question"] is None
    assert ao_data["answer"] == "Patients should arrive 10 minutes prior to scheduled appointment."
    assert ao_data["has_embedding"] is True
    assert ao_data["embedding_stale"] is False


# ============================================================================
# 4. Input Validation Errors (422)
# ============================================================================

@pytest.mark.asyncio
async def test_create_faq_validation_errors(async_client: AsyncClient):
    """Verifies that invalid payloads trigger 422 Unprocessable Entity."""
    _, token, _ = await create_owner_with_business(async_client, "Validation Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Empty answer
    res = await async_client.post("/api/v1/knowledge", json={"answer": ""}, headers=headers)
    assert res.status_code == 422

    # Whitespace-only answer
    res = await async_client.post("/api/v1/knowledge", json={"answer": "     "}, headers=headers)
    assert res.status_code == 422

    # Missing answer field
    res = await async_client.post("/api/v1/knowledge", json={"question": "Only Question?"}, headers=headers)
    assert res.status_code == 422

    # Unsupported language
    res = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Valid answer", "language": "german"},
        headers=headers,
    )
    assert res.status_code == 422

    # Tags not a list
    res = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Valid answer", "tags": "invalid-tags-string"},
        headers=headers,
    )
    assert res.status_code == 422


# ============================================================================
# 5. Listing, Pagination, and Language Filtering
# ============================================================================

@pytest.mark.asyncio
async def test_list_faqs_pagination_and_language_filter(async_client: AsyncClient):
    """Verifies listing FAQs with pagination (limit, offset) and language filter."""
    _, token, _ = await create_owner_with_business(async_client, "List Filter Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Create 3 English FAQs and 2 Urdu FAQs
    for i in range(3):
        await async_client.post(
            "/api/v1/knowledge",
            json={"answer": f"English Clinic Policy {i}", "language": "en"},
            headers=headers,
        )

    for i in range(2):
        await async_client.post(
            "/api/v1/knowledge",
            json={"answer": f"کلینک پالیسی {i}", "language": "ur"},
            headers=headers,
        )

    # 1. Pagination: limit 2, offset 0
    p1_res = await async_client.get("/api/v1/knowledge?limit=2&offset=0", headers=headers)
    assert p1_res.status_code == 200
    p1 = p1_res.json()
    assert len(p1) == 2

    # 2. Pagination: limit 2, offset 2
    p2_res = await async_client.get("/api/v1/knowledge?limit=2&offset=2", headers=headers)
    assert p2_res.status_code == 200
    p2 = p2_res.json()
    assert len(p2) == 2
    assert p1[0]["id"] != p2[0]["id"]

    # 3. Filter by Urdu
    ur_res = await async_client.get("/api/v1/knowledge?language=ur", headers=headers)
    assert ur_res.status_code == 200
    ur_list = ur_res.json()
    assert len(ur_list) == 2
    assert all(item["language"] == "ur" for item in ur_list)

    # 4. Filter by English
    en_res = await async_client.get("/api/v1/knowledge?language=en", headers=headers)
    assert en_res.status_code == 200
    en_list = en_res.json()
    assert len(en_list) == 3
    assert all(item["language"] == "en" for item in en_list)


# ============================================================================
# 6. Single-Entry Retrieval (200 & 404)
# ============================================================================

@pytest.mark.asyncio
async def test_get_single_faq(async_client: AsyncClient):
    """Verifies single FAQ retrieval and nonexistent 404 handling."""
    _, token, _ = await create_owner_with_business(async_client, "Get Single Biz")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await async_client.post(
        "/api/v1/knowledge",
        json={"question": "Emergency contact?", "answer": "Call 911 for emergencies."},
        headers=headers,
    )
    faq_id = create_res.json()["id"]

    # Valid get -> 200
    get_res = await async_client.get(f"/api/v1/knowledge/{faq_id}", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == faq_id
    assert data["question"] == "Emergency contact?"
    assert data["has_embedding"] is True

    # Nonexistent UUID -> 404
    non_existent = uuid.uuid4()
    not_found_res = await async_client.get(f"/api/v1/knowledge/{non_existent}", headers=headers)
    assert not_found_res.status_code == 404
    assert not_found_res.json()["detail"] == "Knowledge entry not found."


# ============================================================================
# 7. Cross-Tenant Isolation (404 on GET, PATCH, DELETE)
# ============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_isolation(async_client: AsyncClient):
    """Verifies that Business B cannot read, update, or delete Business A's FAQ (404)."""
    # Business A creates FAQ
    _, token_a, _ = await create_owner_with_business(async_client, "Tenant Alpha")
    create_res = await async_client.post(
        "/api/v1/knowledge",
        json={"question": "Alpha Secret Q", "answer": "Alpha Confidential Answer"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    faq_a_id = create_res.json()["id"]

    # Business B attempts operations
    _, token_b, _ = await create_owner_with_business(async_client, "Tenant Beta")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Cross-tenant GET -> 404
    cross_get = await async_client.get(f"/api/v1/knowledge/{faq_a_id}", headers=headers_b)
    assert cross_get.status_code == 404

    # Cross-tenant PATCH -> 404
    cross_patch = await async_client.patch(
        f"/api/v1/knowledge/{faq_a_id}",
        json={"answer": "Hacked Answer!"},
        headers=headers_b,
    )
    assert cross_patch.status_code == 404

    # Cross-tenant DELETE -> 404
    cross_del = await async_client.delete(f"/api/v1/knowledge/{faq_a_id}", headers=headers_b)
    assert cross_del.status_code == 404

    # Verify Business A record remains untouched
    verify_res = await async_client.get(
        f"/api/v1/knowledge/{faq_a_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["answer"] == "Alpha Confidential Answer"


# ============================================================================
# 8. Content Updates and Embedding Regeneration
# ============================================================================

@pytest.mark.asyncio
async def test_update_faq_content_and_embedding(async_client: AsyncClient):
    """Verifies content update regenerates embedding while keeping status valid."""
    _, token, _ = await create_owner_with_business(async_client, "Update Biz")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await async_client.post(
        "/api/v1/knowledge",
        json={"question": "Initial Q", "answer": "Initial Answer 100."},
        headers=headers,
    )
    faq_id = create_res.json()["id"]

    # Update answer
    patch_res = await async_client.patch(
        f"/api/v1/knowledge/{faq_id}",
        json={"answer": "Revised Answer 200."},
        headers=headers,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["answer"] == "Revised Answer 200."
    assert data["has_embedding"] is True
    assert data["embedding_stale"] is False

    # Update question
    patch_q_res = await async_client.patch(
        f"/api/v1/knowledge/{faq_id}",
        json={"question": "Updated Q Title?"},
        headers=headers,
    )
    assert patch_q_res.status_code == 200
    q_data = patch_q_res.json()
    assert q_data["question"] == "Updated Q Title?"
    assert q_data["has_embedding"] is True
    assert q_data["embedding_stale"] is False


# ============================================================================
# 9. Metadata-Only Updates
# ============================================================================

@pytest.mark.asyncio
async def test_update_faq_metadata_only(async_client: AsyncClient):
    """Verifies updating only tags or language preserves embedding state."""
    _, token, _ = await create_owner_with_business(async_client, "Meta Update Biz")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Constant answer text.", "tags": ["tag1"], "language": "en"},
        headers=headers,
    )
    faq_id = create_res.json()["id"]

    # Update only tags and language
    patch_res = await async_client.patch(
        f"/api/v1/knowledge/{faq_id}",
        json={"tags": ["tag1", "tag2", "updated"], "language": "mixed"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["answer"] == "Constant answer text."
    assert data["tags"] == ["tag1", "tag2", "updated"]
    assert data["language"] == "mixed"
    assert data["has_embedding"] is True
    assert data["embedding_stale"] is False


# ============================================================================
# 10. Deletion with Empty 204 Response
# ============================================================================

@pytest.mark.asyncio
async def test_delete_faq_success(async_client: AsyncClient):
    """Verifies successful deletion returns HTTP 204 No Content with empty body."""
    _, token, _ = await create_owner_with_business(async_client, "Delete Biz")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Temporary FAQ to be deleted."},
        headers=headers,
    )
    faq_id = create_res.json()["id"]

    # Delete
    del_res = await async_client.delete(f"/api/v1/knowledge/{faq_id}", headers=headers)
    assert del_res.status_code == 204
    assert del_res.content == b""  # Empty response body

    # Subsequent GET returns 404
    get_res = await async_client.get(f"/api/v1/knowledge/{faq_id}", headers=headers)
    assert get_res.status_code == 404


# ============================================================================
# 11. Semantic Vector Search and Score Representation
# ============================================================================

@pytest.mark.asyncio
async def test_semantic_search_success(async_client: AsyncClient):
    """Verifies semantic search returns matching entries with documented cosine distance score."""
    _, token, _ = await create_owner_with_business(async_client, "Search Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Seed FAQs
    await async_client.post(
        "/api/v1/knowledge",
        json={"question": "Consultation fees?", "answer": "General dental checkup is 50 dollars."},
        headers=headers,
    )
    await async_client.post(
        "/api/v1/knowledge",
        json={"question": "Location?", "answer": "Located at 100 Main Street Downtown."},
        headers=headers,
    )

    search_res = await async_client.post(
        "/api/v1/knowledge/search",
        json={"query": "how much does checkup cost", "top_k": 3},
        headers=headers,
    )
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["query"] == "how much does checkup cost"
    assert data["total_results"] >= 1
    assert len(data["results"]) >= 1

    top_result = data["results"][0]
    assert "entry" in top_result
    assert "score" in top_result
    assert top_result["score_metric"] == "cosine_distance"
    assert isinstance(top_result["score"], float)
    assert "embedding" not in top_result["entry"]


# ============================================================================
# 12. Search Tenant Isolation
# ============================================================================

@pytest.mark.asyncio
async def test_search_tenant_isolation(async_client: AsyncClient):
    """Verifies that vector search strictly isolates results to the authenticated tenant."""
    # Tenant Alpha
    _, token_a, _ = await create_owner_with_business(async_client, "Search Tenant A")
    res_a = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Tenant Alpha specializes in dental implants and root canals."},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    faq_a_id = res_a.json()["id"]

    # Tenant Beta
    _, token_b, _ = await create_owner_with_business(async_client, "Search Tenant B")
    res_b = await async_client.post(
        "/api/v1/knowledge",
        json={"answer": "Tenant Beta specializes in orthodontic braces and aligners."},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    faq_b_id = res_b.json()["id"]

    # Tenant Alpha searches
    search_a = await async_client.post(
        "/api/v1/knowledge/search",
        json={"query": "implants and orthodontic aligners", "top_k": 10},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert search_a.status_code == 200
    results_a = search_a.json()["results"]
    result_ids_a = [r["entry"]["id"] for r in results_a]

    assert faq_a_id in result_ids_a
    assert faq_b_id not in result_ids_a  # Cross-tenant entry NEVER appears


# ============================================================================
# 13. Path & Parameter Validation (422)
# ============================================================================

@pytest.mark.asyncio
async def test_invalid_path_and_search_params(async_client: AsyncClient):
    """Verifies invalid UUID path parameters and invalid search top_k values return 422."""
    _, token, _ = await create_owner_with_business(async_client, "Params Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Invalid UUID in GET
    res = await async_client.get("/api/v1/knowledge/not-a-valid-uuid", headers=headers)
    assert res.status_code == 422

    # Invalid UUID in PATCH
    res = await async_client.patch(
        "/api/v1/knowledge/not-a-valid-uuid", json={"answer": "test"}, headers=headers
    )
    assert res.status_code == 422

    # Invalid UUID in DELETE
    res = await async_client.delete("/api/v1/knowledge/not-a-valid-uuid", headers=headers)
    assert res.status_code == 422

    # Search: top_k < 1
    res = await async_client.post(
        "/api/v1/knowledge/search", json={"query": "valid query", "top_k": 0}, headers=headers
    )
    assert res.status_code == 422

    # Search: top_k > 100
    res = await async_client.post(
        "/api/v1/knowledge/search", json={"query": "valid query", "top_k": 150}, headers=headers
    )
    assert res.status_code == 422

    # Search: empty query
    res = await async_client.post(
        "/api/v1/knowledge/search", json={"query": "   ", "top_k": 5}, headers=headers
    )
    assert res.status_code == 422


# ============================================================================
# 14. Vector Array Privacy
# ============================================================================

@pytest.mark.asyncio
async def test_no_raw_embedding_vector_in_any_response(async_client: AsyncClient):
    """Verifies that raw 384-dimensional vector float arrays are never exposed over HTTP."""
    _, token, _ = await create_owner_with_business(async_client, "Privacy Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    c_res = await async_client.post(
        "/api/v1/knowledge",
        json={"question": "Privacy test?", "answer": "Check embedding array absence."},
        headers=headers,
    )
    c_json = c_res.json()
    assert "embedding" not in c_json
    assert c_json["has_embedding"] is True
    faq_id = c_json["id"]

    # Get single
    g_res = await async_client.get(f"/api/v1/knowledge/{faq_id}", headers=headers)
    assert "embedding" not in g_res.json()

    # List
    l_res = await async_client.get("/api/v1/knowledge", headers=headers)
    for item in l_res.json():
        assert "embedding" not in item

    # Update
    u_res = await async_client.patch(
        f"/api/v1/knowledge/{faq_id}",
        json={"answer": "Updated privacy test answer."},
        headers=headers,
    )
    assert "embedding" not in u_res.json()

    # Search
    s_res = await async_client.post(
        "/api/v1/knowledge/search",
        json={"query": "privacy test", "top_k": 5},
        headers=headers,
    )
    for result in s_res.json()["results"]:
        assert "embedding" not in result["entry"]


# ============================================================================
# 15. Route Ordering Verification
# ============================================================================

@pytest.mark.asyncio
async def test_route_ordering_search_vs_id(async_client: AsyncClient):
    """Verifies POST /api/v1/knowledge/search is not matched against /{knowledge_id}."""
    _, token, _ = await create_owner_with_business(async_client, "Route Order Biz")
    headers = {"Authorization": f"Bearer {token}"}

    # If /{knowledge_id} had precedence, POST /search would fail with 405 or 422 UUID parsing error
    search_res = await async_client.post(
        "/api/v1/knowledge/search",
        json={"query": "route precedence check", "top_k": 5},
        headers=headers,
    )
    assert search_res.status_code == 200
    assert "results" in search_res.json()

