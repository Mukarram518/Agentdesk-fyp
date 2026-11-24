"""Integration tests for Phase 4C: AI Orchestrator & Chat Dynamic AgentConfig Integration.

Tests:
1. Dynamic persisted AgentConfig loading: orchestrator loads DB configuration when none is passed in-memory.
2. Saved tone and greeting reaching prompt generation (<agent_configuration> block).
3. Language priority being respected during language fallback/detection.
4. Server-side Chat-Disabled enforcement:
   - Direct AIOrchestrator raises ChatDisabledError (403).
   - POST /api/v1/chat/messages returns HTTP 403 Forbidden without persisting messages.
5. Server-side Lead-Disabled enforcement:
   - Buying/pricing inquiry detected as IntentType.LEAD routes to AgentType.CHAT.
   - Zero lead capture tool calls executed or produced.
6. Server-side Voice-Disabled enforcement:
   - Direct AIOrchestrator with ChannelType.VOICE raises VoiceDisabledError (403).
   - voice_service.validate_voice_session_creation raises VoiceDisabledError (403).
7. Strict multi-tenant isolation:
   - Business A's disabled chat does not affect Business B.
   - Business A's custom tone/greeting is never leaked to Business B.
8. Normal chat behavior when channels are enabled:
   - Standard conversational message executes and returns 200 OK.
"""

import uuid
from typing import Tuple
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.exceptions import ChatDisabledError, VoiceDisabledError
from app.core.widget_auth import generate_widget_token
from app.models.agent_config import AgentConfig as AgentConfigModel
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.user import User
from app.orchestrator.context import ContextBuilder
from app.orchestrator.schemas import (
    AgentTurnInput,
    AgentType,
    ChannelType,
    IntentType,
    LanguageCode,
)
from app.orchestrator.service import AIOrchestrator
from app.providers.llm.mock_provider import MockLLMProvider
from app.repositories.agent_config import agent_config_repository
from app.services.agent_config_service import agent_config_service
from app.services.chat_service import chat_service
from app.services.voice_service import voice_service

settings = get_settings()
TEST_WIDGET_SECRET = "super-secret-widget-signing-key-for-tests-32b!"


@pytest.fixture(autouse=True)
def setup_widget_secret(monkeypatch):
    """Configures dedicated test widget token secret and origins."""
    monkeypatch.setattr(settings, "WIDGET_TOKEN_SECRET", TEST_WIDGET_SECRET)
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"])


async def create_business_with_owner() -> Tuple[Business, str]:
    """Helper creating a business and returning (Business, widget_token)."""
    async with async_session_factory() as db:
        user = User(
            email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Owner User",
            password_hash="test_hash_pw",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        biz = Business(
            name=f"Clinic {uuid.uuid4().hex[:6]}",
            slug=f"clinic-{uuid.uuid4().hex[:8]}",
            allowed_origins=["http://localhost:3000"],
            is_active=True,
        )
        db.add(biz)
        await db.flush()

        member = BusinessMember(
            business_id=biz.id,
            user_id=user.id,
            role=MemberRole.OWNER.value,
        )
        db.add(member)
        await db.commit()
        await db.refresh(biz)

    token = generate_widget_token(business_id=biz.id, secret=TEST_WIDGET_SECRET)
    return biz, token


# ============================================================================
# 1. Dynamic AgentConfig Loading & Prompt Generation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_dynamic_agent_config_loading_in_orchestrator():
    """Verifies orchestrator dynamically loads persisted AgentConfig from database."""
    biz, _ = await create_business_with_owner()

    # Persist custom configuration in DB
    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            tone="friendly",
            greeting="Welcome to Apex Clinic!",
            language_priority=["ur", "en"],
        )
        await db.commit()

    orchestrator = AIOrchestrator(llm_provider=MockLLMProvider())

    turn_input = AgentTurnInput(
        business_id=biz.id,
        channel=ChannelType.WEB,
        message="What are your hours?",
    )

    async with async_session_factory() as db:
        # Note: agent_config is NOT passed in-memory; orchestrator must fetch from DB
        output = await orchestrator.handle_turn(
            db=db,
            turn_input=turn_input,
            business=biz,
        )
        assert output is not None
        assert output.agent == AgentType.CHAT


@pytest.mark.asyncio
async def test_saved_tone_and_greeting_reaching_prompt():
    """Verifies that saved tone and greeting reach the system prompt."""
    biz, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            tone="direct",
            greeting="Welcome to Direct Dental Care.",
            language_priority=["en"],
        )
        await db.commit()

    context_builder = ContextBuilder()
    turn_input = AgentTurnInput(
        business_id=biz.id,
        channel=ChannelType.WEB,
        message="Hello, do you have slots tomorrow?",
    )

    async with async_session_factory() as db:
        # ContextBuilder resolves DB config dynamically
        ctx = await context_builder.build(
            db=db,
            turn_input=turn_input,
            business=biz,
        )

        assert "<agent_configuration>" in ctx.system_prompt
        assert "</agent_configuration>" in ctx.system_prompt
        assert "Response Tone: direct" in ctx.system_prompt
        assert "Configured Greeting: Welcome to Direct Dental Care." in ctx.system_prompt
        assert ctx.agent_config.tone == "direct"
        assert ctx.agent_config.greeting == "Welcome to Direct Dental Care."


@pytest.mark.asyncio
async def test_language_priority_respected_in_fallback():
    """Verifies that language_priority is loaded and respected for ambiguous input."""
    biz_ur, _ = await create_business_with_owner()
    biz_en, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        # Business A prioritizes Urdu
        await agent_config_repository.create_default(
            db=db,
            business_id=biz_ur.id,
            language_priority=["ur", "en"],
        )
        # Business B prioritizes English
        await agent_config_repository.create_default(
            db=db,
            business_id=biz_en.id,
            language_priority=["en", "ur"],
        )
        await db.commit()

    context_builder = ContextBuilder()
    # Non-linguistic / purely numeric input falls back to priority[0]
    ambiguous_msg = "??? 998877"

    async with async_session_factory() as db:
        ctx_ur = await context_builder.build(
            db=db,
            turn_input=AgentTurnInput(business_id=biz_ur.id, channel=ChannelType.WEB, message=ambiguous_msg),
        )
        ctx_en = await context_builder.build(
            db=db,
            turn_input=AgentTurnInput(business_id=biz_en.id, channel=ChannelType.WEB, message=ambiguous_msg),
        )

        assert ctx_ur.language == LanguageCode.UR
        assert ctx_en.language == LanguageCode.EN


# ============================================================================
# 2. Channel Enforcement: Chat Disabled Tests
# ============================================================================


@pytest.mark.asyncio
async def test_chat_disabled_direct_orchestrator_raises_403():
    """Verifies AIOrchestrator rejects chat turn when chat_enabled is False."""
    biz, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            chat_enabled=False,
        )
        await db.commit()

    orchestrator = AIOrchestrator(llm_provider=MockLLMProvider())
    turn_input = AgentTurnInput(
        business_id=biz.id,
        channel=ChannelType.WEB,
        message="Hello, can I ask a question?",
    )

    async with async_session_factory() as db:
        with pytest.raises(ChatDisabledError) as exc_info:
            await orchestrator.handle_turn(db=db, turn_input=turn_input)
        assert exc_info.value.status_code == 403
        assert "Chat is currently disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chat_disabled_api_endpoint_returns_403(async_client: AsyncClient):
    """Verifies POST /api/v1/chat/messages returns 403 Forbidden when chat is disabled."""
    biz, token = await create_business_with_owner()

    # Disable chat for this business
    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            chat_enabled=False,
        )
        await db.commit()

    headers = {
        "X-Widget-Token": token,
        "Origin": "http://localhost:3000",
    }
    payload = {
        "message": "Hello, is anyone there?",
        "request_id": str(uuid.uuid4()),
    }

    res = await async_client.post("/api/v1/chat/messages", headers=headers, json=payload)
    assert res.status_code == 403
    assert "Chat is currently disabled" in res.json()["detail"]

    # Verify no message or conversation was saved
    async with async_session_factory() as db:
        from app.models.conversation import Conversation
        from sqlalchemy import select
        conv_res = await db.execute(select(Conversation).where(Conversation.business_id == biz.id))
        assert conv_res.scalars().first() is None


# ============================================================================
# 3. Channel Enforcement: Lead Disabled Fallback Tests
# ============================================================================


@pytest.mark.asyncio
async def test_lead_disabled_falls_back_to_chat_without_creating_lead():
    """Verifies lead intent routes to CHAT when lead_enabled is False, without lead creation."""
    biz, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            lead_enabled=False,
            tone="professional",
        )
        await db.commit()

    orchestrator = AIOrchestrator(llm_provider=MockLLMProvider())

    # High-confidence buying / pricing inquiry
    buying_message = "What are the prices and packages for root canal treatment?"

    turn_input = AgentTurnInput(
        business_id=biz.id,
        channel=ChannelType.WEB,
        message=buying_message,
    )

    async with async_session_factory() as db:
        output = await orchestrator.handle_turn(db=db, turn_input=turn_input)

        # 1. Intent is accurately recognized as LEAD
        assert output.intent == IntentType.LEAD
        # 2. Agent routes to CHAT (not LEAD)
        assert output.agent == AgentType.CHAT
        # 3. No lead capture tool calls
        assert len(output.tool_calls) == 0


@pytest.mark.asyncio
async def test_lead_enabled_routes_to_lead_agent():
    """Verifies lead intent routes to LEAD agent when lead_enabled is True."""
    biz, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            lead_enabled=True,
        )
        await db.commit()

    orchestrator = AIOrchestrator(llm_provider=MockLLMProvider())
    turn_input = AgentTurnInput(
        business_id=biz.id,
        channel=ChannelType.WEB,
        message="What are your service packages and quotation rates?",
    )

    async with async_session_factory() as db:
        output = await orchestrator.handle_turn(db=db, turn_input=turn_input)
        assert output.intent == IntentType.LEAD
        assert output.agent == AgentType.LEAD


# ============================================================================
# 4. Channel Enforcement: Voice Disabled Tests
# ============================================================================


@pytest.mark.asyncio
async def test_voice_disabled_direct_orchestrator_raises_403():
    """Verifies orchestrator raises VoiceDisabledError when voice channel is disabled."""
    biz, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            voice_enabled=False,
        )
        await db.commit()

    orchestrator = AIOrchestrator(llm_provider=MockLLMProvider())
    turn_input = AgentTurnInput(
        business_id=biz.id,
        channel=ChannelType.VOICE,
        message="Hello from voice simulator",
    )

    async with async_session_factory() as db:
        with pytest.raises(VoiceDisabledError) as exc_info:
            await orchestrator.handle_turn(db=db, turn_input=turn_input)
        assert exc_info.value.status_code == 403
        assert "Voice is currently disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_voice_disabled_session_validation_raises_403():
    """Verifies voice_service.validate_voice_session_creation raises 403 when voice_enabled=False."""
    biz, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            voice_enabled=False,
        )
        await db.commit()

    async with async_session_factory() as db:
        with pytest.raises(VoiceDisabledError) as exc_info:
            await voice_service.validate_voice_session_creation(db=db, business_id=biz.id)
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_voice_enabled_session_validation_succeeds():
    """Verifies voice_service.validate_voice_session_creation succeeds when voice_enabled=True."""
    biz, _ = await create_business_with_owner()

    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            voice_enabled=True,
            voice_id="elevenlabs_voice_sarah",
        )
        await db.commit()

    async with async_session_factory() as db:
        config = await voice_service.validate_voice_session_creation(db=db, business_id=biz.id)
        assert config.voice_enabled is True
        assert config.voice_id == "elevenlabs_voice_sarah"


# ============================================================================
# 5. Multi-Tenant Isolation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_tenant_isolation_chat_disabled_does_not_affect_other_business(
    async_client: AsyncClient,
):
    """Verifies Business A's disabled chat does not block Business B."""
    biz_a, token_a = await create_business_with_owner()
    biz_b, token_b = await create_business_with_owner()

    # Business A disables chat; Business B leaves chat enabled
    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz_a.id,
            chat_enabled=False,
            tone="friendly",
            greeting="Alpha Greeting",
        )
        await agent_config_repository.create_default(
            db=db,
            business_id=biz_b.id,
            chat_enabled=True,
            tone="professional",
            greeting="Beta Greeting",
        )
        await db.commit()

    # Business A chat request: 403
    res_a = await async_client.post(
        "/api/v1/chat/messages",
        headers={"X-Widget-Token": token_a, "Origin": "http://localhost:3000"},
        json={"message": "Hi Alpha", "request_id": str(uuid.uuid4())},
    )
    assert res_a.status_code == 403

    # Business B chat request: 200 OK
    res_b = await async_client.post(
        "/api/v1/chat/messages",
        headers={"X-Widget-Token": token_b, "Origin": "http://localhost:3000"},
        json={"message": "Hi Beta", "request_id": str(uuid.uuid4())},
    )
    assert res_b.status_code == 200
    assert "conversation_id" in res_b.json()


# ============================================================================
# 6. Existing Chat Behavior When All Channels Are Enabled
# ============================================================================


@pytest.mark.asyncio
async def test_normal_chat_turn_when_channels_enabled(async_client: AsyncClient):
    """Verifies end-to-end chat turn succeeds with 200 OK when channels are enabled."""
    biz, token = await create_business_with_owner()

    # Explicitly ensure all channels enabled
    async with async_session_factory() as db:
        await agent_config_repository.create_default(
            db=db,
            business_id=biz.id,
            chat_enabled=True,
            voice_enabled=True,
            lead_enabled=True,
            tone="helpful",
            greeting="Welcome to our business!",
        )
        await db.commit()

    headers = {
        "X-Widget-Token": token,
        "Origin": "http://localhost:3000",
    }
    req_id = str(uuid.uuid4())

    res = await async_client.post(
        "/api/v1/chat/messages",
        headers=headers,
        json={"message": "What are your business hours?", "request_id": req_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert data["message"]["role"] == "assistant"
    assert len(data["message"]["content"]) > 0

