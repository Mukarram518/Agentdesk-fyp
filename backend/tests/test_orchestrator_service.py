"""Unit tests for AgentDesk AI Orchestrator service and intent routing (Phase 6.2D).

Verifies:
1. Deterministic intent routing (FAQ, Lead, Appointment, General, Unknown).
2. Agent selection (Chat, Lead, Booking, Voice) and config respect (lead_enabled, voice_enabled).
3. End-to-end turn processing with MockLLMProvider.
4. Language detection integration (English, Native Urdu, Roman Urdu).
5. Source ID preservation from retrieved knowledge into AgentTurnOutput.sources.
6. Token usage preservation from LLM provider.
7. Empty/whitespace LLM response handling with safe fallback.
8. LLM provider error handling with graceful, secure fallback without leaking secrets.
9. Tool call boundary: model tool calls captured in turn output without unverified execution.
10. Zero database mutations or conversation persistence.
"""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.models.business import Business
from app.models.knowledge import KnowledgeBaseEntry
from app.orchestrator import (
    AIOrchestrator,
    AgentConfig,
    AgentTurnInput,
    AgentTurnOutput,
    AgentType,
    ChannelType,
    ContextBuilder,
    IntentType,
    LanguageCode,
    detect_intent,
    select_agent,
)
from app.orchestrator.service import FALLBACK_RESPONSES
from app.providers.llm import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    MockLLMProvider,
    TokenUsage,
    ToolCall,
    ToolCallFunction,
)


# Override session DB isolation and rate limit fixtures so pure unit tests run standalone
@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No live database connection needed for pure orchestrator unit tests."""
    yield


@pytest.fixture(autouse=True)
def auto_reset_rate_limits():
    """No rate limit reset needed for pure unit tests."""
    yield


# =====================================================================
# 1. Deterministic Intent Routing Tests
# =====================================================================

def test_intent_routing_appointment():
    """Verifies appointment and booking requests across English, Roman Urdu, and Urdu."""
    queries = [
        "Can I book an appointment tomorrow?",
        "I need to schedule a consultation with the doctor.",
        "Kal 3 baje appointment mil sakti hai?",
        "Appointment kaise book karwa sakta hoon?",
        "میں اپائنٹمنٹ کیسے بک کر سکتا ہوں؟",
        "کیا کل کے لیے کوئی سلاٹ دستیاب ہے؟",
    ]
    for q in queries:
        assert detect_intent(q) == IntentType.APPOINTMENT, f"Failed for query: {q}"


def test_intent_routing_lead():
    """Verifies buying intent and pricing inquiries across English, Roman Urdu, and Urdu."""
    queries = [
        "How much does your service cost?",
        "What are your pricing packages?",
        "I want to purchase the premium plan.",
        "Consultation fee kitni hai?",
        "Pricing packages kya hain?",
        "پیکیجز کی قیمتیں کیا ہیں؟",
        "سروس کی فیس کتنی ہے؟",
    ]
    for q in queries:
        assert detect_intent(q) == IntentType.LEAD, f"Failed for query: {q}"


def test_intent_routing_faq():
    """Verifies informational and FAQ inquiries across English, Roman Urdu, and Urdu."""
    queries = [
        "What time does your office open?",
        "Where is your clinic located?",
        "What is your refund policy?",
        "Office timings aur location kya hain?",
        "Aap ka office kab khulta hai?",
        "آپ کا دفتر کب کھلتا ہے؟",
        "آپ کی کمپنی کا پتہ کیا ہے؟",
    ]
    for q in queries:
        assert detect_intent(q) == IntentType.FAQ, f"Failed for query: {q}"


def test_intent_routing_general():
    """Verifies greetings and pleasantries without specific business inquiries."""
    queries = [
        "Hello there!",
        "Hi, how are you?",
        "Good morning!",
        "Thank you so much!",
        "Assalam o alaikum!",
        "Shukriya, Allah hafiz",
        "السلام علیکم، کیسے ہیں آپ؟",
        "بہت شکریہ",
    ]
    for q in queries:
        assert detect_intent(q) == IntentType.GENERAL, f"Failed for query: {q}"


def test_intent_routing_unknown():
    """Verifies unknown intent fallback on gibberish, numeric, or unclassifiable text."""
    queries = [
        "123456789",
        "???",
        "asdfghjkl",
        "",
        "   ",
    ]
    for q in queries:
        assert detect_intent(q) == IntentType.UNKNOWN, f"Failed for query: {q}"


# =====================================================================
# 2. Agent Selection Tests
# =====================================================================

def test_agent_selection_by_intent():
    """Verifies agent selection according to intent type."""
    assert select_agent(IntentType.APPOINTMENT, ChannelType.WEB) == AgentType.BOOKING
    assert select_agent(IntentType.LEAD, ChannelType.WEB) == AgentType.LEAD
    assert select_agent(IntentType.FAQ, ChannelType.WEB) == AgentType.CHAT
    assert select_agent(IntentType.GENERAL, ChannelType.WEB) == AgentType.CHAT
    assert select_agent(IntentType.UNKNOWN, ChannelType.WEB) == AgentType.CHAT


def test_agent_selection_lead_disabled_fallback():
    """Verifies that lead agent falls back to chat when lead_enabled is False."""
    config_lead_disabled = AgentConfig(lead_enabled=False)
    selected = select_agent(
        intent=IntentType.LEAD,
        channel=ChannelType.WEB,
        agent_config=config_lead_disabled,
    )
    assert selected == AgentType.CHAT


def test_agent_selection_voice_channel():
    """Verifies that voice channel selects Voice Agent when voice_enabled is True."""
    config_voice_enabled = AgentConfig(voice_enabled=True)
    selected = select_agent(
        intent=IntentType.FAQ,
        channel=ChannelType.VOICE,
        agent_config=config_voice_enabled,
    )
    assert selected == AgentType.VOICE

    # When voice is disabled on voice channel, routes according to intent
    config_voice_disabled = AgentConfig(voice_enabled=False)
    selected_fallback = select_agent(
        intent=IntentType.FAQ,
        channel=ChannelType.VOICE,
        agent_config=config_voice_disabled,
    )
    assert selected_fallback == AgentType.CHAT


# =====================================================================
# 3. AIOrchestrator End-to-End Turn Processing Tests
# =====================================================================

@pytest.mark.asyncio
async def test_orchestrator_handle_turn_faq_success():
    """Verifies complete turn execution for an FAQ query using MockLLMProvider."""
    business_id = uuid.uuid4()
    entry_id = uuid.uuid4()

    mock_db = MagicMock()
    mock_ks = MagicMock()
    mock_br = MagicMock()

    # Mock business entity
    business = MagicMock(spec=Business)
    business.id = business_id
    business.name = "Health First Clinic"
    business.slug = "health-first"
    mock_br.get_by_id = AsyncMock(return_value=business)

    # Mock knowledge entry
    entry = MagicMock(spec=KnowledgeBaseEntry)
    entry.id = entry_id
    entry.business_id = business_id
    entry.question = "What are your clinic hours?"
    entry.answer = "We are open Monday to Saturday from 9 AM to 8 PM."
    entry.source_type = "FAQ"
    entry.tags = ["hours", "timings"]
    entry.section_title = None

    mock_ks.search_knowledge = AsyncMock(return_value=[(entry, 0.15)])

    context_builder = ContextBuilder(
        knowledge_service=mock_ks,
        business_repo=mock_br,
    )

    mock_llm = MockLLMProvider(
        responses=["We are open Monday to Saturday from 9 AM to 8 PM."],
    )

    orchestrator = AIOrchestrator(
        llm_provider=mock_llm,
        context_builder=context_builder,
    )

    turn_input = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WEB,
        message="What are your clinic hours?",
    )

    output: AgentTurnOutput = await orchestrator.handle_turn(
        db=mock_db,
        turn_input=turn_input,
    )

    assert isinstance(output, AgentTurnOutput)
    assert output.response == "We are open Monday to Saturday from 9 AM to 8 PM."
    assert output.language == LanguageCode.EN
    assert output.intent == IntentType.FAQ
    assert output.agent == AgentType.CHAT
    assert output.sources == [entry_id]
    assert output.confidence is not None and output.confidence > 0.8
    assert output.usage is not None
    assert output.usage.total_tokens > 0
    assert output.metadata["provider"] == "mock"


@pytest.mark.asyncio
async def test_orchestrator_handle_turn_appointment_booking():
    """Verifies appointment intent routing and Booking agent selection."""
    business_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_ks = MagicMock()
    mock_ks.search_knowledge = AsyncMock(return_value=[])
    mock_br = MagicMock()
    mock_br.get_by_id = AsyncMock(return_value=None)

    context_builder = ContextBuilder(knowledge_service=mock_ks, business_repo=mock_br)
    mock_llm = MockLLMProvider(default_response="I can help you book an appointment. What date suits you?")

    orchestrator = AIOrchestrator(llm_provider=mock_llm, context_builder=context_builder)

    turn_input = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WHATSAPP,
        message="Can I schedule a consultation tomorrow at 3 PM?",
    )

    output = await orchestrator.handle_turn(db=mock_db, turn_input=turn_input)
    assert output.intent == IntentType.APPOINTMENT
    assert output.agent == AgentType.BOOKING
    assert output.language == LanguageCode.EN
    assert "book an appointment" in output.response


@pytest.mark.asyncio
async def test_orchestrator_handle_turn_lead_agent():
    """Verifies lead intent routing and Lead agent selection."""
    business_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_ks = MagicMock()
    mock_ks.search_knowledge = AsyncMock(return_value=[])
    mock_br = MagicMock()
    mock_br.get_by_id = AsyncMock(return_value=None)

    context_builder = ContextBuilder(knowledge_service=mock_ks, business_repo=mock_br)
    mock_llm = MockLLMProvider(default_response="Our standard package costs $100 per month.")

    orchestrator = AIOrchestrator(llm_provider=mock_llm, context_builder=context_builder)

    turn_input = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WEB,
        message="What is the price of your monthly package?",
    )

    output = await orchestrator.handle_turn(db=mock_db, turn_input=turn_input)
    assert output.intent == IntentType.LEAD
    assert output.agent == AgentType.LEAD
    assert output.language == LanguageCode.EN


@pytest.mark.asyncio
async def test_orchestrator_handle_turn_multilingual_urdu():
    """Verifies Native Urdu and Roman Urdu language detection and propagation in orchestrator."""
    business_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_ks = MagicMock()
    mock_ks.search_knowledge = AsyncMock(return_value=[])
    mock_br = MagicMock()
    mock_br.get_by_id = AsyncMock(return_value=None)

    context_builder = ContextBuilder(knowledge_service=mock_ks, business_repo=mock_br)
    mock_llm = MockLLMProvider(default_response="جی بالکل، ہمارا کلینک صبح 9 بجے کھلتا ہے۔")

    orchestrator = AIOrchestrator(llm_provider=mock_llm, context_builder=context_builder)

    # 1. Native Urdu turn
    ur_turn = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WEB,
        message="آپ کا دفتر کب کھلتا ہے؟",
    )
    ur_output = await orchestrator.handle_turn(db=mock_db, turn_input=ur_turn)
    assert ur_output.language == LanguageCode.UR
    assert ur_output.intent == IntentType.FAQ
    assert ur_output.agent == AgentType.CHAT

    # 2. Roman Urdu turn
    mock_llm.set_default_response("Ji bilkul, office subah 9 baje open hota hai.")
    mixed_turn = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WHATSAPP,
        message="Office kab khulta hai?",
    )
    mixed_output = await orchestrator.handle_turn(db=mock_db, turn_input=mixed_turn)
    assert mixed_output.language == LanguageCode.MIXED
    assert mixed_output.intent == IntentType.FAQ


@pytest.mark.asyncio
async def test_orchestrator_tool_calls_preserved_not_executed():
    """Verifies that tool calls returned by LLM are preserved in output but not executed."""
    business_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_ks = MagicMock()
    mock_ks.search_knowledge = AsyncMock(return_value=[])
    mock_br = MagicMock()
    mock_br.get_by_id = AsyncMock(return_value=None)

    context_builder = ContextBuilder(knowledge_service=mock_ks, business_repo=mock_br)

    tool_call = ToolCall(
        id="call_check_avail_99",
        function=ToolCallFunction(
            name="check_calendar_availability",
            arguments='{"date": "2026-11-15"}',
        ),
    )
    mock_llm = MockLLMProvider(
        responses=[
            LLMResponse(
                content="Checking available slots for you...",
                tool_calls=[tool_call],
                model="mock-model",
                provider="mock",
                finish_reason="tool_calls",
            )
        ]
    )

    orchestrator = AIOrchestrator(llm_provider=mock_llm, context_builder=context_builder)

    turn_input = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WEB,
        message="Can I book on November 15?",
    )

    output = await orchestrator.handle_turn(db=mock_db, turn_input=turn_input)
    assert len(output.tool_calls) == 1
    assert output.tool_calls[0].id == "call_check_avail_99"
    assert output.tool_calls[0].function.name == "check_calendar_availability"
    assert output.response == "Checking available slots for you..."


@pytest.mark.asyncio
async def test_orchestrator_empty_provider_response_fallback():
    """Verifies that an empty or whitespace response from the provider falls back safely."""
    business_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_ks = MagicMock()
    mock_ks.search_knowledge = AsyncMock(return_value=[])
    mock_br = MagicMock()
    mock_br.get_by_id = AsyncMock(return_value=None)

    context_builder = ContextBuilder(knowledge_service=mock_ks, business_repo=mock_br)

    mock_llm = MagicMock()
    # Mock provider returning an empty/whitespace text response
    mock_response = MagicMock()
    mock_response.content = "   "
    mock_response.tool_calls = []
    mock_response.usage = None
    mock_response.model = "test-model"
    mock_response.provider = "test"
    mock_response.finish_reason = "stop"
    mock_llm.generate = AsyncMock(return_value=mock_response)
    mock_llm.model_name = "test-model"
    mock_llm.provider_name = "test"

    orchestrator = AIOrchestrator(llm_provider=mock_llm, context_builder=context_builder)

    turn_input = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WEB,
        message="Hello",
    )

    output = await orchestrator.handle_turn(db=mock_db, turn_input=turn_input)
    assert output.response == FALLBACK_RESPONSES[LanguageCode.EN]


@pytest.mark.asyncio
async def test_orchestrator_provider_exception_safe_fallback():
    """Verifies that LLM provider errors are caught gracefully without leaking stack traces or secrets."""
    business_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_ks = MagicMock()
    mock_ks.search_knowledge = AsyncMock(return_value=[])
    mock_br = MagicMock()
    mock_br.get_by_id = AsyncMock(return_value=None)

    context_builder = ContextBuilder(knowledge_service=mock_ks, business_repo=mock_br)

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=LLMTimeoutError("Groq request timed out after 30s"))
    mock_llm.model_name = "mock-model"
    mock_llm.provider_name = "mock-provider"

    orchestrator = AIOrchestrator(llm_provider=mock_llm, context_builder=context_builder)

    turn_input = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WEB,
        message="Can you answer my question?",
    )

    output = await orchestrator.handle_turn(db=mock_db, turn_input=turn_input)

    # Must return a valid AgentTurnOutput with polite fallback
    assert isinstance(output, AgentTurnOutput)
    assert output.response == FALLBACK_RESPONSES[LanguageCode.EN]
    assert output.metadata["fallback"] is True
    assert output.metadata["error"] == "Groq request timed out after 30s"
    assert output.confidence == 0.0


@pytest.mark.asyncio
async def test_orchestrator_zero_database_mutations():
    """Verifies that orchestrator handle_turn performs zero database writes."""
    business_id = uuid.uuid4()
    mock_db = MagicMock(spec=["execute"])
    mock_ks = MagicMock()
    mock_ks.search_knowledge = AsyncMock(return_value=[])
    mock_br = MagicMock()
    mock_br.get_by_id = AsyncMock(return_value=None)

    context_builder = ContextBuilder(knowledge_service=mock_ks, business_repo=mock_br)
    mock_llm = MockLLMProvider(default_response="Read-only response")

    orchestrator = AIOrchestrator(llm_provider=mock_llm, context_builder=context_builder)

    turn_input = AgentTurnInput(
        business_id=business_id,
        channel=ChannelType.WEB,
        message="Testing read-only database boundary",
    )

    await orchestrator.handle_turn(db=mock_db, turn_input=turn_input)

    assert not hasattr(mock_db, "add") or not mock_db.add.called
    assert not hasattr(mock_db, "commit") or not mock_db.commit.called
    assert not hasattr(mock_db, "flush") or not mock_db.flush.called
    assert not hasattr(mock_db, "delete") or not mock_db.delete.called

