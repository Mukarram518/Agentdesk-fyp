import test, { describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import {
  ApiClient,
  ApiHttpError,
  ApiNetworkError,
  ApiTimeoutError,
} from "../lib/api/client";
import {
  listFaqs,
  createFaq,
  getFaq,
  updateFaq,
  deleteFaq,
  searchKnowledge,
  uploadFile,
  listFiles,
  getFileStatus,
  deleteFile,
} from "../lib/api/knowledge";
import type {
  FAQResponse,
  FAQCreatePayload,
  FAQUpdatePayload,
  KnowledgeFileResponse,
  KnowledgeFileListResponse,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
} from "../types/knowledge";

describe("Frontend Knowledge Base API Client", () => {
  const originalFetch = globalThis.fetch;
  let mockClient: ApiClient;

  const sampleFaq: FAQResponse = {
    id: "faq-1111-uuid",
    business_id: "biz-1234-uuid",
    question: "What are your business hours?",
    answer: "We are open Monday to Friday 9 AM to 6 PM.",
    tags: ["hours", "support"],
    language: "en",
    source_type: "FAQ",
    has_embedding: true,
    embedding_stale: false,
    source_file_id: null,
    chunk_index: null,
    page_number: null,
    section_title: null,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
  };

  const sampleFile: KnowledgeFileResponse = {
    id: "file-2222-uuid",
    business_id: "biz-1234-uuid",
    filename: "clinic_guide.pdf",
    size_bytes: 1048576,
    mime_type: "application/pdf",
    processing_status: "ready",
    error_message: null,
    created_at: "2026-11-20T11:00:00Z",
    updated_at: "2026-11-20T11:05:00Z",
  };

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("FAQ API Endpoints", () => {
    test("listFaqs sends GET /api/v1/knowledge with query parameters and credentials", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify([sampleFaq]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await mockClient.listFaqs({ language: "en", limit: 20, offset: 5 });

      assert.ok(capturedUrl.includes("/api/v1/knowledge"));
      assert.ok(capturedUrl.includes("language=en"));
      assert.ok(capturedUrl.includes("limit=20"));
      assert.ok(capturedUrl.includes("offset=5"));
      assert.strictEqual(capturedOptions?.method, "GET");
      assert.strictEqual(capturedOptions?.credentials, "include");
      assert.strictEqual(result.length, 1);
      assert.strictEqual(result[0].id, "faq-1111-uuid");
      assert.strictEqual(result[0].question, "What are your business hours?");
    });

    test("standalone listFaqs delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify([sampleFaq]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await listFaqs(undefined, { client: mockClient });
      assert.strictEqual(result.length, 1);
      assert.strictEqual(result[0].id, "faq-1111-uuid");
    });

    test("createFaq sends POST /api/v1/knowledge with JSON payload", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify(sampleFaq), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      };

      const payload: FAQCreatePayload = {
        question: "What are your business hours?",
        answer: "We are open Monday to Friday 9 AM to 6 PM.",
        tags: ["hours"],
        language: "en",
      };

      const result = await mockClient.createFaq(payload);

      assert.ok(capturedUrl.endsWith("/api/v1/knowledge"));
      assert.strictEqual(capturedOptions?.method, "POST");
      assert.strictEqual(capturedOptions?.credentials, "include");
      assert.deepStrictEqual(JSON.parse(String(capturedOptions?.body)), payload);
      assert.strictEqual(result.id, "faq-1111-uuid");
    });

    test("standalone createFaq delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleFaq), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await createFaq({ answer: "Test" }, { client: mockClient });
      assert.strictEqual(result.id, "faq-1111-uuid");
    });

    test("getFaq sends GET /api/v1/knowledge/:id", async () => {
      let capturedUrl = "";

      globalThis.fetch = async (input) => {
        capturedUrl = String(input);
        return new Response(JSON.stringify(sampleFaq), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await mockClient.getFaq("faq-1111-uuid");
      assert.ok(capturedUrl.endsWith("/api/v1/knowledge/faq-1111-uuid"));
      assert.strictEqual(result.id, "faq-1111-uuid");
    });

    test("standalone getFaq delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleFaq), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await getFaq("faq-1111-uuid", { client: mockClient });
      assert.strictEqual(result.id, "faq-1111-uuid");
    });

    test("updateFaq sends PATCH /api/v1/knowledge/:id", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify({ ...sampleFaq, answer: "Updated answer" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const payload: FAQUpdatePayload = { answer: "Updated answer" };
      const result = await mockClient.updateFaq("faq-1111-uuid", payload);

      assert.ok(capturedUrl.endsWith("/api/v1/knowledge/faq-1111-uuid"));
      assert.strictEqual(capturedOptions?.method, "PATCH");
      assert.deepStrictEqual(JSON.parse(String(capturedOptions?.body)), payload);
      assert.strictEqual(result.answer, "Updated answer");
    });

    test("standalone updateFaq delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleFaq), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await updateFaq("faq-1111-uuid", { answer: "Updated" }, { client: mockClient });
      assert.strictEqual(result.id, "faq-1111-uuid");
    });

    test("deleteFaq sends DELETE /api/v1/knowledge/:id and handles 204 No Content", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(null, { status: 204 });
      };

      await mockClient.deleteFaq("faq-1111-uuid");
      assert.ok(capturedUrl.endsWith("/api/v1/knowledge/faq-1111-uuid"));
      assert.strictEqual(capturedOptions?.method, "DELETE");
    });

    test("standalone deleteFaq delegates to provided client", async () => {
      let called = false;
      globalThis.fetch = async () => {
        called = true;
        return new Response(null, { status: 204 });
      };

      await deleteFaq("faq-1111-uuid", { client: mockClient });
      assert.strictEqual(called, true);
    });
  });

  describe("Semantic Search Endpoint", () => {
    test("searchKnowledge sends POST /api/v1/knowledge/search", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      const mockSearchResponse: KnowledgeSearchResponse = {
        query: "clinic timing",
        results: [
          {
            entry: sampleFaq,
            score: 0.12,
            score_metric: "cosine_distance",
            source_type: "FAQ",
          },
        ],
        total_results: 1,
      };

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify(mockSearchResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const payload: KnowledgeSearchRequest = {
        query: "clinic timing",
        top_k: 5,
        score_threshold: 0.25,
      };

      const result = await mockClient.searchKnowledge(payload);
      assert.ok(capturedUrl.endsWith("/api/v1/knowledge/search"));
      assert.strictEqual(capturedOptions?.method, "POST");
      assert.deepStrictEqual(JSON.parse(String(capturedOptions?.body)), payload);
      assert.strictEqual(result.results.length, 1);
      assert.strictEqual(result.results[0].score, 0.12);
    });

    test("standalone searchKnowledge delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ query: "test", results: [], total_results: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const result = await searchKnowledge({ query: "test" }, { client: mockClient });
      assert.strictEqual(result.query, "test");
    });
  });

  describe("Knowledge Document File Endpoints", () => {
    test("uploadKnowledgeFile sends POST /api/v1/knowledge/files with FormData", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(JSON.stringify(sampleFile), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        });
      };

      const blob = new Blob(["test file content"], { type: "application/pdf" });
      const result = await mockClient.uploadKnowledgeFile(blob, "clinic_guide.pdf");

      assert.ok(capturedUrl.endsWith("/api/v1/knowledge/files"));
      assert.strictEqual(capturedOptions?.method, "POST");
      assert.strictEqual(capturedOptions?.credentials, "include");
      assert.ok(capturedOptions?.body instanceof FormData);

      const headers = new Headers(capturedOptions?.headers);
      // Ensure Content-Type is NOT manually overridden to multipart/form-data
      // so fetch can set the boundary automatically
      assert.strictEqual(headers.get("Content-Type"), null);
      assert.strictEqual(result.filename, "clinic_guide.pdf");
      assert.strictEqual(result.processing_status, "ready");
    });

    test("standalone uploadFile delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleFile), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        });
      };

      const blob = new Blob(["test"]);
      const result = await uploadFile(blob, "test.pdf", { client: mockClient });
      assert.strictEqual(result.filename, "clinic_guide.pdf");
    });

    test("listKnowledgeFiles sends GET /api/v1/knowledge/files with query params", async () => {
      let capturedUrl = "";
      const mockFileListResponse: KnowledgeFileListResponse = {
        items: [sampleFile],
        total: 1,
        limit: 50,
        offset: 0,
      };

      globalThis.fetch = async (input) => {
        capturedUrl = String(input);
        return new Response(JSON.stringify(mockFileListResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await mockClient.listKnowledgeFiles({ status: "ready", limit: 10, offset: 0 });
      assert.ok(capturedUrl.includes("/api/v1/knowledge/files"));
      assert.ok(capturedUrl.includes("status=ready"));
      assert.ok(capturedUrl.includes("limit=10"));
      assert.strictEqual(result.items.length, 1);
      assert.strictEqual(result.total, 1);
    });

    test("standalone listFiles delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ items: [sampleFile], total: 1, limit: 50, offset: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const result = await listFiles(undefined, { client: mockClient });
      assert.strictEqual(result.items.length, 1);
    });

    test("getKnowledgeFileStatus sends GET /api/v1/knowledge/files/:id", async () => {
      let capturedUrl = "";

      globalThis.fetch = async (input) => {
        capturedUrl = String(input);
        return new Response(JSON.stringify(sampleFile), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await mockClient.getKnowledgeFileStatus("file-2222-uuid");
      assert.ok(capturedUrl.endsWith("/api/v1/knowledge/files/file-2222-uuid"));
      assert.strictEqual(result.id, "file-2222-uuid");
    });

    test("standalone getFileStatus delegates to provided client", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleFile), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const result = await getFileStatus("file-2222-uuid", { client: mockClient });
      assert.strictEqual(result.id, "file-2222-uuid");
    });

    test("deleteKnowledgeFile sends DELETE /api/v1/knowledge/files/:id", async () => {
      let capturedUrl = "";
      let capturedOptions: RequestInit | undefined;

      globalThis.fetch = async (input, init) => {
        capturedUrl = String(input);
        capturedOptions = init;
        return new Response(null, { status: 204 });
      };

      await mockClient.deleteKnowledgeFile("file-2222-uuid");
      assert.ok(capturedUrl.endsWith("/api/v1/knowledge/files/file-2222-uuid"));
      assert.strictEqual(capturedOptions?.method, "DELETE");
    });

    test("standalone deleteFile delegates to provided client", async () => {
      let called = false;
      globalThis.fetch = async () => {
        called = true;
        return new Response(null, { status: 204 });
      };

      await deleteFile("file-2222-uuid", { client: mockClient });
      assert.strictEqual(called, true);
    });
  });

  describe("API Client Error Handling", () => {
    test("throws ApiHttpError with 401 when unauthenticated", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify({ detail: "Not authenticated" }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "Content-Type": "application/json" },
        });
      };

      await assert.rejects(
        () => mockClient.listFaqs(),
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 401);
          return true;
        }
      );
    });

    test("throws ApiHttpError with 403 on non-owner operations", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify({ detail: "Forbidden: Owner role required." }), {
          status: 403,
          statusText: "Forbidden",
          headers: { "Content-Type": "application/json" },
        });
      };

      await assert.rejects(
        () => mockClient.createFaq({ answer: "Forbidden create" }),
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 403);
          return true;
        }
      );
    });

    test("throws ApiHttpError with 404 when file is not found", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify({ detail: "Knowledge file not found." }), {
          status: 404,
          statusText: "Not Found",
          headers: { "Content-Type": "application/json" },
        });
      };

      await assert.rejects(
        () => mockClient.getKnowledgeFileStatus("missing-uuid"),
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 404);
          return true;
        }
      );
    });

    test("throws ApiHttpError with 422 on validation failure", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({
            detail: [{ loc: ["body", "answer"], msg: "Answer cannot be empty", type: "value_error" }],
          }),
          {
            status: 422,
            statusText: "Unprocessable Entity",
            headers: { "Content-Type": "application/json" },
          }
        );
      };

      await assert.rejects(
        () => mockClient.createFaq({ answer: "" }),
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 422);
          return true;
        }
      );
    });

    test("throws ApiHttpError with sanitized 500 on server error", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ detail: "Failed to execute semantic search." }),
          {
            status: 500,
            statusText: "Internal Server Error",
            headers: { "Content-Type": "application/json" },
          }
        );
      };

      await assert.rejects(
        () => mockClient.searchKnowledge({ query: "crash query" }),
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          assert.strictEqual(err.status, 500);
          return true;
        }
      );
    });

    test("wraps network errors in ApiNetworkError", async () => {
      globalThis.fetch = async () => {
        throw new TypeError("Failed to fetch");
      };

      await assert.rejects(
        () => mockClient.listFaqs(),
        (err: unknown) => {
          assert.ok(err instanceof ApiNetworkError);
          return true;
        }
      );
    });

    test("wraps timeout aborts in ApiTimeoutError", async () => {
      globalThis.fetch = async () => {
        const err = new Error("The operation was aborted");
        err.name = "AbortError";
        throw err;
      };

      await assert.rejects(
        () => mockClient.listFaqs(),
        (err: unknown) => {
          assert.ok(err instanceof ApiTimeoutError);
          return true;
        }
      );
    });
  });
});
