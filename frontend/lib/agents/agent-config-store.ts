/**
 * AgentDesk Agent Configuration Store.
 * Centralized, observable state store for business AI agent configuration.
 *
 * Guarantees:
 * 1. Business-tenant scoped state lifecycle (resets on business switch or logout).
 * 2. Stale-response protection across asynchronous network calls.
 * 3. Atomic transition handling for loading, saving, and error states.
 * 4. SSR-safe snapshot caching for useSyncExternalStore.
 */

import type { AgentConfigResponse, AgentConfigUpdate } from "@/types/agents";
import { apiClient, ApiHttpError, isApiClientError, type ApiClient } from "@/lib/api/client";

export interface AgentConfigState {
  config: AgentConfigResponse | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
}

export const INITIAL_AGENT_CONFIG_STATE: AgentConfigState = Object.freeze({
  config: null,
  isLoading: false,
  isSaving: false,
  error: null,
});

/**
 * Extracts a human-readable error message from an API error or exception.
 */
export function extractApiErrorMessage(
  error: unknown,
  fallback = "An unexpected error occurred."
): string {
  if (error instanceof ApiHttpError) {
    if (error.data && typeof error.data === "object") {
      const payload = error.data as Record<string, unknown>;
      if (typeof payload.detail === "string") {
        return payload.detail;
      }
      if (Array.isArray(payload.detail) && payload.detail.length > 0) {
        const first = payload.detail[0];
        if (first && typeof first === "object" && "msg" in first) {
          return String(first.msg);
        }
      }
      if (typeof payload.message === "string") {
        return payload.message;
      }
    }
    return error.message || fallback;
  }
  if (isApiClientError(error) || error instanceof Error) {
    return error.message;
  }
  return fallback;
}

export interface AgentConfigStoreOptions {
  client?: ApiClient;
  businessId?: string | null;
}

export class AgentConfigStore {
  private state: AgentConfigState;
  private listeners = new Set<() => void>();
  private activeRequestId = 0;
  private currentBusinessId: string | null = null;
  private client: ApiClient;

  constructor(options: AgentConfigStoreOptions = {}) {
    this.client = options.client || apiClient;
    this.state = INITIAL_AGENT_CONFIG_STATE;
    this.currentBusinessId = options.businessId ?? null;
  }

  getSnapshot = (): AgentConfigState => {
    return this.state;
  };

  getServerSnapshot = (): AgentConfigState => {
    return INITIAL_AGENT_CONFIG_STATE;
  };

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private setState(partial: Partial<AgentConfigState>): void {
    this.state = { ...this.state, ...partial };
    for (const listener of this.listeners) {
      listener();
    }
  }

  /**
   * Returns the currently tracked business ID.
   */
  getBusinessId(): string | null {
    return this.currentBusinessId;
  }

  /**
   * Synchronizes the active business ID.
   * If the business changes or becomes null/undefined:
   * - Immediately cancels in-flight operations.
   * - Resets configuration state to prevent stale cross-tenant leakage.
   * - Optionally triggers automatic fetch for the new business.
   */
  setBusinessId = (businessId: string | null | undefined, autoFetch = true): void => {
    const nextId = businessId && businessId.trim() ? businessId.trim() : null;
    if (this.currentBusinessId === nextId) {
      return;
    }

    // Invalidate any in-flight requests from the previous business context
    this.activeRequestId++;
    this.currentBusinessId = nextId;

    if (!nextId) {
      this.setState({
        config: null,
        isLoading: false,
        isSaving: false,
        error: null,
      });
      return;
    }

    // Reset state for new business
    this.setState({
      config: null,
      isLoading: false,
      isSaving: false,
      error: null,
    });

    if (autoFetch) {
      this.fetchConfig().catch(() => {
        // Errors are stored in state.error
      });
    }
  };

  /**
   * Fetches the agent configuration for the active business.
   * Prevents stale responses from overwriting newer requests.
   */
  fetchConfig = async (): Promise<AgentConfigResponse | null> => {
    if (!this.currentBusinessId) {
      this.setState({
        config: null,
        isLoading: false,
        error: null,
      });
      return null;
    }

    const reqId = ++this.activeRequestId;
    const targetBusinessId = this.currentBusinessId;

    this.setState({ isLoading: true, error: null });

    try {
      const config = await this.client.getAgentConfig();

      // Guard against stale response or business switch
      if (reqId !== this.activeRequestId || this.currentBusinessId !== targetBusinessId) {
        return null;
      }

      this.setState({
        config,
        isLoading: false,
        error: null,
      });
      return config;
    } catch (err: unknown) {
      // Guard against stale error
      if (reqId !== this.activeRequestId || this.currentBusinessId !== targetBusinessId) {
        return null;
      }

      const errorMessage = extractApiErrorMessage(err, "Failed to load agent configuration.");
      this.setState({
        isLoading: false,
        error: errorMessage,
      });
      return null;
    }
  };

  /**
   * Updates agent configuration using HTTP PUT.
   */
  updateConfig = async (payload: AgentConfigUpdate): Promise<AgentConfigResponse> => {
    if (!this.currentBusinessId) {
      const err = new Error("No active business selected to update configuration.");
      this.setState({ error: err.message, isSaving: false });
      throw err;
    }

    const reqId = ++this.activeRequestId;
    const targetBusinessId = this.currentBusinessId;

    this.setState({ isSaving: true, error: null });

    try {
      const updated = await this.client.updateAgentConfig(payload);

      // Guard against stale response if user switched business during save
      if (reqId !== this.activeRequestId || this.currentBusinessId !== targetBusinessId) {
        return updated;
      }

      this.setState({
        config: updated,
        isSaving: false,
        error: null,
      });
      return updated;
    } catch (err: unknown) {
      if (reqId !== this.activeRequestId || this.currentBusinessId !== targetBusinessId) {
        throw err;
      }

      const errorMessage = extractApiErrorMessage(err, "Failed to update agent configuration.");
      this.setState({
        isSaving: false,
        error: errorMessage,
      });
      throw err;
    }
  };

  /**
   * Partially updates agent configuration using HTTP PATCH.
   */
  patchConfig = async (payload: AgentConfigUpdate): Promise<AgentConfigResponse> => {
    if (!this.currentBusinessId) {
      const err = new Error("No active business selected to update configuration.");
      this.setState({ error: err.message, isSaving: false });
      throw err;
    }

    const reqId = ++this.activeRequestId;
    const targetBusinessId = this.currentBusinessId;

    this.setState({ isSaving: true, error: null });

    try {
      const updated = await this.client.patchAgentConfig(payload);

      // Guard against stale response if user switched business during save
      if (reqId !== this.activeRequestId || this.currentBusinessId !== targetBusinessId) {
        return updated;
      }

      this.setState({
        config: updated,
        isSaving: false,
        error: null,
      });
      return updated;
    } catch (err: unknown) {
      if (reqId !== this.activeRequestId || this.currentBusinessId !== targetBusinessId) {
        throw err;
      }

      const errorMessage = extractApiErrorMessage(err, "Failed to patch agent configuration.");
      this.setState({
        isSaving: false,
        error: errorMessage,
      });
      throw err;
    }
  };

  /**
   * Clears any active error state.
   */
  clearError = (): void => {
    if (this.state.error !== null) {
      this.setState({ error: null });
    }
  };

  /**
   * Resets the entire store to its initial empty state.
   */
  reset = (): void => {
    this.activeRequestId++;
    this.setState(INITIAL_AGENT_CONFIG_STATE);
  };
}

