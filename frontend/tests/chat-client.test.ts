import test, { describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import {
  ApiClient,
  ApiHttpError,
  ApiNetworkError,
  ApiTimeoutError,
} from "../lib/api/client";
import {
  getPreviewToken,
  sendChatMessage,
  isTokenExpiredError,
} from "../lib/chat/chat-client";

describe("Frontend Chat API Client", () => {
  const originalFetch = globalThis.fetch;
  let mockClient: ApiClient;

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("isTokenExpiredError helper", () => {
    test("returns true specifically for HTTP 401 token expired error", () => {
      const err = new ApiHttpError(401, "Unauthorized", {
        detail: "Widget token has expired.",
      });
      assert.strictEqual(isTokenExpiredError(err), true);
    });

    test("returns true if message contains token_expired or token has expired", () => {
      const err = new ApiHttpError(401, "Unauthorized", {
        detail: "bearer error=\"token_expired\"",
      });
      assert.strictEqual(isTokenExpiredError(err), true);
    });

    test("returns false for HTTP 401 invalid signature or missing token", () => {
      const invalidSig = new ApiHttpError(401, "Unauthorized", {
        detail: "Invalid widget token signature.",
      });
      assert.strictEqual(isTokenExpiredError(invalidSig), false);

      const missingToken = new ApiHttpError(401, "Unauthorized", {
        detail: "Missing widget authentication token.",
      });
      assert.strictEqual(isTokenExpiredError(missingToken), false);
    });

    test("returns false for other HTTP errors (403, 404, 422, 503)", () => {
      const forbidden = new ApiHttpError(403, "Forbidden", {
        detail: "Origin not allowed.",
      });
      assert.strictEqual(isTokenExpiredError(forbidden), false);

      const notFound = new ApiHttpError(404, "Not Found", {
        detail: "Conversation not found.",
      });
      assert.strictEqual(isTokenExpiredError(notFound), false);
    });

    test("returns false for non-HTTP errors or non-error objects", () => {
      assert.strictEqual(isTokenExpiredError(new Error("Generic error")), false);
      assert.strictEqual(isTokenExpiredError(null), false);
      assert.strictEqual(isTokenExpiredError(undefined), false);
      assert.strictEqual(isTokenExpiredError({ status: 401 }), false);
    });
  });

  describe("getPreviewToken", () => {
    test("sends POST /api/v1/chat/preview-token with optional business_id and credentials", async () => {
      let capturedUrl = "";
      let capturedMethod = "";
      let capturedBody = "";
      let capturedCredentials: RequestCredentials | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedMethod = init?.method || "GET";
        capturedBody = init?.body ? String(init.body) : "";
        capturedCredentials = init?.credentials;

        return new Response(
          JSON.stringify({
            token: "mock-preview-token-123",
            expires_at: "2026-11-09T22:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const result = await getPreviewToken({
        businessId: "biz-uuid-456",
        client: mockClient,
      });

      assert.ok(capturedUrl.includes("/api/v1/chat/preview-token"));
      assert.strictEqual(capturedMethod, "POST");
      assert.strictEqual(capturedCredentials, "include");
      assert.deepStrictEqual(JSON.parse(capturedBody), {
        business_id: "biz-uuid-456",
      });
      assert.strictEqual(result.token, "mock-preview-token-123");
      assert.strictEqual(result.expires_at, "2026-11-09T22:00:00Z");
    });

    test("omits body when no businessId is provided", async () => {
      let capturedBody: BodyInit | null | undefined = null;

      globalThis.fetch = async (_input, init) => {
        capturedBody = init?.body;
        return new Response(
          JSON.stringify({
            token: "mock-preview-token-789",
            expires_at: "2026-11-09T22:15:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const result = await getPreviewToken({ client: mockClient });
      assert.strictEqual(capturedBody, undefined);
      assert.strictEqual(result.token, "mock-preview-token-789");
    });

    test("throws ApiHttpError 401 when unauthenticated", async () => {
      globalThis.fetch = async () =>
        new Response(
          JSON.stringify({ detail: "Authentication required." }),
          { status: 401, statusText: "Unauthorized" }
        );

      await assert.rejects(
        async () => {
          await getPreviewToken({ client: mockClient });
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 401);
          assert.strictEqual(err.message, "Authentication required.");
          return true;
        }
      );
    });

    test("throws ApiHttpError 403 when user is not owner/admin", async () => {
      globalThis.fetch = async () =>
        new Response(
          JSON.stringify({
            detail: "Only business owners and admins are authorized to obtain preview tokens.",
          }),
          { status: 403, statusText: "Forbidden" }
        );

      await assert.rejects(
        async () => {
          await getPreviewToken({ client: mockClient });
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 403);
          return true;
        }
      );
    });
  });

  describe("sendChatMessage", () => {
    test("sends POST /api/v1/chat/messages with X-Widget-Token and JSON payload", async () => {
      let capturedUrl = "";
      let capturedHeaders: Headers | undefined;
      let capturedBody = "";

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedHeaders = new Headers(init?.headers);
        capturedBody = init?.body ? String(init.body) : "";

        return new Response(
          JSON.stringify({
            conversation_id: "conv-111",
            message: {
              id: "msg-222",
              role: "assistant",
              content: "Hello! How can I assist you today?",
              created_at: "2026-11-09T21:30:00Z",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const result = await sendChatMessage(
        "widget-jwt-token-abc",
        {
          conversation_id: "conv-111",
          message: "What services do you offer?",
          request_id: "req-333",
        },
        { client: mockClient }
      );

      assert.ok(capturedUrl.includes("/api/v1/chat/messages"));
      assert.strictEqual(capturedHeaders?.get("X-Widget-Token"), "widget-jwt-token-abc");
      // INVARIANT: Browser controls Origin, never set manually
      assert.strictEqual(capturedHeaders?.has("Origin"), false);

      const parsedBody = JSON.parse(capturedBody);
      assert.strictEqual(parsedBody.conversation_id, "conv-111");
      assert.strictEqual(parsedBody.message, "What services do you offer?");
      assert.strictEqual(parsedBody.request_id, "req-333");

      assert.strictEqual(result.conversation_id, "conv-111");
      assert.strictEqual(result.message.id, "msg-222");
      assert.strictEqual(result.message.role, "assistant");
      assert.strictEqual(result.message.content, "Hello! How can I assist you today?");
    });

    test("handles HTTP 503 lock timeout or lease loss", async () => {
      globalThis.fetch = async () =>
        new Response(
          JSON.stringify({
            detail: "Chat coordination temporarily unavailable. Please retry shortly.",
          }),
          { status: 503, statusText: "Service Unavailable" }
        );

      await assert.rejects(
        async () => {
          await sendChatMessage(
            "token",
            {
              message: "Test",
              request_id: "req-1",
            },
            { client: mockClient }
          );
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 503);
          return true;
        }
      );
    });

    test("handles network failure and wraps in ApiNetworkError", async () => {
      globalThis.fetch = async () => {
        throw new TypeError("Failed to fetch");
      };

      await assert.rejects(
        async () => {
          await sendChatMessage(
            "token",
            {
              message: "Test",
              request_id: "req-1",
            },
            { client: mockClient }
          );
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiNetworkError);
          return true;
        }
      );
    });

    test("handles request timeout and wraps in ApiTimeoutError", async () => {
      globalThis.fetch = async () => {
        const error = new Error("The operation was aborted");
        error.name = "AbortError";
        throw error;
      };

      await assert.rejects(
        async () => {
          await sendChatMessage(
            "token",
            {
              message: "Test",
              request_id: "req-1",
            },
            { client: mockClient, timeoutMs: 50 }
          );
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiTimeoutError);
          return true;
        }
      );
    });
  });
});
