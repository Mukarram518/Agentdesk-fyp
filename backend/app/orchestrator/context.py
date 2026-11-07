"""Context builder for assembling tenant-scoped Business Brain context."""

from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.orchestrator.language import detect_language
from app.orchestrator.prompts import (
    build_llm_messages,
    build_system_prompt,
    format_retrieved_knowledge,
)
from app.orchestrator.schemas import (
    AgentConfig,
    AgentTurnInput,
    ChannelType,
    LanguageCode,
)
from app.providers.llm.schemas import ChatMessage
from app.repositories.business_repository import (
    BusinessRepository,
    business_repository as default_business_repo,
)
from app.services.knowledge_service import (
    KnowledgeService,
    knowledge_service as default_knowledge_service,
)


DEFAULT_MAX_HISTORY_TURNS = 8
DEFAULT_KNOWLEDGE_TOP_K = 5
DEFAULT_KNOWLEDGE_SCORE_THRESHOLD = 0.35


class RetrievedKnowledgeItem(BaseModel):
    """Pydantic representation of a retrieved knowledge entry for AI context."""

    id: uuid.UUID
    question: Optional[str] = None
    answer: str
    source_type: str = "FAQ"
    score: float = 0.0
    tags: List[Any] = Field(default_factory=list)
    section_title: Optional[str] = None


class OrchestratorContext(BaseModel):
    """Encapsulates the complete Business Brain context for an orchestrator turn."""

    business_id: uuid.UUID
    business_name: str
    business_slug: Optional[str] = None
    channel: ChannelType
    language: LanguageCode
    agent_config: AgentConfig
    current_message: str
    conversation_id: Optional[uuid.UUID] = None
    customer_id: Optional[str] = None
    recent_history: List[ChatMessage] = Field(default_factory=list)
    retrieved_knowledge: List[RetrievedKnowledgeItem] = Field(default_factory=list)
    source_ids: List[uuid.UUID] = Field(default_factory=list)
    system_prompt: str
    messages: List[ChatMessage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextBuilder:
    """Builds tenant-isolated Business Brain context and guardrailed prompts."""

    def __init__(
        self,
        knowledge_service: Optional[KnowledgeService] = None,
        business_repo: Optional[BusinessRepository] = None,
        max_history_turns: int = DEFAULT_MAX_HISTORY_TURNS,
        knowledge_top_k: int = DEFAULT_KNOWLEDGE_TOP_K,
        knowledge_score_threshold: float = DEFAULT_KNOWLEDGE_SCORE_THRESHOLD,
    ) -> None:
        self.knowledge_service = knowledge_service or default_knowledge_service
        self.business_repo = business_repo or default_business_repo
        self.max_history_turns = max_history_turns
        self.knowledge_top_k = knowledge_top_k
        self.knowledge_score_threshold = knowledge_score_threshold

    async def build(
        self,
        db: AsyncSession,
        turn_input: AgentTurnInput,
        agent_config: Optional[AgentConfig] = None,
        business: Optional[Business] = None,
    ) -> OrchestratorContext:
        """Constructs the complete tenant-scoped orchestrator context.

        Guarantees:
        1. Tenant scoping: Queries strictly using turn_input.business_id.
        2. Safe business resolution: Fetches business or falls back safely without crashing.
        3. Deterministic language detection: Uses turn_input.language or detects from message.
        4. Safe knowledge retrieval: Calls knowledge_service.search_knowledge with top_k=5, score_threshold=0.35.
        5. Preserves source IDs: Keeps UUIDs of returned entries for later output population.
        6. Limits history: Truncates history to max_history_turns (default 8).
        7. Guardrailed prompts: Formats untrusted content with boundary delimiters.
        8. Zero DB mutations: Pure read operations; no writes or persistence.
        """
        # 1. Enforce tenant ID from turn_input
        business_id = turn_input.business_id
        if not business_id or not isinstance(business_id, uuid.UUID):
            raise ValueError("A valid business_id is required.")

        # 2. Resolve Business Profile
        business_name = "AgentDesk Business"
        business_slug: Optional[str] = None

        if business is not None:
            if business.id != business_id:
                raise ValueError(
                    f"Supplied business id '{business.id}' does not match turn_input.business_id '{business_id}'."
                )
            business_name = business.name
            business_slug = business.slug
        else:
            try:
                fetched_business = await self.business_repo.get_by_id(db, business_id)
                if fetched_business is not None:
                    business_name = fetched_business.name
                    business_slug = fetched_business.slug
                else:
                    business_name = turn_input.metadata.get("business_name", "AgentDesk Business")
                    business_slug = turn_input.metadata.get("business_slug", None)
            except Exception:
                business_name = turn_input.metadata.get("business_name", "AgentDesk Business")
                business_slug = turn_input.metadata.get("business_slug", None)

        # 3. Resolve Agent Configuration
        effective_config = agent_config or AgentConfig(business_id=business_id)
        if effective_config.business_id is None:
            effective_config.business_id = business_id

        # 4. Resolve Language
        if turn_input.language is not None:
            effective_language = turn_input.language
        else:
            effective_language = detect_language(
                turn_input.message,
                language_priority=effective_config.language_priority,
            )

        # 5. Semantic Knowledge Retrieval
        retrieved_items: List[RetrievedKnowledgeItem] = []
        source_ids: List[uuid.UUID] = []

        try:
            raw_knowledge = await self.knowledge_service.search_knowledge(
                db=db,
                business_id=business_id,
                query=turn_input.message,
                top_k=self.knowledge_top_k,
                score_threshold=self.knowledge_score_threshold,
            )
        except Exception:
            raw_knowledge = []

        for entry, score in (raw_knowledge or []):
            item = RetrievedKnowledgeItem(
                id=entry.id,
                question=entry.question,
                answer=entry.answer,
                source_type=getattr(entry, "source_type", "FAQ"),
                score=float(score) if score is not None else 0.0,
                tags=list(getattr(entry, "tags", []) or []),
                section_title=getattr(entry, "section_title", None),
            )
            retrieved_items.append(item)
            source_ids.append(entry.id)

        # 6. History Truncation (conservative limit of 8 turns)
        recent_history: List[ChatMessage] = []
        if turn_input.history:
            recent_history = list(turn_input.history[-self.max_history_turns:])

        # 7. Construct Guardrailed System Prompt and Messages
        knowledge_str = format_retrieved_knowledge(retrieved_items)
        system_prompt = build_system_prompt(
            business_name=business_name,
            business_slug=business_slug,
            agent_config=effective_config,
            language=effective_language,
            channel=turn_input.channel,
            retrieved_knowledge_str=knowledge_str,
        )

        messages = build_llm_messages(
            system_prompt=system_prompt,
            recent_history=recent_history,
            current_message=turn_input.message,
            max_history_turns=self.max_history_turns,
        )

        # 8. Return Structured Context
        return OrchestratorContext(
            business_id=business_id,
            business_name=business_name,
            business_slug=business_slug,
            channel=turn_input.channel,
            language=effective_language,
            agent_config=effective_config,
            current_message=turn_input.message,
            conversation_id=turn_input.conversation_id,
            customer_id=turn_input.customer_id,
            recent_history=recent_history,
            retrieved_knowledge=retrieved_items,
            source_ids=source_ids,
            system_prompt=system_prompt,
            messages=messages,
            metadata=turn_input.metadata,
        )


async def build_orchestrator_context(
    db: AsyncSession,
    turn_input: AgentTurnInput,
    agent_config: Optional[AgentConfig] = None,
    business: Optional[Business] = None,
    knowledge_service: Optional[KnowledgeService] = None,
    business_repo: Optional[BusinessRepository] = None,
    max_history_turns: int = DEFAULT_MAX_HISTORY_TURNS,
    knowledge_top_k: int = DEFAULT_KNOWLEDGE_TOP_K,
    knowledge_score_threshold: float = DEFAULT_KNOWLEDGE_SCORE_THRESHOLD,
) -> OrchestratorContext:
    """Convenience helper for building orchestrator context."""
    builder = ContextBuilder(
        knowledge_service=knowledge_service,
        business_repo=business_repo,
        max_history_turns=max_history_turns,
        knowledge_top_k=knowledge_top_k,
        knowledge_score_threshold=knowledge_score_threshold,
    )
    return await builder.build(
        db=db,
        turn_input=turn_input,
        agent_config=agent_config,
        business=business,
    )

