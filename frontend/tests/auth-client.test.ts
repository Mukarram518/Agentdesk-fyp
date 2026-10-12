import test, { describe, afterEach } from "node:test";
import assert from "node:assert/strict";
import { ApiClient, ApiHttpError } from "../lib/api/client";

describe("Frontend Authentication API Client", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("register sends POST /api/v1/auth/register with serialized payload and credentials", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedOptions = init;
      return new Response(
        JSON.stringify({
          user: {
            id: "uuid-1234",
            email: "newuser@example.com",
            full_name: "New User",
            verified: false,
            is_active: true,
          },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const res = await client.register({
      email: "newuser@example.com",
      password: "StrongPassword123!",
      full_name: "New User",
    });

    assert.ok(capturedUrl.endsWith("/api/v1/auth/register"));
    assert.strictEqual(capturedOptions?.method, "POST");
    assert.strictEqual(capturedOptions?.credentials, "include");
    assert.strictEqual(res.user.email, "newuser@example.com");
    assert.strictEqual(res.user.verified, false);
  });

  test("login sends POST /api/v1/auth/login and receives session user", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedOptions = init;
      return new Response(
        JSON.stringify({
          user: {
            id: "uuid-5678",
            email: "owner@example.com",
            full_name: "Owner User",
            verified: true,
            is_active: true,
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const res = await client.login({
      email: "owner@example.com",
      password: "Password123!",
    });

    assert.ok(capturedUrl.endsWith("/api/v1/auth/login"));
    assert.strictEqual(capturedOptions?.method, "POST");
    assert.strictEqual(capturedOptions?.credentials, "include");
    assert.strictEqual(res.user.email, "owner@example.com");
  });

  test("login throws ApiHttpError with 401 status on incorrect credentials", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "Invalid email or password." }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    await assert.rejects(
      async () => {
        await client.login({
          email: "wrong@example.com",
          password: "badpassword",
        });
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.statusCode, 401);
        assert.ok(err.message.includes("Invalid email or password"));
        return true;
      }
    );
  });

  test("register throws ApiHttpError with 409 status on duplicate email", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "An account with this email address already exists." }),
        { status: 409, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    await assert.rejects(
      async () => {
        await client.register({
          email: "existing@example.com",
          password: "Password123!",
        });
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.statusCode, 409);
        return true;
      }
    );
  });

  test("getCurrentUser sends GET /api/v1/auth/me with credentials", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedOptions = init;
      return new Response(
        JSON.stringify({
          id: "uuid-9999",
          email: "me@example.com",
          full_name: "Current Profile",
          verified: true,
          is_active: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const user = await client.getCurrentUser();

    assert.ok(capturedUrl.endsWith("/api/v1/auth/me"));
    assert.strictEqual(capturedOptions?.method, "GET");
    assert.strictEqual(capturedOptions?.credentials, "include");
    assert.strictEqual(user.email, "me@example.com");
  });

  test("logout sends POST /api/v1/auth/logout", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (input) => {
      capturedUrl = String(input);
      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const res = await client.logout();

    assert.ok(capturedUrl.endsWith("/api/v1/auth/logout"));
    assert.strictEqual(res.success, true);
  });
});
