/**
 * AgentDesk Chat API Client (Phase 7 - Step 7B).
 * Provides typed HTTP functions for preview token acquisition and chat turn submission.
 */

import { apiClient, ApiClient, ApiHttpError, isApiClientError } from "@/lib/api/client";
import type {
  ChatMessageRequest,
  ChatMessageResponse,
  ChatPreviewTokenRequest,
  ChatPreviewTokenResponse,
} from "@/types/chat";

/**
 * Checks whether an error from the backend specifically identifies an expired widget token.
 * Matches HTTP 401 with "Widget token has expired." detail or token_expired error header/payload.
 */
export function isTokenExpiredError(error: unknown): boolean {
  if (!isApiClientError(error) || !(error instanceof ApiHttpError)) {
    return false;
  }
  if (error.status !== 401) {
    return false;
  }

  const message = (error.message || "").toLowerCase();
  if (message.includes("token has expired") || message.includes("token_expired")) {
    return true;
  }

  if (error.data && typeof error.data === "object") {
    const payload = error.data as Record<string, unknown>;
    if (typeof payload.detail === "string") {
      const detail = payload.detail.toLowerCase();
      if (detail.includes("token has expired") || detail.includes("token_expired")) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Obtains a short-lived widget preview token for the dashboard chat preview.
 * Authenticates via session cookie (credentials: "include").
 */
export async function getPreviewToken(
  options: {
    businessId?: string;
    client?: ApiClient;
  } = {}
): Promise<ChatPreviewTokenResponse> {
  const client = options.client || apiClient;
  const payload: ChatPreviewTokenRequest | undefined = options.businessId
    ? { business_id: options.businessId }
    : undefined;

  return client.post<ChatPreviewTokenResponse>(
    "/api/v1/chat/preview-token",
    payload,
    { cache: "no-store" }
  );
}

/**
 * Submits a chat message turn to the backend chat endpoint.
 *
 * Security & Transport Invariants:
 * 1. Transmits widget token strictly in X-Widget-Token header.
 * 2. NEVER manually sets Origin header (browser injects this header automatically).
 */
export async function sendChatMessage(
  token: string,
  payload: ChatMessageRequest,
  options: {
    client?: ApiClient;
    timeoutMs?: number;
  } = {}
): Promise<ChatMessageResponse> {
  const client = options.client || apiClient;

  return client.post<ChatMessageResponse>("/api/v1/chat/messages", payload, {
    headers: {
      "X-Widget-Token": token.trim(),
    },
    timeoutMs: options.timeoutMs,
    cache: "no-store",
  });
}
