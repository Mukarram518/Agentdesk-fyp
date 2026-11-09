/**
 * AgentDesk Chat State Management Store (Phase 7 - Step 7B).
 * Pure state management, message validation, token renewal, and retry mechanics.
 */

import type {
  ChatState,
  ChatStatus,
  ChatUIMessage,
  ChatMessageItem,
} from "@/types/chat";
import { detectTextDirection } from "./text-direction";
import {
  getPreviewToken,
  sendChatMessage,
  isTokenExpiredError,
} from "./chat-client";
import { apiClient, ApiClient, isApiClientError } from "@/lib/api/client";

export const TOKEN_EXPIRATION_BUFFER_MS = 60 * 1000; // 60 seconds

export const INITIAL_CHAT_STATE: ChatState = Object.freeze({
  messages: [] as ChatUIMessage[],
  conversationId: null,
  status: "idle" as ChatStatus,
  token: null,
  tokenExpiresAt: null,
  lastFailedRequest: null,
  error: null,
}) as ChatState;

export interface ValidationResult {
  isValid: boolean;
  error?: string;
  cleanedMessage?: string;
}

/**
 * Validates chat message text: 1 to 2000 characters, not empty, not whitespace-only.
 */
export function validateChatMessage(raw: unknown): ValidationResult {
  if (typeof raw !== "string" || !raw.trim()) {
    return {
      isValid: false,
      error: "Message content cannot be empty or whitespace-only.",
    };
  }
  const cleaned = raw.trim();
  if (cleaned.length > 2000) {
    return {
      isValid: false,
      error: "Message content cannot exceed 2000 characters.",
    };
  }
  return {
    isValid: true,
    cleanedMessage: cleaned,
  };
}

/**
 * Checks whether a token is expired or within the renewal buffer.
 */
export function isTokenCloseToExpiry(
  expiresAt: Date | null,
  bufferMs: number = TOKEN_EXPIRATION_BUFFER_MS
): boolean {
  if (!expiresAt) {
    return true;
  }
  return Date.now() + bufferMs >= expiresAt.getTime();
}

export class ChatStore {
  private state: ChatState;
  private listeners = new Set<() => void>();
  private client: ApiClient;
  private businessId?: string;
  private isSubmitting = false;

  constructor(options: { businessId?: string; client?: ApiClient } = {}) {
    this.businessId = options.businessId;
    this.client = options.client || apiClient;
    this.state = INITIAL_CHAT_STATE;
  }

  get isSending(): boolean {
    return this.isSubmitting || this.state.status === "sending";
  }

  getSnapshot = (): ChatState => {
    return this.state;
  };

  getServerSnapshot = (): ChatState => {
    return INITIAL_CHAT_STATE;
  };

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private setState(partial: Partial<ChatState>) {
    this.state = { ...this.state, ...partial };
    for (const listener of this.listeners) {
      listener();
    }
  }

  setBusinessId(newBusinessId?: string) {
    if (this.businessId !== newBusinessId) {
      this.businessId = newBusinessId;
      // Invalidate existing token and conversation on business switch
      this.setState({
        token: null,
        tokenExpiresAt: null,
        conversationId: null,
        messages: [],
        lastFailedRequest: null,
        status: "idle",
        error: null,
      });
    }
  }

  /**
   * Acquires or renews the preview token.
   */
  refreshToken = async (): Promise<string> => {
    if (!this.isSubmitting) {
      this.setState({ status: "loading_token", error: null });
    }
    try {
      const response = await getPreviewToken({
        businessId: this.businessId,
        client: this.client,
      });
      const expiresAt = new Date(response.expires_at);
      this.setState({
        token: response.token,
        tokenExpiresAt: expiresAt,
        status: this.isSubmitting ? "sending" : "ready",
        error: null,
      });
      return response.token;
    } catch (err: unknown) {
      const message = isApiClientError(err)
        ? err.message
        : "Failed to obtain chat preview token.";
      this.setState({
        status: "error",
        error: message,
      });
      throw err;
    }
  };

  /**
   * Internal helper ensuring a valid token is available before message dispatch.
   */
  private ensureValidToken = async (): Promise<string> => {
    if (this.state.token && !isTokenCloseToExpiry(this.state.tokenExpiresAt)) {
      return this.state.token;
    }
    return this.refreshToken();
  };

  /**
   * Sends a new user message turn.
   */
  sendMessage = async (rawMessage: string): Promise<void> => {
    // 1. Prevent concurrent submissions
    if (this.isSubmitting || this.state.status === "sending") {
      return;
    }

    // 2. Validate input
    const validation = validateChatMessage(rawMessage);
    if (!validation.isValid || !validation.cleanedMessage) {
      this.setState({
        status: "error",
        error: validation.error || "Invalid message content.",
      });
      return;
    }
    const messageText = validation.cleanedMessage;

    // 3. Generate new request ID
    const requestId = crypto.randomUUID();

    // 4. Execute turn under concurrency lock
    this.isSubmitting = true;
    try {
      await this.executeTurn({
        requestId,
        messageText,
        isRetry: false,
      });
    } finally {
      this.isSubmitting = false;
    }
  };

  /**
   * Retries the last failed message using the original request ID and message text.
   */
  retryLastMessage = async (): Promise<void> => {
    // 1. Prevent concurrent submissions
    if (this.isSubmitting || this.state.status === "sending") {
      return;
    }

    // 2. Must have a failed request recorded
    const failed = this.state.lastFailedRequest;
    if (!failed) {
      return;
    }

    // 3. Execute retry turn with EXACT SAME requestId and message under concurrency lock
    this.isSubmitting = true;
    try {
      await this.executeTurn({
        requestId: failed.requestId,
        messageText: failed.message,
        isRetry: true,
      });
    } finally {
      this.isSubmitting = false;
    }
  };

  /**
   * Executes a turn or retry with optimistic updates, token refresh, and retry handling.
   */
  private executeTurn = async (params: {
    requestId: string;
    messageText: string;
    isRetry: boolean;
  }): Promise<void> => {
    const { requestId, messageText, isRetry } = params;

    // A. Optimistic UI update
    let nextMessages: ChatUIMessage[];
    if (isRetry) {
      // Never create duplicate optimistic user messages during retries.
      // Find the existing user message matching requestId and transition to "sending".
      nextMessages = this.state.messages.map((msg) => {
        if (msg.requestId === requestId && msg.role === "user") {
          return {
            ...msg,
            status: "sending" as const,
            errorMessage: undefined,
          };
        }
        return msg;
      });
    } else {
      const userBubble: ChatUIMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: messageText,
        createdAt: new Date().toISOString(),
        status: "sending",
        requestId,
        direction: detectTextDirection(messageText),
      };
      nextMessages = [...this.state.messages, userBubble];
    }

    this.setState({
      messages: nextMessages,
      status: "sending",
      error: null,
    });

    // B. Acquire or proactively renew token
    let token: string;
    try {
      token = await this.ensureValidToken();
    } catch (tokenErr: unknown) {
      const errMessage = isApiClientError(tokenErr)
        ? tokenErr.message
        : "Failed to acquire preview token.";
      this.handleTurnError({
        requestId,
        messageText,
        errorMessage: errMessage,
      });
      return;
    }

    // C. Dispatch chat request with 401 token renewal handling
    let attempts = 0;
    const maxAttempts = 2; // Initial attempt + 1 retry specifically on expired token

    while (attempts < maxAttempts) {
      attempts++;
      try {
        const response = await sendChatMessage(
          token,
          {
            conversation_id: this.state.conversationId,
            message: messageText,
            request_id: requestId,
          },
          { client: this.client }
        );

        // Success: Update optimistic user bubble to "sent", append assistant bubble, preserve conversationId
        this.handleTurnSuccess({
          requestId,
          response,
        });
        return;
      } catch (err: unknown) {
        // Specifically check if HTTP 401 identifies an expired widget token
        if (isTokenExpiredError(err) && attempts === 1) {
          try {
            // Proactively renew token and retry the loop with the EXACT SAME requestId
            token = await this.refreshToken();
            continue;
          } catch (refreshErr: unknown) {
            const errMessage = isApiClientError(refreshErr)
              ? refreshErr.message
              : "Failed to renew expired preview token.";
            this.handleTurnError({
              requestId,
              messageText,
              errorMessage: errMessage,
            });
            return;
          }
        }

        // All other errors (or expired token retry failed): do NOT retry automatically
        const errMessage = isApiClientError(err)
          ? err.message
          : "An unexpected error occurred while processing the chat request.";
        this.handleTurnError({
          requestId,
          messageText,
          errorMessage: errMessage,
        });
        return;
      }
    }
  };

  /**
   * Handles successful turn completion.
   */
  private handleTurnSuccess(params: {
    requestId: string;
    response: { conversation_id: string; message: ChatMessageItem };
  }) {
    const { requestId, response } = params;

    // 1. Mark optimistic user message as "sent"
    const updatedMessages = this.state.messages.map((msg) => {
      if (msg.requestId === requestId && msg.role === "user") {
        return {
          ...msg,
          status: "sent" as const,
          errorMessage: undefined,
        };
      }
      return msg;
    });

    // 2. Append assistant message
    const assistantBubble: ChatUIMessage = {
      id: response.message.id,
      role: "assistant",
      content: response.message.content,
      createdAt: response.message.created_at,
      status: "sent",
      direction: detectTextDirection(response.message.content),
    };

    this.setState({
      messages: [...updatedMessages, assistantBubble],
      conversationId: response.conversation_id, // Preserve conversation ID
      status: "ready",
      lastFailedRequest: null,
      error: null,
    });
  }

  /**
   * Handles turn errors, preserves original request ID and message for retry.
   */
  private handleTurnError(params: {
    requestId: string;
    messageText: string;
    errorMessage: string;
  }) {
    const { requestId, messageText, errorMessage } = params;

    const updatedMessages = this.state.messages.map((msg) => {
      if (msg.requestId === requestId && msg.role === "user") {
        return {
          ...msg,
          status: "error" as const,
          errorMessage,
        };
      }
      return msg;
    });

    this.setState({
      messages: updatedMessages,
      status: "error",
      error: errorMessage,
      lastFailedRequest: {
        requestId,
        message: messageText,
        conversationId: this.state.conversationId,
      },
    });
  }

  /**
   * Clears the current conversation thread.
   */
  clearConversation = () => {
    this.setState({
      messages: [],
      conversationId: null,
      lastFailedRequest: null,
      error: null,
      status: this.state.token ? "ready" : "idle",
    });
  };
}
