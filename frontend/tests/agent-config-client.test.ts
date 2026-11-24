import test, { describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { ApiClient, ApiHttpError, ApiNetworkError, ApiTimeoutError } from "../lib/api/client";
import {
  getAgentConfig,
  updateAgentConfig,
  patchAgentConfig,
} from "../lib/api/agents";
import type { AgentConfigResponse, AgentConfigUpdate } from "../types/agents";

describe("Frontend AgentConfig API Client", () => {
  const originalFetch = globalThis.fetch;
  let mockClient: ApiClient;

  const sampleConfig: AgentConfigResponse = {
    business_id: "biz-1234-uuid",
    voice_enabled: true,
    chat_enabled: true,
    lead_enabled: true,
    voice_id: null,
    tone: "helpful",
    greeting: "Hello! Welcome to our store. How can we help you today?",
    language_priority: ["en", "ur"],
    created_at: "2026-11-10T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
  };

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("GET /api/v1/agents/config", () => {
    test("sends GET request with credentials: include and returns typed AgentConfigResponse", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify(sampleConfig), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await mockClient.getAgentConfig();

      assert.ok(capturedUrl.endsWith("/api/v1/agents/config"));
      assert.strictEqual(capturedOptions?.method, "GET");
      assert.strictEqual(capturedOptions?.credentials, "include");
      assert.strictEqual(result.business_id, "biz-1234-uuid");
      assert.strictEqual(result.tone, "helpful");
      assert.strictEqual(result.chat_enabled, true);
      assert.strictEqual(result.voice_enabled, true);
      assert.strictEqual(result.lead_enabled, true);
      assert.deepStrictEqual(result.language_priority, ["en", "ur"]);
    });

    test("standalone getAgentConfig helper delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleConfig), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await getAgentConfig({ client: mockClient });
      assert.strictEqual(result.business_id, sampleConfig.business_id);
    });

    test("throws ApiHttpError with 401 when unauthenticated", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ detail: "Not authenticated" }),
          { status: 401, headers: { "Content-Type": "application/json" } }
        );
      };

      await assert.rejects(
        async () => {
          await mockClient.getAgentConfig();
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 401);
          assert.strictEqual(err.message, "Not authenticated");
          return true;
        }
      );
    });

    test("throws ApiHttpError with 403 when user is not a business owner", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ detail: "Only the business owner or admin can access agent configuration." }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        );
      };

      await assert.rejects(
        async () => {
          await mockClient.getAgentConfig();
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 403);
          assert.strictEqual(
            err.message,
            "Only the business owner or admin can access agent configuration."
          );
          return true;
        }
      );
    });

    test("wraps network drop in ApiNetworkError", async () => {
      globalThis.fetch = async () => {
        throw new TypeError("Failed to fetch");
      };

      await assert.rejects(
        async () => {
          await mockClient.getAgentConfig();
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiNetworkError);
          return true;
        }
      );
    });

    test("wraps request timeout in ApiTimeoutError", async () => {
      globalThis.fetch = async () => {
        const error = new Error("The operation was aborted.");
        error.name = "AbortError";
        throw error;
      };

      await assert.rejects(
        async () => {
          await mockClient.getAgentConfig();
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiTimeoutError);
          return true;
        }
      );
    });
  });

  describe("PUT /api/v1/agents/config", () => {
    test("sends PUT request with serialized payload and credentials: include", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      const updatePayload: AgentConfigUpdate = {
        tone: "professional",
        greeting: "Welcome to AgentDesk Enterprise.",
        voice_enabled: false,
        chat_enabled: true,
        lead_enabled: false,
        language_priority: ["ur", "en"],
        voice_id: "voice-123",
      };

      const updatedResponse: AgentConfigResponse = {
        ...sampleConfig,
        ...updatePayload,
        updated_at: "2026-11-10T11:00:00Z",
      };

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify(updatedResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await mockClient.updateAgentConfig(updatePayload);

      assert.ok(capturedUrl.endsWith("/api/v1/agents/config"));
      assert.strictEqual(capturedOptions?.method, "PUT");
      assert.strictEqual(capturedOptions?.credentials, "include");

      const parsedBody = JSON.parse(String(capturedOptions?.body));
      assert.deepStrictEqual(parsedBody, updatePayload);

      assert.strictEqual(result.tone, "professional");
      assert.strictEqual(result.voice_enabled, false);
      assert.strictEqual(result.lead_enabled, false);
      assert.strictEqual(result.voice_id, "voice-123");
      assert.deepStrictEqual(result.language_priority, ["ur", "en"]);
    });

    test("standalone updateAgentConfig helper delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleConfig), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await updateAgentConfig({ tone: "friendly" }, { client: mockClient });
      assert.strictEqual(result.business_id, sampleConfig.business_id);
    });

    test("handles HTTP 422 validation error with server detail payload", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({
            detail: "Invalid tone 'sarcastic'. Allowed tones are: direct, friendly, helpful, professional.",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } }
        );
      };

      await assert.rejects(
        async () => {
          await mockClient.updateAgentConfig({
            tone: "sarcastic" as unknown as AgentConfigUpdate["tone"],
          });
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 422);
          assert.ok(err.message.includes("Invalid tone 'sarcastic'"));
          return true;
        }
      );
    });
  });

  describe("PATCH /api/v1/agents/config", () => {
    test("sends PATCH request with partial payload", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      const patchPayload: AgentConfigUpdate = {
        chat_enabled: false,
      };

      const patchedResponse: AgentConfigResponse = {
        ...sampleConfig,
        chat_enabled: false,
        updated_at: "2026-11-10T12:00:00Z",
      };

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify(patchedResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await mockClient.patchAgentConfig(patchPayload);

      assert.ok(capturedUrl.endsWith("/api/v1/agents/config"));
      assert.strictEqual(capturedOptions?.method, "PATCH");
      assert.strictEqual(capturedOptions?.credentials, "include");

      const parsedBody = JSON.parse(String(capturedOptions?.body));
      assert.deepStrictEqual(parsedBody, patchPayload);
      assert.strictEqual(result.chat_enabled, false);
    });

    test("standalone patchAgentConfig helper delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleConfig), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await patchAgentConfig({ voice_enabled: false }, { client: mockClient });
      assert.strictEqual(result.business_id, sampleConfig.business_id);
    });
  });
});
