"""Deterministic keyword and rule-based intent routing for the AI Orchestrator."""

import re
from typing import Optional

from app.orchestrator.schemas import (
    AgentConfig,
    AgentType,
    ChannelType,
    IntentType,
)


# 1. Lead / Buying Intent Patterns (English, Roman Urdu, Native Urdu)
# Checked before appointment so fee/cost inquiries (e.g., 'consultation fee') route to Lead
LEAD_REGEX = re.compile(
    r"\b(?:"
    # English
    r"buy|buying|purchase|purchasing|price|pricing|cost|costs|package|packages|quote|quotation|hire|order|ordering|fee|fees|charges|rate|rates|"
    # Roman Urdu
    r"kharidna|kharidne|kharid|keemat|qimat|dam|daam|"
    r"price\s+kya|cost\s+kitni|charges\s+kya|fee\s+kitni|fees\s+kitni|rate\s+kya"
    r")\b|"
    # Native Urdu script
    r"[\u0600-\u06FF]*(?:خریدنا|خریداری|قیمت|قیمتیں|نرخ|پیکیج|پیکج|پیکیجز|چارجز|فیس|آرڈر)[\u0600-\u06FF]*",
    re.IGNORECASE,
)

# 2. Appointment Patterns (English, Roman Urdu, Native Urdu)
APPOINTMENT_REGEX = re.compile(
    r"\b(?:"
    # English
    r"appointment|appointments|book|booking|schedule|scheduling|consultation|meeting|slot|slots|reschedule|reserve|reservation|"
    # Roman Urdu
    r"mulaqat|mulaqaat|rabta karna|waqt chahiye|time chahiye|"
    # Common collocations like 'book karwana', 'mil sakti hai'
    r"book\s+(?:karwa|karna|karein|karen|karwana)|"
    r"mil\s+(?:sakti|sakta|sakte)\s+hai|"
    r"available\s+hai"
    r")\b|"
    # Native Urdu script
    r"[\u0600-\u06FF]*(?:اپائنٹمنٹ|بکنگ|بک|مشاورت|میٹنگ|شیڈول|ملاقات|ریزرویشن|سلاٹ|سلاٹس|دستیاب)[\u0600-\u06FF]*",
    re.IGNORECASE,
)

# 3. Informational / FAQ Patterns (English, Roman Urdu, Native Urdu)
# Focused on business domain concepts, omitting standalone conversational interrogatives
FAQ_REGEX = re.compile(
    r"\b(?:"
    # English
    r"hours|timings|timing|open|opening|close|closing|closed|location|located|address|services|service|policy|policies|refund|refunds|support|information|info|details|where|when|clinic|office|company|"
    # Roman Urdu
    r"kab|kahan|kaha|kidhar|khulta|khulti|khulte|auqat|waqt|pata|rabta|madad|maloomat|daftar|clinic"
    r")\b|"
    # Native Urdu script
    r"[\u0600-\u06FF]*(?:کہاں|کب|کیوں|اوقات|وقت|کھلتا|کھلتی|بند|پتہ|خدمات|رابطہ|مدد|معلومات|پالیسی|دفتر|کلینک|کمپنی)[\u0600-\u06FF]*",
    re.IGNORECASE,
)

# 4. General Conversation / Pleasantry Patterns (English, Roman Urdu, Native Urdu)
GENERAL_REGEX = re.compile(
    r"\b(?:"
    # English
    r"hello|hi|hey|greetings|good\s+morning|good\s+afternoon|good\s+evening|how\s+are\s+you|thank\s+you|thanks|bye|goodbye|"
    # Roman Urdu
    r"salam|assalam|assalamu|walaikum|kya\s+haal|kaise\s+ho|kese\s+ho|kaise\s+hain|kese\s+hain|shukriya|shukria|mehrbani|khuda\s+hafiz|allah\s+hafiz"
    r")\b|"
    # Native Urdu script
    r"[\u0600-\u06FF]*(?:سلام|السلام|وعلیکم|کیسے\s+ہیں|کیا\s+حال|شکریہ|مہربانی|اللہ\s+حافظ|خدا\s+حافظ)[\u0600-\u06FF]*",
    re.IGNORECASE,
)


def detect_intent(message: str) -> IntentType:
    """Deterministically detects customer intent from input message.

    Priority hierarchy:
    1. LEAD (Buying intent, pricing inquiries, package questions, fees)
    2. APPOINTMENT (Explicit booking, meeting, or scheduling requests)
    3. FAQ (Informational inquiries about business, hours, services)
    4. GENERAL (Greetings, polite pleasantries, gratitude, farewells)
    5. UNKNOWN (Unmatched, ambiguous, or empty input)
    """
    cleaned = message.strip()
    if not cleaned:
        return IntentType.UNKNOWN

    # Priority 1: Buying / Lead Intent (takes precedence on fee/pricing inquiries)
    if LEAD_REGEX.search(cleaned):
        return IntentType.LEAD

    # Priority 2: Appointment & Booking Intent
    if APPOINTMENT_REGEX.search(cleaned):
        return IntentType.APPOINTMENT

    # Priority 3: Informational / FAQ Intent
    if FAQ_REGEX.search(cleaned):
        return IntentType.FAQ

    # Priority 4: General Greeting & Pleasantry Intent
    if GENERAL_REGEX.search(cleaned):
        return IntentType.GENERAL

    # Priority 5: Fallback to Unknown Intent
    return IntentType.UNKNOWN


def select_agent(
    intent: IntentType,
    channel: ChannelType,
    agent_config: Optional[AgentConfig] = None,
) -> AgentType:
    """Selects the active agent based on intent, channel, and agent configuration.

    Rules:
    - If channel is VOICE and voice_enabled is True: AgentType.VOICE
    - If intent is APPOINTMENT: AgentType.BOOKING
    - If intent is LEAD:
        - If lead_enabled is True: AgentType.LEAD
        - If lead_enabled is False: AgentType.CHAT (fallback to chat)
    - If intent is FAQ, GENERAL, or UNKNOWN: AgentType.CHAT
    """
    config = agent_config or AgentConfig()

    # Rule 1: Voice Channel handling
    if channel == ChannelType.VOICE and config.voice_enabled:
        return AgentType.VOICE

    # Rule 2: Appointment Intent
    if intent == IntentType.APPOINTMENT:
        return AgentType.BOOKING

    # Rule 3: Lead Intent (respects lead_enabled configuration)
    if intent == IntentType.LEAD:
        if config.lead_enabled:
            return AgentType.LEAD
        return AgentType.CHAT

    # Rule 4: FAQ, General conversation, and Unknown fallback
    return AgentType.CHAT
