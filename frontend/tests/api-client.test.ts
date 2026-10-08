import test, { describe, afterEach } from "node:test";
import assert from "node:assert/strict";
import {
  ApiClient,
  ApiHttpError,
  ApiNetworkError,
  ApiParseError,
  ApiTimeoutError,
  isApiClientError,
} from "../lib/api/client";

describe("Frontend API Client Foundation", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("correctly initializes and normalizes API base URL", () => {
    const client1 = new ApiClient("http://api.agentdesk.local:8000/");
    assert.strictEqual(client1.baseUrl, "http://api.agentdesk.local:8000");

    const client2 = new ApiClient("http://localhost:8000///");
    assert.strictEqual(client2.baseUrl, "http://localhost:8000");

    const clientDefault = new ApiClient();
    assert.ok(clientDefault.baseUrl.startsWith("http://"));
  });

  test("handles successful health request with typed response", async () => {
    const mockHealthData = {
      status: "healthy",
      app: "AgentDesk",
      version: "0.1.0",
      environment: "development",
      timestamp: "2026-10-07T15:00:00Z",
      database: { status: "healthy", pgvector: "enabled (v0.8.7)" },
      redis: { status: "healthy" },
    };

    globalThis.fetch = async (input) => {
      const url = String(input);
      assert.ok(url.includes("/health"));
      assert.ok(url.includes("full=true"));
      return new Response(JSON.stringify(mockHealthData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const result = await client.getHealth({ full: true });

    assert.strictEqual(result.status, "healthy");
    assert.strictEqual(result.app, "AgentDesk");
    assert.strictEqual(result.version, "0.1.0");
    assert.strictEqual(result.database?.status, "healthy");
    assert.strictEqual(result.redis?.status, "healthy");
  });

  test("correctly requests versioned /api/v1/health endpoint", async () => {
    let requestedUrl = "";
    globalThis.fetch = async (input) => {
      requestedUrl = String(input);
      return new Response(JSON.stringify({ status: "healthy" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    await client.getV1Health();

    assert.ok(requestedUrl.includes("/api/v1/health"));
  });

  test("checkOperationalStatus returns true on healthy and false on error", async () => {
    // Healthy probe
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ status: "healthy" }), { status: 200 });

    const client = new ApiClient("http://127.0.0.1:8000");
    assert.strictEqual(await client.checkOperationalStatus(), true);

    // Unhealthy probe
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ status: "unhealthy" }), { status: 503 });

    assert.strictEqual(await client.checkOperationalStatus(), false);
  });

  test("handles backend HTTP errors and extracts server error detail", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({ detail: "Invalid request parameter" }),
        { status: 400, statusText: "Bad Request" }
      );

    const client = new ApiClient("http://127.0.0.1:8000");

    await assert.rejects(
      async () => {
        await client.get("/invalid-path");
      },
      (err: unknown) => {
        assert.ok(isApiClientError(err));
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.status, 400);
        assert.strictEqual(err.code, "HTTP_ERROR");
        assert.strictEqual(err.message, "Invalid request parameter");
        return true;
      }
    );
  });

  test("handles network failure and wraps in ApiNetworkError", async () => {
    globalThis.fetch = async () => {
      throw new TypeError("Failed to fetch");
    };

    const client = new ApiClient("http://127.0.0.1:8000");

    await assert.rejects(
      async () => {
        await client.get("/health");
      },
      (err: unknown) => {
        assert.ok(isApiClientError(err));
        assert.ok(err instanceof ApiNetworkError);
        assert.strictEqual(err.code, "NETWORK_ERROR");
        return true;
      }
    );
  });

  test("handles invalid non-JSON response and wraps in ApiParseError", async () => {
    globalThis.fetch = async () =>
      new Response("<html>502 Bad Gateway</html>", {
        status: 200,
        headers: { "Content-Type": "text/html" },
      });

    const client = new ApiClient("http://127.0.0.1:8000");

    await assert.rejects(
      async () => {
        await client.get("/broken-json");
      },
      (err: unknown) => {
        assert.ok(isApiClientError(err));
        assert.ok(err instanceof ApiParseError);
        assert.strictEqual(err.code, "PARSE_ERROR");
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

    const client = new ApiClient("http://127.0.0.1:8000");

    await assert.rejects(
      async () => {
        await client.get("/slow-endpoint", { timeoutMs: 100 });
      },
      (err: unknown) => {
        assert.ok(isApiClientError(err));
        assert.ok(err instanceof ApiTimeoutError);
        assert.strictEqual(err.code, "TIMEOUT_ERROR");
        return true;
      }
    );
  });
});
