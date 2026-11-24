/**
 * AgentDesk Agent Configuration API Client.
 * Provides typed HTTP functions for querying and updating agent configuration.
 */

import { apiClient, type ApiClient } from "./client";
import type { AgentConfigResponse, AgentConfigUpdate } from "@/types/agents";

/**
 * Retrieves the agent configuration for the authenticated business.
 * Endpoint: GET /api/v1/agents/config
 * Derives business context strictly from session authentication cookies.
 */
export async function getAgentConfig(
  options: { client?: ApiClient } = {}
): Promise<AgentConfigResponse> {
  const client = options.client || apiClient;
  return client.getAgentConfig();
}

/**
 * Updates agent configuration using HTTP PUT.
 * Endpoint: PUT /api/v1/agents/config
 */
export async function updateAgentConfig(
  payload: AgentConfigUpdate,
  options: { client?: ApiClient } = {}
): Promise<AgentConfigResponse> {
  const client = options.client || apiClient;
  return client.updateAgentConfig(payload);
}

/**
 * Updates agent configuration using HTTP PATCH.
 * Endpoint: PATCH /api/v1/agents/config
 */
export async function patchAgentConfig(
  payload: AgentConfigUpdate,
  options: { client?: ApiClient } = {}
): Promise<AgentConfigResponse> {
  const client = options.client || apiClient;
  return client.patchAgentConfig(payload);
}

