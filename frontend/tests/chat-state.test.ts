import test, { describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import {
  ChatStore,
  INITIAL_CHAT_STATE,
  validateChatMessage,
  isTokenCloseToExpiry,
} from "../lib/chat/chat-state";
import { ApiClient } from "../lib/api/client";
import type { ChatState } from "../types/chat";

describe("Frontend Chat State Store (Phase 7 - Step 7B)", () => {
  const originalFetch = globalThis.fetch;
  let mockClient: ApiClient;

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("Message Validation (validateChatMessage)", () => {
    test("rejects empty, whitespace-only, null, or non-string inputs", () => {
      assert.strictEqual(validateChatMessage("").isValid, false);
      assert.strictEqual(validateChatMessage("   ").isValid, false);
      assert.strictEqual(validateChatMessage("\t\n").isValid, false);
      assert.strictEqual(validateChatMessage(null).isValid, false);
      assert.strictEqual(validateChatMessage(undefined).isValid, false);
      assert.strictEqual(validateChatMessage(12345).isValid, false);
    });

    test("accepts boundary lengths (1 character and 2000 characters)", () => {
      const minValid = validateChatMessage("a");
      assert.strictEqual(minValid.isValid, true);
      assert.strictEqual(minValid.cleanedMessage, "a");

      const maxValid = validateChatMessage("a".repeat(2000));
      assert.strictEqual(maxValid.isValid, true);
      assert.strictEqual(maxValid.cleanedMessage?.length, 2000);
    });

    test("rejects messages exceeding 2000 characters", () => {
      const overBoundary = validateChatMessage("a".repeat(2001));
      assert.strictEqual(overBoundary.isValid, false);
      assert.strictEqual(
        overBoundary.error,
        "Message content cannot exceed 2000 characters."
      );
    });

    test("trims leading and trailing whitespace while retaining content", () => {
      const result = validateChatMessage("   Hello world!   ");
      assert.strictEqual(result.isValid, true);
      assert.strictEqual(result.cleanedMessage, "Hello world!");
    });
  });

  describe("Token Expiration Check (isTokenCloseToExpiry)", () => {
    test("returns true for null or undefined expiresAt", () => {
      assert.strictEqual(isTokenCloseToExpiry(null), true);
    });

    test("returns true for past expiration date", () => {
      const past = new Date(Date.now() - 1000);
      assert.strictEqual(isTokenCloseToExpiry(past), true);
    });

    test("returns true if token expires within 60 seconds buffer", () => {
      const withinBuffer = new Date(Date.now() + 30 * 1000); // 30s left
      assert.strictEqual(isTokenCloseToExpiry(withinBuffer), true);
    });

    test("returns false if token has ample validity remaining", () => {
      const ampleValidity = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes left
      assert.strictEqual(isTokenCloseToExpiry(ampleValidity), false);
    });
  });

  describe("ChatStore State Lifecycle & Transitions", () => {
    test("initializes with initial state and snapshot integrity", () => {
      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      const state = store.getSnapshot();

      assert.deepStrictEqual(state, INITIAL_CHAT_STATE);
      assert.strictEqual(state.status, "idle");
      assert.strictEqual(state.messages.length, 0);
      assert.strictEqual(state.conversationId, null);
      assert.strictEqual(state.lastFailedRequest, null);
    });

    test("refreshToken updates token, expiration date, and transitions status to ready", async () => {
      globalThis.fetch = async () =>
        new Response(
          JSON.stringify({
            token: "valid-preview-token",
            expires_at: "2026-11-09T22:30:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      const token = await store.refreshToken();

      assert.strictEqual(token, "valid-preview-token");
      const state = store.getSnapshot();
      assert.strictEqual(state.token, "valid-preview-token");
      assert.strictEqual(
        state.tokenExpiresAt?.toISOString(),
        "2026-11-09T22:30:00.000Z"
      );
      assert.strictEqual(state.status, "ready");
      assert.strictEqual(state.error, null);
    });

    test("sendMessage validates input and rejects empty content without dispatching", async () => {
      let fetchCalled = false;
      globalThis.fetch = async () => {
        fetchCalled = true;
        return new Response("{}", { status: 200 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      await store.sendMessage("   ");

      assert.strictEqual(fetchCalled, false);
      const state = store.getSnapshot();
      assert.strictEqual(state.status, "error");
      assert.strictEqual(
        state.error,
        "Message content cannot be empty or whitespace-only."
      );
      assert.strictEqual(state.messages.length, 0);
    });

    test("successful turn appends optimistic user message, receives assistant reply, and updates conversationId", async () => {
      globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.includes("/preview-token")) {
          return new Response(
            JSON.stringify({
              token: "preview-token-xyz",
              expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/messages")) {
          return new Response(
            JSON.stringify({
              conversation_id: "conv-uuid-111",
              message: {
                id: "msg-uuid-assistant-1",
                role: "assistant",
                content: "We provide comprehensive dental care.",
                created_at: "2026-11-09T21:40:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("Not found", { status: 404 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      await store.sendMessage("What services do you offer?");

      const state = store.getSnapshot();
      assert.strictEqual(state.status, "ready");
      assert.strictEqual(state.conversationId, "conv-uuid-111");
      assert.strictEqual(state.messages.length, 2);

      // Verify user message
      const userMsg = state.messages[0];
      assert.strictEqual(userMsg.role, "user");
      assert.strictEqual(userMsg.content, "What services do you offer?");
      assert.strictEqual(userMsg.status, "sent");
      assert.strictEqual(userMsg.direction, "ltr");
      assert.ok(userMsg.requestId);

      // Verify assistant message
      const assistantMsg = state.messages[1];
      assert.strictEqual(assistantMsg.role, "assistant");
      assert.strictEqual(
        assistantMsg.content,
        "We provide comprehensive dental care."
      );
      assert.strictEqual(assistantMsg.status, "sent");
      assert.strictEqual(assistantMsg.direction, "ltr");

      // Verify no failed request remaining
      assert.strictEqual(state.lastFailedRequest, null);
    });

    test("sets direction to RTL for Urdu queries and preserves conversation ID across multiple turns", async () => {
      const capturedPayloads: Array<{ conversation_id?: string | null }> = [];
      globalThis.fetch = async (input, init) => {
        const url = String(input);
        if (url.includes("/preview-token")) {
          return new Response(
            JSON.stringify({
              token: "token-urdu",
              expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/messages")) {
          const body = JSON.parse(String(init?.body));
          capturedPayloads.push(body);
          return new Response(
            JSON.stringify({
              conversation_id: "conv-thread-urdu",
              message: {
                id: `msg-${capturedPayloads.length}`,
                role: "assistant",
                content: "جی ہاں، ہماری کلینک کھلی ہے۔",
                created_at: "2026-11-09T21:42:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("Not found", { status: 404 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });

      // Turn 1
      await store.sendMessage("کیا آپ کی کلینک کھلی ہے؟");
      assert.strictEqual(capturedPayloads[0].conversation_id, null);
      let state = store.getSnapshot();
      assert.strictEqual(state.messages[0].direction, "rtl");
      assert.strictEqual(state.messages[1].direction, "rtl");
      assert.strictEqual(state.conversationId, "conv-thread-urdu");

      // Turn 2
      await store.sendMessage("اوقات کار کیا ہیں؟");
      assert.strictEqual(capturedPayloads[1].conversation_id, "conv-thread-urdu");
      state = store.getSnapshot();
      assert.strictEqual(state.messages.length, 4);
      assert.strictEqual(state.conversationId, "conv-thread-urdu");
    });

    test("concurrency guard prevents duplicate submission while a turn is in flight", async () => {
      let messageCalls = 0;
      globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.includes("/preview-token")) {
          return new Response(
            JSON.stringify({
              token: "token-slow",
              expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/messages")) {
          messageCalls++;
          // Simulate latency
          await new Promise((resolve) => setTimeout(resolve, 50));
          return new Response(
            JSON.stringify({
              conversation_id: "conv-slow",
              message: {
                id: "msg-slow",
                role: "assistant",
                content: "Done",
                created_at: "2026-11-09T21:45:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("Not found", { status: 404 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      const p1 = store.sendMessage("First message");
      const p2 = store.sendMessage("Second concurrent message");

      await Promise.all([p1, p2]);

      // Only first message should have been dispatched
      assert.strictEqual(messageCalls, 1);
      const state = store.getSnapshot();
      assert.strictEqual(state.messages.length, 2);
    });

    test("on network error or timeout, preserves original request ID and message for retry", async () => {
      globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.includes("/preview-token")) {
          return new Response(
            JSON.stringify({
              token: "token-timeout",
              expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/messages")) {
          const timeoutErr = new Error("The operation was aborted");
          timeoutErr.name = "AbortError";
          throw timeoutErr;
        }
        return new Response("Not found", { status: 404 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      await store.sendMessage("Will time out");

      const state = store.getSnapshot();
      assert.strictEqual(state.status, "error");
      assert.ok(state.error?.includes("timed out") || state.error?.includes("aborted"));

      // Verify user message is marked error
      assert.strictEqual(state.messages.length, 1);
      const failedMsg = state.messages[0];
      assert.strictEqual(failedMsg.status, "error");
      assert.ok(failedMsg.requestId);

      // Verify lastFailedRequest preserves the exact original parameters
      assert.ok(state.lastFailedRequest);
      assert.strictEqual(state.lastFailedRequest.requestId, failedMsg.requestId);
      assert.strictEqual(state.lastFailedRequest.message, "Will time out");
    });

    test("retryLastMessage reuses exact original requestId and updates existing bubble without duplicating", async () => {
      const sentRequestIds: string[] = [];
      let shouldFail = true;

      globalThis.fetch = async (input, init) => {
        const url = String(input);
        if (url.includes("/preview-token")) {
          return new Response(
            JSON.stringify({
              token: "token-retry",
              expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/messages")) {
          const body = JSON.parse(String(init?.body));
          sentRequestIds.push(body.request_id);

          if (shouldFail) {
            return new Response(
              JSON.stringify({ detail: "Coordination lock timeout" }),
              { status: 503, statusText: "Service Unavailable" }
            );
          }
          return new Response(
            JSON.stringify({
              conversation_id: "conv-retry-ok",
              message: {
                id: "msg-retry-ok",
                role: "assistant",
                content: "Success on retry",
                created_at: "2026-11-09T21:48:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("Not found", { status: 404 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      await store.sendMessage("Retry test");

      // Verify first attempt failed
      assert.strictEqual(store.getSnapshot().status, "error");
      assert.strictEqual(store.getSnapshot().messages.length, 1);
      const originalRequestId = sentRequestIds[0];

      // Now retry with backend restored
      shouldFail = false;
      await store.retryLastMessage();

      const finalState = store.getSnapshot();
      assert.strictEqual(finalState.status, "ready");
      // INVARIANT: Never create duplicate optimistic user messages during retries
      // Only 1 user message + 1 assistant message = 2 messages total!
      assert.strictEqual(finalState.messages.length, 2);
      assert.strictEqual(finalState.messages[0].status, "sent");
      assert.strictEqual(finalState.messages[1].status, "sent");

      // INVARIANT: Exactly the same request ID was sent on retry
      assert.strictEqual(sentRequestIds.length, 2);
      assert.strictEqual(sentRequestIds[0], originalRequestId);
      assert.strictEqual(sentRequestIds[1], originalRequestId);
    });

    test("on HTTP 401 specifically for expired token, automatically renews and retries at most once", async () => {
      let previewTokenCalls = 0;
      let messageCalls = 0;
      const sentTokens: string[] = [];
      const sentRequestIds: string[] = [];

      globalThis.fetch = async (input, init) => {
        const url = String(input);
        if (url.includes("/preview-token")) {
          previewTokenCalls++;
          return new Response(
            JSON.stringify({
              token: `token-turn-${previewTokenCalls}`,
              expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/messages")) {
          messageCalls++;
          const headers = new Headers(init?.headers);
          sentTokens.push(headers.get("X-Widget-Token") || "");
          const body = JSON.parse(String(init?.body));
          sentRequestIds.push(body.request_id);

          // First call rejects with expired token
          if (messageCalls === 1) {
            return new Response(
              JSON.stringify({ detail: "Widget token has expired." }),
              {
                status: 401,
                statusText: "Unauthorized",
                headers: { "WWW-Authenticate": 'Bearer error="token_expired"' },
              }
            );
          }
          // Second call (with renewed token) succeeds
          return new Response(
            JSON.stringify({
              conversation_id: "conv-token-refresh",
              message: {
                id: "msg-recovered",
                role: "assistant",
                content: "Recovered seamlessly",
                created_at: "2026-11-09T21:50:00Z",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("Not found", { status: 404 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      await store.sendMessage("Will expire once");

      const state = store.getSnapshot();
      assert.strictEqual(state.status, "ready");
      assert.strictEqual(state.messages.length, 2);
      assert.strictEqual(state.messages[1].content, "Recovered seamlessly");

      // Verify token renewal and single retry occurred
      assert.strictEqual(previewTokenCalls, 2); // Initial bootstrap + renewal
      assert.strictEqual(messageCalls, 2);       // First attempt + 1 retry
      assert.strictEqual(sentTokens[0], "token-turn-1");
      assert.strictEqual(sentTokens[1], "token-turn-2");

      // INVARIANT: Exactly the same request_id was reused during the renewal retry
      assert.strictEqual(sentRequestIds[0], sentRequestIds[1]);
    });

    test("does not automatically retry non-expired authentication or validation errors", async () => {
      let previewTokenCalls = 0;
      let messageCalls = 0;

      globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.includes("/preview-token")) {
          previewTokenCalls++;
          return new Response(
            JSON.stringify({
              token: "valid-initial-token",
              expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/messages")) {
          messageCalls++;
          // Returns 401 invalid signature (NOT expired)
          return new Response(
            JSON.stringify({ detail: "Invalid widget token signature." }),
            { status: 401, statusText: "Unauthorized" }
          );
        }
        return new Response("Not found", { status: 404 });
      };

      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      await store.sendMessage("Invalid signature probe");

      const state = store.getSnapshot();
      assert.strictEqual(state.status, "error");
      assert.strictEqual(state.error, "Invalid widget token signature.");

      // Verify no automatic retry occurred
      assert.strictEqual(previewTokenCalls, 1);
      assert.strictEqual(messageCalls, 1);
    });

    test("clearConversation resets messages and conversation state back to ready", async () => {
      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      // Pre-set some state
      (store as unknown as { setState: (partial: Partial<ChatState>) => void }).setState({
        token: "tok",
        messages: [{
          id: "1",
          role: "user",
          content: "hi",
          status: "sent",
          createdAt: new Date().toISOString(),
          direction: "ltr",
        }],
        conversationId: "conv-1",
        lastFailedRequest: { requestId: "r-1", message: "hi", conversationId: "conv-1" },
      });

      store.clearConversation();
      const state = store.getSnapshot();

      assert.strictEqual(state.messages.length, 0);
      assert.strictEqual(state.conversationId, null);
      assert.strictEqual(state.lastFailedRequest, null);
      assert.strictEqual(state.status, "ready");
    });

    test("setBusinessId resets conversation and token when business changes", () => {
      const store = new ChatStore({ businessId: "biz-1", client: mockClient });
      (store as unknown as { setState: (partial: Partial<ChatState>) => void }).setState({
        token: "tok-biz-1",
        conversationId: "conv-biz-1",
        messages: [{
          id: "1",
          role: "user",
          content: "test",
          status: "sent",
          createdAt: new Date().toISOString(),
          direction: "ltr",
        }],
      });

      store.setBusinessId("biz-2");
      const state = store.getSnapshot();

      assert.strictEqual(state.token, null);
      assert.strictEqual(state.conversationId, null);
      assert.strictEqual(state.messages.length, 0);
      assert.strictEqual(state.status, "idle");
    });
  });
});
