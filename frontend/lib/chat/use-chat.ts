"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import type { ChatStatus, ChatUIMessage } from "@/types/chat";
import { ChatStore } from "./chat-state";
import type { ApiClient } from "@/lib/api/client";

export interface UseChatOptions {
  businessId?: string;
  autoBootstrapToken?: boolean;
  client?: ApiClient;
}

export interface UseChatReturn {
  messages: ChatUIMessage[];
  conversationId: string | null;
  status: ChatStatus;
  isSending: boolean;
  error: string | null;
  canRetry: boolean;
  sendMessage: (content: string) => Promise<void>;
  retryLastMessage: () => Promise<void>;
  clearConversation: () => void;
  refreshToken: () => Promise<string>;
}

/**
 * Reusable React hook for dashboard preview chat.
 * Coordinates token management, message dispatch, optimistic updates, and retries.
 */
export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const { businessId, autoBootstrapToken = true, client } = options;

  const store = useMemo(() => {
    return new ChatStore({ businessId, client });
  }, [businessId, client]);

  // Synchronize businessId if it changes dynamically
  useEffect(() => {
    store.setBusinessId(businessId);
  }, [store, businessId]);

  // Auto-bootstrap preview token on mount if requested
  useEffect(() => {
    if (autoBootstrapToken) {
      store.refreshToken().catch(() => {
        // Errors are captured within store state
      });
    }
  }, [store, autoBootstrapToken]);

  const state = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot
  );

  return {
    messages: state.messages,
    conversationId: state.conversationId,
    status: state.status,
    isSending: store.isSending,
    error: state.error,
    canRetry: state.lastFailedRequest !== null && !store.isSending,
    sendMessage: store.sendMessage,
    retryLastMessage: store.retryLastMessage,
    clearConversation: store.clearConversation,
    refreshToken: store.refreshToken,
  };
}
