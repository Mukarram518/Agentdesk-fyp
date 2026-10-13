import test, { describe, afterEach } from "node:test";
import assert from "node:assert/strict";
import { ApiClient, ApiHttpError } from "../lib/api/client";
import type { BusinessResponse } from "../types/business";

describe("Frontend Business API Client", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("createBusiness sends POST /api/v1/businesses with correct payload and credentials", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    const mockResponse: BusinessResponse = {
      id: "b-1234",
      name: "Acme Dental",
      slug: "acme-dental",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T10:00:00Z",
      updated_at: "2026-10-13T10:00:00Z",
    };

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedOptions = init;
      return new Response(JSON.stringify(mockResponse), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const payload = { name: "Acme Dental", slug: "acme-dental" };
    const res = await client.createBusiness(payload);

    assert.ok(capturedUrl.endsWith("/api/v1/businesses"));
    assert.strictEqual(capturedOptions?.method, "POST");
    assert.strictEqual(capturedOptions?.credentials, "include");

    const parsedBody = JSON.parse(String(capturedOptions?.body));
    assert.deepStrictEqual(parsedBody, payload);

    assert.strictEqual(res.id, "b-1234");
    assert.strictEqual(res.name, "Acme Dental");
    assert.strictEqual(res.slug, "acme-dental");
    assert.strictEqual(res.is_active, true);
    assert.strictEqual(res.role, "owner");
  });

  test("createBusiness throws ApiHttpError with 409 on duplicate slug conflict", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "A business with the slug 'acme-dental' already exists." }),
        { status: 409, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    await assert.rejects(
      async () => {
        await client.createBusiness({ name: "Acme Dental", slug: "acme-dental" });
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.statusCode, 409);
        assert.ok(err.message.includes("already exists"));
        return true;
      }
    );
  });

  test("createBusiness throws ApiHttpError with 422 on invalid input", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "Business name cannot be empty." }),
        { status: 422, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    await assert.rejects(
      async () => {
        await client.createBusiness({ name: "" });
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.statusCode, 422);
        assert.ok(err.message.includes("cannot be empty"));
        return true;
      }
    );
  });

  test("listBusinesses sends GET /api/v1/businesses and returns array with roles", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    const mockBusinesses: BusinessResponse[] = [
      {
        id: "b-1",
        name: "Clinic Alpha",
        slug: "clinic-alpha",
        is_active: true,
        role: "owner",
        created_at: "2026-10-13T10:00:00Z",
        updated_at: "2026-10-13T10:00:00Z",
      },
      {
        id: "b-2",
        name: "Partner Dental",
        slug: "partner-dental",
        is_active: true,
        role: "member",
        created_at: "2026-10-13T11:00:00Z",
        updated_at: "2026-10-13T11:00:00Z",
      },
    ];

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedOptions = init;
      return new Response(JSON.stringify(mockBusinesses), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const res = await client.listBusinesses();

    assert.ok(capturedUrl.endsWith("/api/v1/businesses"));
    assert.strictEqual(capturedOptions?.method, "GET");
    assert.strictEqual(capturedOptions?.credentials, "include");
    assert.strictEqual(res.length, 2);
    assert.strictEqual(res[0].role, "owner");
    assert.strictEqual(res[1].role, "member");
  });

  test("getCurrentBusiness sends GET /api/v1/businesses/current and returns current business", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    const mockBusiness: BusinessResponse = {
      id: "b-primary",
      name: "Primary Clinic",
      slug: "primary-clinic",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T10:00:00Z",
      updated_at: "2026-10-13T10:00:00Z",
    };

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedOptions = init;
      return new Response(JSON.stringify(mockBusiness), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const res = await client.getCurrentBusiness();

    assert.ok(capturedUrl.endsWith("/api/v1/businesses/current"));
    assert.strictEqual(capturedOptions?.method, "GET");
    assert.strictEqual(capturedOptions?.credentials, "include");
    assert.strictEqual(res.id, "b-primary");
    assert.strictEqual(res.name, "Primary Clinic");
    assert.strictEqual(res.role, "owner");
  });

  test("getCurrentBusiness throws typed ApiHttpError on 404 without triggering logout", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "No active business found for this account. Please complete business onboarding." }),
        { status: 404, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    await assert.rejects(
      async () => {
        await client.getCurrentBusiness();
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.statusCode, 404);
        assert.ok(err.message.includes("No active business found"));
        return true;
      }
    );
  });

  test("getBusinessById sends GET /api/v1/businesses/:id using the correct endpoint", async () => {
    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    const mockBusiness: BusinessResponse = {
      id: "b-specific-99",
      name: "Specific Medical",
      slug: "specific-medical",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T10:00:00Z",
      updated_at: "2026-10-13T10:00:00Z",
    };

    globalThis.fetch = async (input, init) => {
      capturedUrl = String(input);
      capturedOptions = init;
      return new Response(JSON.stringify(mockBusiness), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    const res = await client.getBusinessById("b-specific-99");

    assert.ok(capturedUrl.endsWith("/api/v1/businesses/b-specific-99"));
    assert.strictEqual(capturedOptions?.method, "GET");
    assert.strictEqual(capturedOptions?.credentials, "include");
    assert.strictEqual(res.id, "b-specific-99");
    assert.strictEqual(res.name, "Specific Medical");
  });

  test("getBusinessById throws typed ApiHttpError on 404 for unauthorized or missing business", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "Business not found." }),
        { status: 404, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ApiClient("http://127.0.0.1:8000");
    await assert.rejects(
      async () => {
        await client.getBusinessById("b-nonexistent");
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.statusCode, 404);
        assert.ok(err.message.includes("Business not found"));
        return true;
      }
    );
  });
});
