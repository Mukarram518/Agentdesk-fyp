"""AgentDesk AI Orchestrator module."""

from app.orchestrator.context import (
    ContextBuilder,
    OrchestratorContext,
    RetrievedKnowledgeItem,
    build_orchestrator_context,
)
from app.orchestrator.language import detect_language
from app.orchestrator.prompts import (
    build_llm_messages,
    build_system_prompt,
    format_retrieved_knowledge,
)
from app.orchestrator.routing import detect_intent, select_agent
from app.orchestrator.schemas import (
    AgentConfig,
    AgentTurnInput,
    AgentTurnOutput,
    AgentType,
    ChannelType,
    IntentType,
    LanguageCode,
)
from app.orchestrator.service import AIOrchestrator

__all__ = [
    "AIOrchestrator",
    "AgentConfig",
    "AgentTurnInput",
    "AgentTurnOutput",
    "AgentType",
    "ChannelType",
    "ContextBuilder",
    "IntentType",
    "LanguageCode",
    "OrchestratorContext",
    "RetrievedKnowledgeItem",
    "build_llm_messages",
    "build_orchestrator_context",
    "build_system_prompt",
    "detect_intent",
    "detect_language",
    "format_retrieved_knowledge",
    "select_agent",
]
