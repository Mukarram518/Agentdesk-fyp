/**
 * AgentDesk Web Chat Types (Phase 7 - Step 7B).
 * Defines contracts matching backend schemas and frontend state management.
 */

export type TextDirection = "ltr" | "rtl";
export type MessageRole = "user" | "assistant";
export type MessageDeliveryStatus = "sending" | "sent" | "error";

export interface ChatMessageItem {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface ChatMessageRequest {
  conversation_id?: string | null;
  message: string;
  request_id: string;
}

export interface ChatMessageResponse {
  conversation_id: string;
  message: ChatMessageItem;
}

export interface ChatPreviewTokenRequest {
  business_id?: string;
}

export interface ChatPreviewTokenResponse {
  token: string;
  expires_at: string;
}

export interface ChatUIMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  status: MessageDeliveryStatus;
  requestId?: string;
  direction: TextDirection;
  errorMessage?: string;
}

export type ChatStatus = "idle" | "loading_token" | "ready" | "sending" | "error";

export interface ChatTokenState {
  token: string | null;
  expiresAt: Date | null;
}

export interface FailedChatRequest {
  requestId: string;
  message: string;
  conversationId: string | null;
}

export interface ChatState {
  messages: ChatUIMessage[];
  conversationId: string | null;
  status: ChatStatus;
  token: string | null;
  tokenExpiresAt: Date | null;
  lastFailedRequest: FailedChatRequest | null;
  error: string | null;
}
