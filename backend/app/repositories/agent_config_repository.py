"""Forwarding module alias for agent_config repository."""

from app.repositories.agent_config import (
    AgentConfigRepository,
    agent_config_repository,
)

__all__ = ["AgentConfigRepository", "agent_config_repository"]

