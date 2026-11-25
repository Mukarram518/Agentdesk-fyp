"use client";

import React, { useContext, useState } from "react";
import { KnowledgeStore } from "./knowledge-store";
import {
  KnowledgeContext,
  useKnowledge,
  type UseKnowledgeReturn,
} from "./use-knowledge";
import { BusinessContext } from "@/lib/business/BusinessContext";
import type { ApiClient } from "@/lib/api/client";

export { KnowledgeContext };

export interface KnowledgeProviderProps {
  children?: React.ReactNode;
  businessId?: string | null;
  client?: ApiClient;
  store?: KnowledgeStore;
  autoFetch?: boolean;
  autoPoll?: boolean;
  pollIntervalMs?: number;
}

/**
 * KnowledgeProvider manages a single shared KnowledgeStore and polling lifecycle
 * for all child Knowledge Base components.
 *
 * Guarantees:
 * 1. Single shared store instance across tabs (FAQs, Documents, Semantic Search).
 * 2. Avoids duplicate polling intervals by running a single polling loop.
 * 3. Preserves active-business synchronization with BusinessContext.
 * 4. Cleans up background intervals and listeners on unmount.
 * 5. Prevents cross-tenant state leakage on business switch.
 */
export function KnowledgeProvider({
  children,
  businessId: propBusinessId,
  client,
  store: propStore,
  autoFetch = true,
  autoPoll = true,
  pollIntervalMs = 3000,
}: KnowledgeProviderProps) {
  const businessContext = useContext(BusinessContext);
  const resolvedBusinessId =
    propBusinessId !== undefined
      ? propBusinessId
      : (businessContext?.currentBusiness?.id ?? null);

  // Stable single store instance per provider lifecycle
  const [internalStore] = useState(
    () =>
      new KnowledgeStore({
        businessId: resolvedBusinessId,
        client,
      })
  );
  const store = propStore ?? internalStore;

  const knowledge = useKnowledge({
    store,
    businessId: resolvedBusinessId,
    client,
    autoFetch,
    autoPoll,
    pollIntervalMs,
  });

  return (
    <KnowledgeContext.Provider value={knowledge}>
      {children}
    </KnowledgeContext.Provider>
  );
}

/**
 * Hook to consume the shared KnowledgeContext.
 * Throws a helpful error if used outside KnowledgeProvider.
 */
export function useKnowledgeContext(): UseKnowledgeReturn {
  const context = useContext(KnowledgeContext);
  if (!context) {
    throw new Error(
      "useKnowledgeContext must be used within a <KnowledgeProvider>. " +
      "Wrap your component tree in <KnowledgeProvider> or use standalone useKnowledge()."
    );
  }
  return context;
}
