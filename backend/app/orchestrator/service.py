"""AI Orchestrator service coordinating routing, context building, and LLM inference."""

import logging
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.business import Business
from app.orchestrator.context import ContextBuilder, OrchestratorContext
from app.orchestrator.language import detect_language
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
from app.providers.llm import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    get_llm_provider,
)


# Safe customer-facing fallback messages per language
FALLBACK_RESPONSES = {
    LanguageCode.EN: (
        "I apologize, but I am currently having difficulty processing your request. "
        "Please try again shortly or contact our team directly."
    ),
    LanguageCode.UR: (
        "معذرت، میں اس وقت آپ کی درخواست پر عمل کرنے سے قاصر ہوں۔ "
        "براہ کرم کچھ دیر بعد کوشش کریں یا ہماری ٹیم سے رابطہ کریں۔"
    ),
    LanguageCode.MIXED: (
        "Maazrat, is waqt aap ki request process nahi ho saki. "
        "Barah-e-karam thori der baad koshish karein ya hamari team se direct rabta karein."
    ),
}


class AIOrchestrator:
    """Central AI coordination engine for AgentDesk multi-agent platform.

    The orchestrator provides a single shared business brain across all agents
    (Chat, Lead, Booking, Voice) and communication channels (Web, WhatsApp, Voice).

    Architectural boundaries:
    - Layer: Service layer (invoked by API routes or background channels).
    - Stateless execution: accepts AgentTurnInput, returns validated AgentTurnOutput.
    - Zero direct DB mutations: does not persist conversation records or message logs in Phase 6.2.
    - Zero tool execution: captures requested tool calls without executing arbitrary code.
    - Zero external SDK coupling: interacts solely through the abstract LLMProvider contract.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        context_builder: Optional[ContextBuilder] = None,
    ) -> None:
        """Initializes the orchestrator with required provider and context services.

        Args:
            llm_provider: Concrete LLMProvider (Mock or Groq). Defaults to factory provider.
            context_builder: ContextBuilder service for RAG retrieval and prompt formatting.
        """
        self.llm_provider = llm_provider or get_llm_provider()
        self.context_builder = context_builder or ContextBuilder()

    async def handle_turn(
        self,
        db: AsyncSession,
        turn_input: AgentTurnInput,
        agent_config: Optional[AgentConfig] = None,
        business: Optional[Business] = None,
    ) -> AgentTurnOutput:
        """Processes a single conversational turn through the AI orchestration pipeline.

        Execution pipeline:
        1. Tenant identity enforcement: turn_input.business_id must be non-empty and valid.
        2. Language resolution: detects language or uses explicit turn_input.language.
        3. Intent & Agent routing: detects intent and selects active agent based on channel and config.
        4. Context building: Constructs tenant-scoped Business Brain context and guardrailed prompt.
        5. LLM execution: Invokes LLMProvider without coupling to SDK specifics.
        6. Tool call boundary: Captures requested tool calls safely without executing tools in Phase 6.2.
        7. Source preservation: Preserves retrieved knowledge UUIDs into AgentTurnOutput.sources.
        8. Token usage: Preserves token usage metadata when returned by provider.
        9. Exception safety: Never leaks internal stack traces, API keys, or database errors.
        10. Zero DB mutations: Pure read operations; no writes or persistence.
        """
        # 1. Enforce authorized tenant identity
        business_id = turn_input.business_id
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("A valid business_id is required.")

        # 2. Resolve Agent Configuration
        effective_config = agent_config or AgentConfig(business_id=business_id)
        if effective_config.business_id is None:
            effective_config.business_id = business_id

        # 3. Resolve Language
        if turn_input.language is not None:
            effective_language = turn_input.language
        else:
            effective_language = detect_language(
                turn_input.message,
                language_priority=effective_config.language_priority,
            )

        # 4. Intent Detection & Agent Selection
        intent: IntentType = detect_intent(turn_input.message)
        agent: AgentType = select_agent(
            intent=intent,
            channel=turn_input.channel,
            agent_config=effective_config,
        )

        logger.info(
            f"Orchestrator turn initiated for business={business_id} "
            f"channel={turn_input.channel.value} language={effective_language.value} "
            f"intent={intent.value} agent={agent.value}"
        )

        # 5. Build Tenant-Scoped Context
        # Ensure turn_input carries the resolved language for downstream context
        turn_input_with_lang = turn_input.model_copy(update={"language": effective_language})
        context: OrchestratorContext = await self.context_builder.build(
            db=db,
            turn_input=turn_input_with_lang,
            agent_config=effective_config,
            business=business,
        )

        # 6. LLM Inference Execution with Safe Fallback
        provider = self.llm_provider
        try:
            response: LLMResponse = await provider.generate(
                messages=context.messages,
                temperature=0.3,
            )
        except LLMProviderError as exc:
            logger.warning(
                f"LLM provider generation error during orchestrator turn: {exc.message} "
                f"(provider={provider.provider_name})"
            )
            fallback_msg = FALLBACK_RESPONSES.get(
                effective_language,
                FALLBACK_RESPONSES[LanguageCode.EN],
            )
            return AgentTurnOutput(
                response=fallback_msg,
                language=effective_language,
                intent=intent,
                agent=agent,
                tool_calls=[],
                confidence=0.0,
                sources=context.source_ids,
                usage=None,
                metadata={
                    "error": exc.message,
                    "error_type": type(exc).__name__,
                    "provider": provider.provider_name,
                    "fallback": True,
                },
            )
        except Exception as exc:
            logger.error(f"Unexpected error during orchestrator LLM call: {exc}")
            fallback_msg = FALLBACK_RESPONSES.get(
                effective_language,
                FALLBACK_RESPONSES[LanguageCode.EN],
            )
            return AgentTurnOutput(
                response=fallback_msg,
                language=effective_language,
                intent=intent,
                agent=agent,
                tool_calls=[],
                confidence=0.0,
                sources=context.source_ids,
                usage=None,
                metadata={
                    "error": "Internal processing error",
                    "provider": provider.provider_name,
                    "fallback": True,
                },
            )

        # 7. Response Text Normalization
        response_text = (response.content or "").strip()
        if not response_text:
            if response.tool_calls:
                # Model requested tool actions without conversational text
                tool_names = ", ".join(tc.function.name for tc in response.tool_calls)
                response_text = f"Action requested: {tool_names}"
            else:
                response_text = FALLBACK_RESPONSES.get(
                    effective_language,
                    FALLBACK_RESPONSES[LanguageCode.EN],
                )

        # 8. Tool Call Handling Boundary (Phase 6.2: do not execute tools)
        if response.tool_calls:
            logger.info(
                f"Model returned {len(response.tool_calls)} tool call(s) for agent={agent.value}. "
                "Tool execution is disabled in Phase 6.2; passing through to turn output."
            )

        # 9. Compute Confidence Score
        confidence: Optional[float] = None
        if context.retrieved_knowledge:
            # Cosine distance: closer to 0.0 means higher similarity
            best_distance = context.retrieved_knowledge[0].score
            confidence = round(max(0.0, min(1.0, 1.0 - best_distance)), 4)
        elif intent != IntentType.UNKNOWN:
            confidence = 0.85
        else:
            confidence = 0.50

        # 10. Assemble and Validate AgentTurnOutput
        metadata = dict(turn_input.metadata)
        metadata.update({
            "model": response.model or provider.model_name,
            "provider": response.provider or provider.provider_name,
            "finish_reason": response.finish_reason,
        })

        return AgentTurnOutput(
            response=response_text,
            language=effective_language,
            intent=intent,
            agent=agent,
            tool_calls=response.tool_calls,
            confidence=confidence,
            sources=context.source_ids,
            usage=response.usage,
            metadata=metadata,
        )
