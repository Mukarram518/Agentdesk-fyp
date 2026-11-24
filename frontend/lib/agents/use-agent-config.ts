"use client";

import { useContext, useEffect, useMemo, useSyncExternalStore } from "react";
import type { AgentConfigResponse, AgentConfigUpdate } from "@/types/agents";
import { AgentConfigStore, type AgentConfigState } from "./agent-config-store";
import { BusinessContext } from "@/lib/business/BusinessContext";
import type { ApiClient } from "@/lib/api/client";

export interface UseAgentConfigOptions {
  /**
   * Explicit business ID to manage.
   * If omitted, defaults dynamically to the active `currentBusiness` from `BusinessContext`.
   */
  businessId?: string | null;
  /**
   * Optional custom ApiClient instance (e.g. for testing or isolated sessions).
   */
  client?: ApiClient;
  /**
   * Whether to automatically fetch configuration on mount or when the business changes.
   * Defaults to true.
   */
  autoFetch?: boolean;
  /**
   * Optional custom AgentConfigStore instance (useful for unit testing and state sharing).
   */
  store?: AgentConfigStore;
}

export interface UseAgentConfigReturn {
  config: AgentConfigResponse | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  fetchConfig: () => Promise<AgentConfigResponse | null>;
  updateConfig: (payload: AgentConfigUpdate) => Promise<AgentConfigResponse>;
  patchConfig: (payload: AgentConfigUpdate) => Promise<AgentConfigResponse>;
  clearError: () => void;
  reset: () => void;
  store: AgentConfigStore;
}

/**
 * Reusable React hook for business AgentConfig state management.
 * Provides typed access to configuration fetching, saving, partial patching,
 * business switching synchronization, and error handling.
 */
export function useAgentConfig(options: UseAgentConfigOptions = {}): UseAgentConfigReturn {
  const {
    businessId: explicitBusinessId,
    client,
    autoFetch = true,
    store: injectedStore,
  } = options;

  const businessContext = useContext(BusinessContext);
  const resolvedBusinessId =
    explicitBusinessId !== undefined
      ? explicitBusinessId
      : (businessContext?.currentBusiness?.id ?? null);

  const store = useMemo(() => {
    return (
      injectedStore ??
      new AgentConfigStore({
        businessId: resolvedBusinessId,
        client,
      })
    );
  }, [injectedStore, resolvedBusinessId, client]);

  // Synchronize store business ID whenever the resolved business ID changes
  useEffect(() => {
    if (store.getBusinessId() !== resolvedBusinessId) {
      store.setBusinessId(resolvedBusinessId, autoFetch);
    } else if (
      autoFetch &&
      resolvedBusinessId &&
      !store.getSnapshot().config &&
      !store.getSnapshot().isLoading &&
      !store.getSnapshot().error
    ) {
      void store.fetchConfig().catch(() => {});
    }
  }, [store, resolvedBusinessId, autoFetch]);

  const state: AgentConfigState = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot
  );

  return {
    config: state.config,
    isLoading: state.isLoading,
    isSaving: state.isSaving,
    error: state.error,
    fetchConfig: store.fetchConfig,
    updateConfig: store.updateConfig,
    patchConfig: store.patchConfig,
    clearError: store.clearError,
    reset: store.reset,
    store,
  };
}
