"""End-to-End Acceptance Test for Phase 4 (Agent Configuration).

Executes the complete 12-step acceptance testing workflow:
1. Log in as a business owner.
2. Open /agents (GET /api/v1/agents/config).
3. Load the saved configuration.
4. Change tone and greeting.
5. Disable Chat and save (PUT /api/v1/agents/config).
6. Refresh the configuration and confirm the setting persists.
7. Attempt a chat request and verify it is rejected with HTTP 403 (ChatDisabledError).
8. Re-enable Chat.
9. Disable Lead and verify lead-intent messages route to normal chat without creating leads.
10. Disable Voice and verify voice-session initialization is rejected with HTTP 403 (VoiceDisabledError).
11. Re-enable all agents.
12. Switch between two business workspaces and verify complete tenant isolation.
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.security import hash_password
from app.core.widget_auth import generate_widget_token
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.user import User
from app.orchestrator.schemas import (
    AgentTurnInput,
    AgentType,
    ChannelType,
    IntentType,
    LanguageCode,
)
from app.schemas.agent_config import AgentConfigUpdate
from app.services.agent_config_service import agent_config_service
from app.services.voice_service import voice_service

settings = get_settings()
TEST_WIDGET_SECRET = "super-secret-widget-signing-key-for-tests-32b!"


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    monkeypatch.setattr(settings, "WIDGET_TOKEN_SECRET", TEST_WIDGET_SECRET)
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:3000"])


async def create_user_and_business(email_prefix: str, biz_name: str):
    """Helper creating user, business, and business member in the test DB."""
    async with async_session_factory() as session:
        user = User(
            email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("StrongPass123!"),
            full_name=f"Owner of {biz_name}",
        )
        session.add(user)
        await session.flush()

        slug = f"{biz_name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"
        business = Business(
            name=biz_name,
            slug=slug,
            is_active=True,
        )
        session.add(business)
        await session.flush()

        member = BusinessMember(
            business_id=business.id,
            user_id=user.id,
            role=MemberRole.OWNER,
        )
        session.add(member)
        await session.commit()
        return user, business


@pytest.mark.asyncio
async def test_phase4_complete_acceptance_workflow():
    """Complete 12-step acceptance test verifying Phase 4 end-to-end."""
    # -------------------------------------------------------------
    # Step 1: Log in as a business owner
    # -------------------------------------------------------------
    raw_password = "StrongPass123!"
    user_a, biz_a = await create_user_and_business("owner_a", "Zenith Health")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # Perform login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user_a.email, "password": raw_password},
        )
        assert login_resp.status_code == 200
        # Cookie session is automatically managed by httpx AsyncClient

        # ---------------------------------------------------------
        # Step 2: Open /agents (GET /api/v1/agents/config)
        # ---------------------------------------------------------
        get_config_resp = await client.get("/api/v1/agents/config")
        assert get_config_resp.status_code == 200

        # ---------------------------------------------------------
        # Step 3: Load the saved configuration (initial default)
        # ---------------------------------------------------------
        initial_config = get_config_resp.json()
        assert initial_config["business_id"] == str(biz_a.id)
        assert initial_config["tone"] == "helpful"
        assert initial_config["chat_enabled"] is True
        assert initial_config["lead_enabled"] is True
        assert initial_config["voice_enabled"] is True
        assert initial_config["language_priority"] == ["en", "ur"]

        # ---------------------------------------------------------
        # Step 4: Change tone and greeting
        # Step 5: Disable Chat and save (PUT /api/v1/agents/config)
        # ---------------------------------------------------------
        put_payload = {
            "tone": "professional",
            "greeting": "Welcome to Zenith Health. How may our medical team assist you today?",
            "chat_enabled": False,
            "lead_enabled": True,
            "voice_enabled": True,
            "language_priority": ["ur", "en"],
            "voice_id": "eleven-voice-123",
        }
        put_resp = await client.put("/api/v1/agents/config", json=put_payload)
        assert put_resp.status_code == 200
        updated_data = put_resp.json()
        assert updated_data["tone"] == "professional"
        assert updated_data["greeting"] == "Welcome to Zenith Health. How may our medical team assist you today?"
        assert updated_data["chat_enabled"] is False
        assert updated_data["language_priority"] == ["ur", "en"]
        assert updated_data["voice_id"] == "eleven-voice-123"

        # ---------------------------------------------------------
        # Step 6: Refresh the configuration and confirm the setting persists
        # ---------------------------------------------------------
        refresh_resp = await client.get("/api/v1/agents/config")
        assert refresh_resp.status_code == 200
        persisted = refresh_resp.json()
        assert persisted["tone"] == "professional"
        assert persisted["greeting"] == put_payload["greeting"]
        assert persisted["chat_enabled"] is False
        assert persisted["language_priority"] == ["ur", "en"]

        # ---------------------------------------------------------
        # Step 7: Attempt a chat request and verify it is rejected with HTTP 403
        # ---------------------------------------------------------
        widget_token = generate_widget_token(biz_a.id, is_preview=True)
        chat_resp = await client.post(
            "/api/v1/chat/messages",
            headers={
                "X-Widget-Token": widget_token,
                "Origin": "http://localhost:3000",
            },
            json={
                "message": "Hello, I need an appointment.",
                "request_id": str(uuid.uuid4()),
            },
        )
        assert chat_resp.status_code == 403
        assert "Chat is currently disabled" in chat_resp.json()["detail"]

        # ---------------------------------------------------------
        # Step 8: Re-enable Chat
        # ---------------------------------------------------------
        patch_resp = await client.patch(
            "/api/v1/agents/config",
            json={"chat_enabled": True},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["chat_enabled"] is True

        # Verify chat now passes
        chat_ok_resp = await client.post(
            "/api/v1/chat/messages",
            headers={
                "X-Widget-Token": widget_token,
                "Origin": "http://localhost:3000",
            },
            json={
                "message": "Hello, is the clinic open?",
                "request_id": str(uuid.uuid4()),
            },
        )
        assert chat_ok_resp.status_code == 200

        # ---------------------------------------------------------
        # Step 9: Disable Lead and verify lead-intent messages route to normal chat
        # ---------------------------------------------------------
        lead_disable_resp = await client.patch(
            "/api/v1/agents/config",
            json={"lead_enabled": False},
        )
        assert lead_disable_resp.status_code == 200
        assert lead_disable_resp.json()["lead_enabled"] is False

        # Verify orchestrator routing with lead_enabled=False routes to CHAT agent
        from app.orchestrator.service import AIOrchestrator
        from app.providers.llm.mock_provider import MockLLMProvider

        orchestrator = AIOrchestrator(llm_provider=MockLLMProvider())
        buying_message = "What are the prices and packages for root canal treatment?"
        turn_input = AgentTurnInput(
            business_id=biz_a.id,
            channel=ChannelType.WEB,
            message=buying_message,
        )

        async with async_session_factory() as session:
            output = await orchestrator.handle_turn(db=session, turn_input=turn_input)
            assert output.intent == IntentType.LEAD
            assert output.agent == AgentType.CHAT
            assert len(output.tool_calls) == 0

        # ---------------------------------------------------------
        # Step 10: Disable Voice and verify voice-session initialization is rejected
        # ---------------------------------------------------------
        voice_disable_resp = await client.patch(
            "/api/v1/agents/config",
            json={"voice_enabled": False},
        )
        assert voice_disable_resp.status_code == 200
        assert voice_disable_resp.json()["voice_enabled"] is False

        async with async_session_factory() as session:
            from app.core.exceptions import VoiceDisabledError
            with pytest.raises(VoiceDisabledError) as exc_info:
                await voice_service.validate_voice_session_creation(session, biz_a.id)
            assert exc_info.value.status_code == 403
            assert "Voice is currently disabled" in exc_info.value.message

        # ---------------------------------------------------------
        # Step 11: Re-enable all agents
        # ---------------------------------------------------------
        enable_all_resp = await client.patch(
            "/api/v1/agents/config",
            json={"chat_enabled": True, "lead_enabled": True, "voice_enabled": True},
        )
        assert enable_all_resp.status_code == 200
        all_enabled = enable_all_resp.json()
        assert all_enabled["chat_enabled"] is True
        assert all_enabled["lead_enabled"] is True
        assert all_enabled["voice_enabled"] is True

        # ---------------------------------------------------------
        # Step 12: Switch between two business workspaces and verify complete tenant isolation
        # ---------------------------------------------------------
        user_b, biz_b = await create_user_and_business("owner_b", "Horizon Law Firm")

        # Configure Business B with distinct custom settings
        async with async_session_factory() as session:
            await agent_config_service.update_config(
                db=session,
                business_id=biz_b.id,
                payload=AgentConfigUpdate(
                    tone="direct",
                    greeting="Horizon Law. State your legal query.",
                    chat_enabled=False,
                    voice_id="law-firm-voice-99",
                ),
            )
            await session.commit()

        # Log out of user A
        logout_resp = await client.post("/api/v1/auth/logout")
        assert logout_resp.status_code == 200

        # Log in as user B
        login_b_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user_b.email, "password": raw_password},
        )
        assert login_b_resp.status_code == 200

        # Query config as user B
        config_b_resp = await client.get("/api/v1/agents/config")
        assert config_b_resp.status_code == 200
        data_b = config_b_resp.json()

        # Strict tenant isolation verification:
        # 1. Config belongs to Business B, not Business A
        assert data_b["business_id"] == str(biz_b.id)
        assert data_b["tone"] == "direct"
        assert data_b["greeting"] == "Horizon Law. State your legal query."
        assert data_b["chat_enabled"] is False
        assert data_b["voice_id"] == "law-firm-voice-99"

        # 2. Re-verifying Business A's database row remains unchanged and isolated
        async with async_session_factory() as session:
            biz_a_check = await agent_config_service.get_or_create_config(session, biz_a.id)
            assert biz_a_check.business_id == biz_a.id
            assert biz_a_check.tone == "professional"
            assert biz_a_check.greeting == put_payload["greeting"]
            assert biz_a_check.chat_enabled is True
            assert biz_a_check.lead_enabled is True
            assert biz_a_check.voice_enabled is True
            assert biz_a_check.voice_id == "eleven-voice-123"
