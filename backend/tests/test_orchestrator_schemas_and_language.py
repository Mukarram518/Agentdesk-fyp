"""Unit tests for AgentDesk AI Orchestrator schemas and language detection (Phase 6.2B).

Verifies:
1. Orchestrator Enums:
   - ChannelType (web, whatsapp, voice).
   - LanguageCode (en, ur, mixed).
   - IntentType (faq, lead, appointment, general, unknown).
   - AgentType (chat, lead, booking, voice).
2. AgentConfig Schema:
   - Default values and types.
   - Custom overrides.
3. AgentTurnInput Schema:
   - Required fields and types (business_id, channel, message).
   - Optional fields (conversation_id, customer_id, language, history, metadata).
   - Whitespace stripping and non-empty message validation.
   - Channel enum coercion and invalid channel rejection.
   - UUID validation.
4. AgentTurnOutput Schema:
   - Required fields (response, language, intent, agent).
   - Optional fields (tool_calls, confidence, sources, usage, metadata).
   - Non-empty response validation.
   - Confidence bounds validation (0.0 <= confidence <= 1.0).
   - Integration with ToolCall, TokenUsage, and UUID sources.
5. Deterministic Language Detection (detect_language):
   - English sentences.
   - Native Urdu sentences in Arabic script.
   - Urdu with Latin brand names/acronyms (predominantly Urdu).
   - Roman Urdu sentences and phrases (mixed).
   - Substantial bilingual code-switching (mixed).
   - Non-alphabetic and empty inputs with language-priority fallback.
   - False-positive prevention for English words containing Roman Urdu substrings.
"""

import uuid
import pytest
from pydantic import ValidationError

from app.orchestrator import (
    AgentConfig,
    AgentTurnInput,
    AgentTurnOutput,
    AgentType,
    ChannelType,
    IntentType,
    LanguageCode,
    detect_language,
)
from app.providers.llm.schemas import ChatMessage, TokenUsage, ToolCall, ToolCallFunction


# Override session DB isolation and rate limit fixtures so pure unit tests can run standalone
@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """No database connection needed for pure orchestrator unit tests."""
    yield


@pytest.fixture(autouse=True)
def auto_reset_rate_limits():
    """No rate limit reset needed for pure unit tests."""
    yield


# =====================================================================
# 1. Enums Tests
# =====================================================================

def test_channel_type_enum():
    """Verifies supported channels."""
    assert ChannelType.WEB == "web"
    assert ChannelType.WHATSAPP == "whatsapp"
    assert ChannelType.VOICE == "voice"
    assert len(ChannelType) == 3


def test_language_code_enum():
    """Verifies supported language codes."""
    assert LanguageCode.EN == "en"
    assert LanguageCode.UR == "ur"
    assert LanguageCode.MIXED == "mixed"
    assert len(LanguageCode) == 3


def test_intent_type_enum():
    """Verifies supported intent classifications."""
    assert IntentType.FAQ == "faq"
    assert IntentType.LEAD == "lead"
    assert IntentType.APPOINTMENT == "appointment"
    assert IntentType.GENERAL == "general"
    assert IntentType.UNKNOWN == "unknown"
    assert len(IntentType) == 5


def test_agent_type_enum():
    """Verifies supported specialized agent types."""
    assert AgentType.CHAT == "chat"
    assert AgentType.LEAD == "lead"
    assert AgentType.BOOKING == "booking"
    assert AgentType.VOICE == "voice"
    assert len(AgentType) == 4


# =====================================================================
# 2. AgentConfig Schema Tests
# =====================================================================

def test_agent_config_defaults():
    """Verifies default values of in-memory AgentConfig."""
    config = AgentConfig()
    assert config.business_id is None
    assert config.voice_enabled is True
    assert config.chat_enabled is True
    assert config.lead_enabled is True
    assert config.voice_id is None
    assert config.tone == "helpful"
    assert config.greeting is None
    assert config.language_priority == ["en", "ur"]


def test_agent_config_custom_values():
    """Verifies custom configuration attributes."""
    b_id = uuid.uuid4()
    config = AgentConfig(
        business_id=b_id,
        voice_enabled=False,
        chat_enabled=True,
        lead_enabled=False,
        voice_id="eleven_voice_123",
        tone="professional and formal",
        greeting="Welcome to our clinic! How can we assist you today?",
        language_priority=["ur", "en"],
    )
    assert config.business_id == b_id
    assert config.voice_enabled is False
    assert config.chat_enabled is True
    assert config.lead_enabled is False
    assert config.voice_id == "eleven_voice_123"
    assert config.tone == "professional and formal"
    assert config.greeting == "Welcome to our clinic! How can we assist you today?"
    assert config.language_priority == ["ur", "en"]


# =====================================================================
# 3. AgentTurnInput Schema Tests
# =====================================================================

def test_agent_turn_input_valid():
    """Verifies creation of valid turn input with minimal required fields."""
    b_id = uuid.uuid4()
    turn = AgentTurnInput(
        business_id=b_id,
        channel=ChannelType.WEB,
        message="Hello, what time do you open?",
    )
    assert turn.business_id == b_id
    assert turn.channel == ChannelType.WEB
    assert turn.message == "Hello, what time do you open?"
    assert turn.conversation_id is None
    assert turn.customer_id is None
    assert turn.language is None
    assert turn.history == []
    assert turn.metadata == {}


def test_agent_turn_input_all_fields():
    """Verifies turn input with all optional fields and history."""
    b_id = uuid.uuid4()
    c_id = uuid.uuid4()
    history = [
        ChatMessage.user("Hi"),
        ChatMessage.assistant("Hello! How can I help you today?"),
    ]
    turn = AgentTurnInput(
        business_id=b_id,
        channel="whatsapp",
        message="Can I book a consultation tomorrow?",
        conversation_id=c_id,
        customer_id="+923001234567",
        language=LanguageCode.EN,
        history=history,
        metadata={"whatsapp_sender": "+923001234567", "ip": "127.0.0.1"},
    )
    assert turn.business_id == b_id
    assert turn.channel == ChannelType.WHATSAPP
    assert turn.conversation_id == c_id
    assert turn.customer_id == "+923001234567"
    assert turn.language == LanguageCode.EN
    assert len(turn.history) == 2
    assert turn.metadata["whatsapp_sender"] == "+923001234567"


def test_agent_turn_input_message_stripping():
    """Verifies that surrounding whitespace is stripped from customer message."""
    b_id = uuid.uuid4()
    turn = AgentTurnInput(
        business_id=b_id,
        channel=ChannelType.VOICE,
        message="   Appointment booking request   \n",
    )
    assert turn.message == "Appointment booking request"


def test_agent_turn_input_rejects_empty_message():
    """Verifies that empty or whitespace-only messages are rejected."""
    b_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        AgentTurnInput(
            business_id=b_id,
            channel=ChannelType.WEB,
            message="",
        )

    with pytest.raises(ValidationError):
        AgentTurnInput(
            business_id=b_id,
            channel=ChannelType.WEB,
            message="   \n\t  ",
        )


def test_agent_turn_input_rejects_invalid_channel():
    """Verifies that unsupported channels are rejected."""
    b_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        AgentTurnInput(
            business_id=b_id,
            channel="unsupported_channel",  # type: ignore
            message="Test message",
        )


def test_agent_turn_input_rejects_invalid_uuid():
    """Verifies that invalid UUID strings raise validation errors."""
    with pytest.raises(ValidationError):
        AgentTurnInput(
            business_id="not-a-uuid",  # type: ignore
            channel=ChannelType.WEB,
            message="Test message",
        )


# =====================================================================
# 4. AgentTurnOutput Schema Tests
# =====================================================================

def test_agent_turn_output_valid():
    """Verifies valid minimal agent turn output."""
    output = AgentTurnOutput(
        response="We are open Monday through Friday from 9 AM to 6 PM.",
        language=LanguageCode.EN,
        intent=IntentType.FAQ,
        agent=AgentType.CHAT,
    )
    assert output.response == "We are open Monday through Friday from 9 AM to 6 PM."
    assert output.language == LanguageCode.EN
    assert output.intent == IntentType.FAQ
    assert output.agent == AgentType.CHAT
    assert output.tool_calls == []
    assert output.confidence is None
    assert output.sources == []
    assert output.usage is None
    assert output.metadata == {}


def test_agent_turn_output_all_fields():
    """Verifies output containing tool calls, sources, and usage statistics."""
    source_uuid = uuid.uuid4()
    tool_call = ToolCall(
        id="call_check_avail_1",
        function=ToolCallFunction(
            name="check_calendar_availability",
            arguments='{"date": "2026-11-10"}',
        ),
    )
    usage = TokenUsage(prompt_tokens=150, completion_tokens=35, total_tokens=185)

    output = AgentTurnOutput(
        response="I found available slots tomorrow at 3:00 PM.",
        language=LanguageCode.EN,
        intent=IntentType.APPOINTMENT,
        agent=AgentType.BOOKING,
        tool_calls=[tool_call],
        confidence=0.92,
        sources=[source_uuid],
        usage=usage,
        metadata={"model": "llama-3.3-70b-versatile"},
    )
    assert output.confidence == 0.92
    assert len(output.tool_calls) == 1
    assert output.tool_calls[0].function.name == "check_calendar_availability"
    assert output.sources == [source_uuid]
    assert output.usage.total_tokens == 185
    assert output.metadata["model"] == "llama-3.3-70b-versatile"


def test_agent_turn_output_rejects_empty_response():
    """Verifies that empty or whitespace-only response text is rejected."""
    with pytest.raises(ValidationError):
        AgentTurnOutput(
            response="",
            language=LanguageCode.EN,
            intent=IntentType.GENERAL,
            agent=AgentType.CHAT,
        )

    with pytest.raises(ValidationError):
        AgentTurnOutput(
            response="   \n  ",
            language=LanguageCode.EN,
            intent=IntentType.GENERAL,
            agent=AgentType.CHAT,
        )


def test_agent_turn_output_confidence_bounds():
    """Verifies that confidence scores outside [0.0, 1.0] are rejected."""
    # Valid bounds
    output_zero = AgentTurnOutput(
        response="OK",
        language=LanguageCode.EN,
        intent=IntentType.UNKNOWN,
        agent=AgentType.CHAT,
        confidence=0.0,
    )
    assert output_zero.confidence == 0.0

    output_one = AgentTurnOutput(
        response="OK",
        language=LanguageCode.EN,
        intent=IntentType.FAQ,
        agent=AgentType.CHAT,
        confidence=1.0,
    )
    assert output_one.confidence == 1.0

    # Negative confidence
    with pytest.raises(ValidationError):
        AgentTurnOutput(
            response="OK",
            language=LanguageCode.EN,
            intent=IntentType.FAQ,
            agent=AgentType.CHAT,
            confidence=-0.05,
        )

    # Greater than 1.0
    with pytest.raises(ValidationError):
        AgentTurnOutput(
            response="OK",
            language=LanguageCode.EN,
            intent=IntentType.FAQ,
            agent=AgentType.CHAT,
            confidence=1.05,
        )


# =====================================================================
# 5. Deterministic Language Detection Tests
# =====================================================================

def test_detect_language_english():
    """Verifies English sentence detection."""
    queries = [
        "What time does your office open?",
        "How can I book an appointment?",
        "What are the business hours and office location for AgentDesk Demo Business?",
        "Can you please explain your pricing packages and services?",
        "Hello, I would like to schedule a consultation with your team.",
    ]
    for q in queries:
        assert detect_language(q) == LanguageCode.EN, f"Failed for query: {q}"


def test_detect_language_native_urdu():
    """Verifies Native Urdu (Arabic script) detection."""
    queries = [
        "آپ کا دفتر کب کھلتا ہے؟",
        "میں اپائنٹمنٹ کیسے بک کر سکتا ہوں؟",
        "ایجنٹ ڈیسک ڈیمو بزنس کے دفتری اوقات اور پتہ کیا ہے؟",
        "پیکیجز کی قیمتیں اور ادائیگی کے طریقے کیا ہیں؟",
        "براہِ کرم مجھے اپنی سروسز کے بارے میں تفصیلات فراہم کریں۔",
    ]
    for q in queries:
        assert detect_language(q) == LanguageCode.UR, f"Failed for query: {q}"


def test_detect_language_urdu_with_latin_terms():
    """Verifies predominantly Urdu text containing Latin brand names or acronyms."""
    queries = [
        "AgentDesk کے دفتری اوقات کیا ہیں؟",
        "RAG سسٹم کیسے کام کرتا ہے؟",
        "کیا میں WhatsApp پر رابطہ کر سکتا ہوں؟",
    ]
    for q in queries:
        assert detect_language(q) == LanguageCode.UR, f"Failed for query: {q}"


def test_detect_language_roman_urdu():
    """Verifies Roman Urdu / Mixed language detection."""
    queries = [
        "Aap ka office kab khulta hai?",
        "Appointment kaise book karwa sakta hoon?",
        "AgentDesk Demo Business ke office timings aur location kya hain?",
        "Kal 3 baje appointment available hai?",
        "Ap ki clinic ki opening timing kya hai?",
        "Clinic kab open hota hai?",
        "Consultation fee kitni hai?",
        "Kya main online meeting schedule kar sakta hoon?",
        "Batao pricing kya hai?",
        "Theek hai shukriya",
        "Assalam o alaikum, appointment chahiye",
        "Mera appointment cancel kar dein",
    ]
    for q in queries:
        assert detect_language(q) == LanguageCode.MIXED, f"Failed for query: {q}"


def test_detect_language_bilingual_script_mixing():
    """Verifies code-switching where both Latin and Urdu scripts are substantially present."""
    text = "Please tell me: آپ کے پاس کیا سروسز ہیں؟"
    assert detect_language(text) == LanguageCode.MIXED


def test_detect_language_fallback_to_priority():
    """Verifies priority fallback when input contains no linguistic characters."""
    assert detect_language("", language_priority=["ur", "en"]) == LanguageCode.UR
    assert detect_language("   ", language_priority=["mixed", "en"]) == LanguageCode.MIXED
    assert detect_language("12345", language_priority=["ur", "en"]) == LanguageCode.UR
    assert detect_language("12345", language_priority=["en", "ur"]) == LanguageCode.EN
    assert detect_language("??? !!!", language_priority=["mixed"]) == LanguageCode.MIXED


def test_detect_language_default_fallback():
    """Verifies default fallback to EN when no priority list or empty priority is provided."""
    assert detect_language("") == LanguageCode.EN
    assert detect_language("   ") == LanguageCode.EN
    assert detect_language("12345") == LanguageCode.EN
    assert detect_language("12345", language_priority=[]) == LanguageCode.EN
    assert detect_language("12345", language_priority=["unknown_lang"]) == LanguageCode.EN


def test_detect_language_avoid_false_positives_in_english():
    """Verifies that English words containing Roman Urdu substrings are not misclassified."""
    queries = [
        "Does your salon cut hair?",  # 'hair' contains 'hai'
        "Is this a retail chain?",  # 'chain' contains 'hai'
        "What is the main service?",  # 'main' contains 'hai'
        "I accept your sincere apology.",  # 'apology' contains 'ap'
        "When do you open tomorrow?",  # 'open' contains 'pe'
        "I would like to book a table.",
        "What is the best way to contact you?",
    ]
    for q in queries:
        assert detect_language(q) == LanguageCode.EN, f"False positive for English query: {q}"
