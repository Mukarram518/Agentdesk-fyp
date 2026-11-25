import test, { describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  KnowledgeStore,
  INITIAL_KNOWLEDGE_STATE,
  extractApiErrorMessage,
} from "../lib/knowledge/knowledge-store";
import { useKnowledge, type UseKnowledgeReturn } from "../lib/knowledge/use-knowledge";
import { BusinessContext, type BusinessContextType } from "../lib/business/BusinessContext";
import {
  ApiClient,
  ApiHttpError,
} from "../lib/api/client";
import {
  isKnowledgeLanguage,
  isKnowledgeFileStatus,
  type FAQResponse,
  type KnowledgeFileResponse,
  type KnowledgeSearchResultItem,
} from "../types/knowledge";
import type { BusinessResponse } from "../types/business";

describe("Frontend Knowledge State Store", () => {
  const originalFetch = globalThis.fetch;
  let mockClient: ApiClient;

  const sampleFaqAlpha: FAQResponse = {
    id: "faq-alpha-1",
    business_id: "biz-alpha",
    question: "Alpha hours?",
    answer: "Open 9 AM to 5 PM.",
    tags: ["hours"],
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

  const sampleFilePending: KnowledgeFileResponse = {
    id: "file-pending-1",
    business_id: "biz-alpha",
    filename: "policy.pdf",
    size_bytes: 500000,
    mime_type: "application/pdf",
    processing_status: "pending",
    error_message: null,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: null,
  };

  const sampleFileReady: KnowledgeFileResponse = {
    id: "file-pending-1",
    business_id: "biz-alpha",
    filename: "policy.pdf",
    size_bytes: 500000,
    mime_type: "application/pdf",
    processing_status: "ready",
    error_message: null,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:02:00Z",
  };

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("Initial State & Subscriptions", () => {
    test("initializes with empty lists, zero flags, and null errors", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      const snap = store.getSnapshot();

      assert.deepStrictEqual(snap.faqs, []);
      assert.deepStrictEqual(snap.files, []);
      assert.strictEqual(snap.filesTotal, 0);
      assert.strictEqual(snap.searchResults, null);
      assert.strictEqual(snap.searchQuery, null);
      assert.strictEqual(snap.isLoadingFaqs, false);
      assert.strictEqual(snap.isLoadingFiles, false);
      assert.strictEqual(snap.isSearching, false);
      assert.strictEqual(snap.isMutating, false);
      assert.strictEqual(snap.isUploading, false);
      assert.strictEqual(snap.error, null);
      assert.strictEqual(snap.successMessage, null);
    });

    test("getServerSnapshot returns stable, frozen initial reference", () => {
      const store = new KnowledgeStore();
      const serverSnap = store.getServerSnapshot();
      assert.deepStrictEqual(serverSnap, INITIAL_KNOWLEDGE_STATE);
      assert.ok(Object.isFrozen(serverSnap));
    });

    test("subscribe notifies listeners on state changes and allows unsubscribe", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      let callCount = 0;
      const unsubscribe = store.subscribe(() => {
        callCount++;
      });

      store.clearError(); // No change when error is null
      assert.strictEqual(callCount, 0);

      store.clearSearch(); // State change
      assert.strictEqual(callCount, 1);

      unsubscribe();
      store.clearSearch();
      assert.strictEqual(callCount, 1);
    });
  });

  describe("Tenant Isolation & Business Switching", () => {
    test("fetchFaqs and fetchFiles return null without network call if businessId is null", async () => {
      let networkCalled = false;
      globalThis.fetch = async () => {
        networkCalled = true;
        return new Response("[]", { status: 200 });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: null });
      const faqs = await store.fetchFaqs();
      const files = await store.fetchFiles();

      assert.strictEqual(faqs, null);
      assert.strictEqual(files, null);
      assert.strictEqual(networkCalled, false);
    });

    test("switching businessId immediately wipes state to prevent cross-tenant data leakage", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });

      // Seed store with Alpha data
      (store as unknown as { setState: (p: unknown) => void }).setState({
        faqs: [sampleFaqAlpha],
        files: [sampleFilePending],
        filesTotal: 1,
        searchResults: [],
      });

      assert.strictEqual(store.getSnapshot().faqs.length, 1);
      assert.strictEqual(store.getSnapshot().files.length, 1);

      // Switch to Beta (without autoFetch)
      store.setBusinessId("biz-beta", false);

      assert.strictEqual(store.getBusinessId(), "biz-beta");
      assert.deepStrictEqual(store.getSnapshot().faqs, []);
      assert.deepStrictEqual(store.getSnapshot().files, []);
      assert.strictEqual(store.getSnapshot().filesTotal, 0);
      assert.strictEqual(store.getSnapshot().searchResults, null);
    });

    test("setting identical businessId is a no-op and preserves state", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        faqs: [sampleFaqAlpha],
      });

      store.setBusinessId("biz-alpha");
      assert.strictEqual(store.getSnapshot().faqs.length, 1);
    });

    test("stale in-flight fetch from previous business cannot overwrite state after switch", async () => {
      let resolveAlphaFetch: (v: Response) => void;
      const alphaPromise = new Promise<Response>((res) => {
        resolveAlphaFetch = res;
      });

      globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.includes("/api/v1/knowledge") && !url.includes("files")) {
          return alphaPromise;
        }
        return new Response("[]", { status: 200 });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });

      // 1. Start fetch for Alpha
      const alphaFetchPromise = store.fetchFaqs();

      // 2. Switch business to Beta before Alpha fetch resolves
      store.setBusinessId("biz-beta", false);
      assert.deepStrictEqual(store.getSnapshot().faqs, []);

      // 3. Resolve Alpha's delayed response
      resolveAlphaFetch!(
        new Response(JSON.stringify([sampleFaqAlpha]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
      await alphaFetchPromise;

      // 4. Verify Alpha's data did NOT clobber Beta's clean state
      assert.deepStrictEqual(store.getSnapshot().faqs, []);
      assert.strictEqual(store.getSnapshot().isLoadingFaqs, false);
    });

    test("stale error from cancelled previous request does not pollute new business state", async () => {
      let rejectAlphaFetch: (err: Error) => void;
      const alphaPromise = new Promise<Response>((_, rej) => {
        rejectAlphaFetch = rej;
      });

      globalThis.fetch = async () => alphaPromise;

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      const alphaFetchPromise = store.fetchFaqs();

      // Switch business
      store.setBusinessId("biz-beta", false);

      // Trigger error on previous business's request
      rejectAlphaFetch!(new Error("Network drop on Alpha"));
      await assert.rejects(alphaFetchPromise);

      // Verify error did not land in Beta state
      assert.strictEqual(store.getSnapshot().error, null);
    });
  });

  describe("Concurrency & Request ID Isolation", () => {
    test("concurrent fetchFaqs and fetchFiles (e.g. via fetchAll) both update their respective state without collision", async () => {
      globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.includes("/api/v1/knowledge/files")) {
          return new Response(
            JSON.stringify({ items: [sampleFilePending], total: 1, limit: 50, offset: 0 }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/knowledge")) {
          return new Response(
            JSON.stringify([sampleFaqAlpha]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("{}", { status: 200 });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      await store.fetchAll();

      const snapshot = store.getSnapshot();
      assert.strictEqual(snapshot.faqs.length, 1);
      assert.strictEqual(snapshot.faqs[0].id, "faq-alpha-1");
      assert.strictEqual(snapshot.isLoadingFaqs, false);

      assert.strictEqual(snapshot.files.length, 1);
      assert.strictEqual(snapshot.files[0].id, "file-pending-1");
      assert.strictEqual(snapshot.filesTotal, 1);
      assert.strictEqual(snapshot.isLoadingFiles, false);
      assert.strictEqual(snapshot.error, null);
    });

    test("newer fetchFaqs request invalidates older request in the same operation", async () => {
      let resolveFirstFetch: (v: Response) => void;
      const firstPromise = new Promise<Response>((res) => {
        resolveFirstFetch = res;
      });

      let callIndex = 0;
      globalThis.fetch = async () => {
        callIndex++;
        if (callIndex === 1) {
          return firstPromise;
        }
        return new Response(
          JSON.stringify([{ ...sampleFaqAlpha, id: "faq-newer-2" }]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });

      // 1. Dispatch first (slow) fetch
      const firstFetchPromise = store.fetchFaqs();

      // 2. Dispatch second (fast) fetch immediately
      const secondFetchPromise = store.fetchFaqs();
      await secondFetchPromise;

      assert.strictEqual(store.getSnapshot().faqs[0].id, "faq-newer-2");

      // 3. Resolve the first (stale) fetch with older data
      resolveFirstFetch!(
        new Response(
          JSON.stringify([{ ...sampleFaqAlpha, id: "faq-older-1" }]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
      await firstFetchPromise;

      // 4. Stale first fetch must NOT overwrite the newer state
      assert.strictEqual(store.getSnapshot().faqs.length, 1);
      assert.strictEqual(store.getSnapshot().faqs[0].id, "faq-newer-2");
    });

    test("newer fetchFiles request invalidates older request in the same operation", async () => {
      let resolveFirstFetch: (v: Response) => void;
      const firstPromise = new Promise<Response>((res) => {
        resolveFirstFetch = res;
      });

      let callIndex = 0;
      globalThis.fetch = async () => {
        callIndex++;
        if (callIndex === 1) {
          return firstPromise;
        }
        return new Response(
          JSON.stringify({ items: [{ ...sampleFilePending, id: "file-newer-2" }], total: 1 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });

      // 1. Dispatch first (slow) fetch
      const firstFetchPromise = store.fetchFiles();

      // 2. Dispatch second (fast) fetch immediately
      const secondFetchPromise = store.fetchFiles();
      await secondFetchPromise;

      assert.strictEqual(store.getSnapshot().files[0].id, "file-newer-2");

      // 3. Resolve the first (stale) fetch with older data
      resolveFirstFetch!(
        new Response(
          JSON.stringify({ items: [{ ...sampleFilePending, id: "file-older-1" }], total: 1 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
      await firstFetchPromise;

      // 4. Stale first fetch must NOT overwrite the newer state
      assert.strictEqual(store.getSnapshot().files.length, 1);
      assert.strictEqual(store.getSnapshot().files[0].id, "file-newer-2");
    });

    test("switching businesses invalidates pending requests across FAQs, files, and search", async () => {
      let resolveFaqs: (v: Response) => void;
      const faqsPromise = new Promise<Response>((res) => {
        resolveFaqs = res;
      });
      let resolveFiles: (v: Response) => void;
      const filesPromise = new Promise<Response>((res) => {
        resolveFiles = res;
      });
      let resolveSearch: (v: Response) => void;
      const searchPromise = new Promise<Response>((res) => {
        resolveSearch = res;
      });

      globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.includes("/search")) return searchPromise;
        if (url.includes("/files")) return filesPromise;
        if (url.includes("/api/v1/knowledge")) return faqsPromise;
        return new Response("{}", { status: 200 });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      const pFaqs = store.fetchFaqs();
      const pFiles = store.fetchFiles();
      const pSearch = store.search("alpha query");

      // Switch business to Beta before any response resolves
      store.setBusinessId("biz-beta", false);

      // Resolve all old responses from Alpha
      resolveFaqs!(
        new Response(JSON.stringify([sampleFaqAlpha]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
      resolveFiles!(
        new Response(JSON.stringify({ items: [sampleFilePending], total: 1 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
      resolveSearch!(
        new Response(
          JSON.stringify({
            query: "alpha query",
            results: [{ entry: sampleFaqAlpha, score: 0.1, score_metric: "cosine_distance" }],
            total_results: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );

      await Promise.allSettled([pFaqs, pFiles, pSearch]);

      // All three slices must remain clean for Beta
      const snap = store.getSnapshot();
      assert.deepStrictEqual(snap.faqs, []);
      assert.strictEqual(snap.isLoadingFaqs, false);
      assert.deepStrictEqual(snap.files, []);
      assert.strictEqual(snap.filesTotal, 0);
      assert.strictEqual(snap.isLoadingFiles, false);
      assert.strictEqual(snap.searchResults, null);
      assert.strictEqual(snap.isSearching, false);
    });

    test("semantic search stale request protection discards older search response", async () => {
      let resolveFirstSearch: (v: Response) => void;
      const firstPromise = new Promise<Response>((res) => {
        resolveFirstSearch = res;
      });

      let searchCount = 0;
      globalThis.fetch = async () => {
        searchCount++;
        if (searchCount === 1) {
          return firstPromise;
        }
        return new Response(
          JSON.stringify({
            query: "hours newer",
            results: [
              {
                entry: { ...sampleFaqAlpha, id: "result-newer" },
                score: 0.05,
                score_metric: "cosine_distance",
              },
            ],
            total_results: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });

      // 1. Dispatch first search query (slow)
      const firstSearchPromise = store.search("hours older");

      // 2. Dispatch second search query (fast)
      const secondSearchPromise = store.search("hours newer");
      await secondSearchPromise;

      assert.strictEqual(store.getSnapshot().searchQuery, "hours newer");
      assert.strictEqual(store.getSnapshot().searchResults?.[0]?.entry?.id, "result-newer");

      // 3. Resolve first (older) search
      resolveFirstSearch!(
        new Response(
          JSON.stringify({
            query: "hours older",
            results: [
              {
                entry: { ...sampleFaqAlpha, id: "result-older" },
                score: 0.2,
                score_metric: "cosine_distance",
              },
            ],
            total_results: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
      await firstSearchPromise;

      // 4. State must still hold the newer search results
      assert.strictEqual(store.getSnapshot().searchQuery, "hours newer");
      assert.strictEqual(store.getSnapshot().searchResults?.[0]?.entry?.id, "result-newer");
    });
  });

  describe("FAQ State Mutations", () => {
    test("fetchFaqs loads entries and updates loading state", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify([sampleFaqAlpha]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      const res = await store.fetchFaqs();

      assert.strictEqual(res?.length, 1);
      assert.strictEqual(store.getSnapshot().faqs.length, 1);
      assert.strictEqual(store.getSnapshot().faqs[0].id, "faq-alpha-1");
      assert.strictEqual(store.getSnapshot().isLoadingFaqs, false);
      assert.strictEqual(store.getSnapshot().error, null);
    });

    test("createFaq prepends new entry and sets success message", async () => {
      const createdFaq: FAQResponse = {
        ...sampleFaqAlpha,
        id: "faq-new-id",
        question: "New question",
      };

      globalThis.fetch = async () => {
        return new Response(JSON.stringify(createdFaq), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      const created = await store.createFaq({
        question: "New question",
        answer: "New answer",
      });

      assert.strictEqual(created.id, "faq-new-id");
      assert.strictEqual(store.getSnapshot().faqs.length, 1);
      assert.strictEqual(store.getSnapshot().faqs[0].id, "faq-new-id");
      assert.strictEqual(store.getSnapshot().isMutating, false);
      assert.ok(store.getSnapshot().successMessage?.includes("successfully"));
    });

    test("updateFaq updates specific item in-place", async () => {
      const updatedFaq: FAQResponse = {
        ...sampleFaqAlpha,
        answer: "Updated answer text.",
      };

      globalThis.fetch = async () => {
        return new Response(JSON.stringify(updatedFaq), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        faqs: [sampleFaqAlpha],
      });

      const updated = await store.updateFaq("faq-alpha-1", { answer: "Updated answer text." });
      assert.strictEqual(updated.answer, "Updated answer text.");
      assert.strictEqual(store.getSnapshot().faqs[0].answer, "Updated answer text.");
      assert.strictEqual(store.getSnapshot().isMutating, false);
    });

    test("deleteFaq removes item from list", async () => {
      globalThis.fetch = async () => {
        return new Response(null, { status: 204 });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        faqs: [sampleFaqAlpha],
      });

      await store.deleteFaq("faq-alpha-1");
      assert.strictEqual(store.getSnapshot().faqs.length, 0);
      assert.strictEqual(store.getSnapshot().isMutating, false);
    });

    test("mutations throw error and record message if no business is selected", async () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: null });

      await assert.rejects(
        () => store.createFaq({ answer: "Test" }),
        /No active business selected/
      );
      await assert.rejects(
        () => store.updateFaq("id", { answer: "Test" }),
        /No active business selected/
      );
      await assert.rejects(
        () => store.deleteFaq("id"),
        /No active business selected/
      );
    });
  });

  describe("Document File State & Polling", () => {
    test("fetchFiles loads documents and sets total count", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ items: [sampleFilePending], total: 1, limit: 50, offset: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      const files = await store.fetchFiles();

      assert.strictEqual(files?.length, 1);
      assert.strictEqual(store.getSnapshot().files.length, 1);
      assert.strictEqual(store.getSnapshot().filesTotal, 1);
      assert.strictEqual(store.getSnapshot().isLoadingFiles, false);
    });

    test("uploadFile prepends new file, increments total, and resets uploading flag", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleFilePending), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      const uploaded = await store.uploadFile(new Blob(["content"]), "policy.pdf");

      assert.strictEqual(uploaded.filename, "policy.pdf");
      assert.strictEqual(store.getSnapshot().files.length, 1);
      assert.strictEqual(store.getSnapshot().filesTotal, 1);
      assert.strictEqual(store.getSnapshot().isUploading, false);
      assert.ok(store.getSnapshot().successMessage?.includes("policy.pdf"));
    });

    test("deleteFile cascades and removes associated chunks from faqs list", async () => {
      const chunkFaq: FAQResponse = {
        ...sampleFaqAlpha,
        id: "chunk-1",
        source_type: "document_chunk",
        source_file_id: "file-pending-1",
      };

      globalThis.fetch = async () => {
        return new Response(null, { status: 204 });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [sampleFilePending],
        filesTotal: 1,
        faqs: [sampleFaqAlpha, chunkFaq],
      });

      await store.deleteFile("file-pending-1");

      assert.strictEqual(store.getSnapshot().files.length, 0);
      assert.strictEqual(store.getSnapshot().filesTotal, 0);
      // Chunk associated with file-pending-1 should be removed, while standalone FAQ is kept
      assert.strictEqual(store.getSnapshot().faqs.length, 1);
      assert.strictEqual(store.getSnapshot().faqs[0].id, "faq-alpha-1");
    });

    test("refreshFileStatus updates specific file status in list", async () => {
      globalThis.fetch = async () => {
        return new Response(JSON.stringify(sampleFileReady), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [sampleFilePending],
      });

      assert.strictEqual(store.getSnapshot().files[0].processing_status, "pending");

      const updated = await store.refreshFileStatus("file-pending-1");
      assert.strictEqual(updated?.processing_status, "ready");
      assert.strictEqual(store.getSnapshot().files[0].processing_status, "ready");
    });

    test("pollFiles background updates files without setting main isLoadingFiles spinner", async () => {
      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ items: [sampleFileReady], total: 1, limit: 50, offset: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [sampleFilePending],
        isLoadingFiles: false,
      });

      const polled = await store.pollFiles();
      assert.strictEqual(polled?.length, 1);
      assert.strictEqual(store.getSnapshot().files[0].processing_status, "ready");
      assert.strictEqual(store.getSnapshot().isLoadingFiles, false);
    });

    test("pollFiles fails silently on transient network errors without wiping visible files", async () => {
      globalThis.fetch = async () => {
        throw new TypeError("Failed to fetch");
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [sampleFilePending],
      });

      const res = await store.pollFiles();
      assert.strictEqual(res, null);
      // Existing file should remain intact
      assert.strictEqual(store.getSnapshot().files.length, 1);
      assert.strictEqual(store.getSnapshot().error, null);
    });
  });

  describe("Semantic Search State", () => {
    test("search trims query and stores results", async () => {
      const mockResultItem: KnowledgeSearchResultItem = {
        entry: sampleFaqAlpha,
        score: 0.15,
        score_metric: "cosine_distance",
      };

      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({ query: "hours", results: [mockResultItem], total_results: 1 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      const results = await store.search("  hours  ", 5);

      assert.strictEqual(results.length, 1);
      assert.strictEqual(store.getSnapshot().searchQuery, "hours");
      assert.strictEqual(store.getSnapshot().searchResults?.length, 1);
      assert.strictEqual(store.getSnapshot().isSearching, false);
    });

    test("search with whitespace or empty query clears search results without calling API", async () => {
      let networkCalled = false;
      globalThis.fetch = async () => {
        networkCalled = true;
        return new Response("{}", { status: 200 });
      };

      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        searchResults: [{ entry: sampleFaqAlpha, score: 0.1, score_metric: "cosine_distance" }],
        searchQuery: "old query",
      });

      const results = await store.search("   ");
      assert.deepStrictEqual(results, []);
      assert.strictEqual(store.getSnapshot().searchResults, null);
      assert.strictEqual(store.getSnapshot().searchQuery, null);
      assert.strictEqual(networkCalled, false);
    });

    test("clearSearch resets searchResults and searchQuery", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        searchResults: [],
        searchQuery: "query",
        isSearching: true,
      });

      store.clearSearch();
      assert.strictEqual(store.getSnapshot().searchResults, null);
      assert.strictEqual(store.getSnapshot().searchQuery, null);
      assert.strictEqual(store.getSnapshot().isSearching, false);
    });
  });

  describe("Error Message Extraction Helper", () => {
    test("extracts detail string from ApiHttpError", () => {
      const err = new ApiHttpError(422, "Unprocessable", { detail: "Answer cannot be empty." });
      assert.strictEqual(extractApiErrorMessage(err), "Answer cannot be empty.");
    });

    test("extracts first validation error from Pydantic detail array", () => {
      const err = new ApiHttpError(422, "Unprocessable", {
        detail: [{ loc: ["body", "answer"], msg: "String should have at least 1 character" }],
      });
      assert.strictEqual(
        extractApiErrorMessage(err),
        "String should have at least 1 character"
      );
    });

    test("extracts message property from object if detail is absent", () => {
      const err = new ApiHttpError(400, "Bad Request", { message: "Custom message" });
      assert.strictEqual(extractApiErrorMessage(err), "Custom message");
    });

    test("falls back to standard Error message or default string", () => {
      assert.strictEqual(extractApiErrorMessage(new Error("Disk full")), "Disk full");
      assert.strictEqual(extractApiErrorMessage("unknown error"), "An unexpected error occurred.");
    });
  });

  describe("Type Guards", () => {
    test("isKnowledgeLanguage identifies valid languages", () => {
      assert.strictEqual(isKnowledgeLanguage("en"), true);
      assert.strictEqual(isKnowledgeLanguage("ur"), true);
      assert.strictEqual(isKnowledgeLanguage("mixed"), true);
      assert.strictEqual(isKnowledgeLanguage("EN"), true);
      assert.strictEqual(isKnowledgeLanguage("fr"), false);
      assert.strictEqual(isKnowledgeLanguage(123), false);
    });

    test("isKnowledgeFileStatus identifies valid file statuses", () => {
      assert.strictEqual(isKnowledgeFileStatus("pending"), true);
      assert.strictEqual(isKnowledgeFileStatus("processing"), true);
      assert.strictEqual(isKnowledgeFileStatus("ready"), true);
      assert.strictEqual(isKnowledgeFileStatus("failed"), true);
      assert.strictEqual(isKnowledgeFileStatus("archived"), false);
      assert.strictEqual(isKnowledgeFileStatus(null), false);
    });
  });

  describe("Frontend useKnowledge Hook & Polling Integration", () => {
    const sampleBusiness: BusinessResponse = {
      id: "biz-context-id",
      name: "Apex Healthcare",
      slug: "apex-healthcare",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T10:00:00Z",
      updated_at: "2026-10-13T10:00:00Z",
    };

    test("renders safely outside of BusinessProvider without throwing", () => {
      let capturedHookReturn!: UseKnowledgeReturn;

      function TestComponent() {
        capturedHookReturn = useKnowledge({ client: mockClient, autoFetch: false, autoPoll: false });
        return React.createElement("div", null, "rendered");
      }

      const html = renderToStaticMarkup(React.createElement(TestComponent));
      assert.ok(html.includes("rendered"));
      assert.deepStrictEqual(capturedHookReturn.faqs, []);
      assert.deepStrictEqual(capturedHookReturn.files, []);
      assert.strictEqual(capturedHookReturn.filesTotal, 0);
      assert.strictEqual(capturedHookReturn.isLoading, false);
      assert.strictEqual(capturedHookReturn.isPolling, false);
      assert.strictEqual(typeof capturedHookReturn.fetchFaqs, "function");
      assert.strictEqual(typeof capturedHookReturn.fetchFiles, "function");
      assert.strictEqual(typeof capturedHookReturn.createFaq, "function");
      assert.strictEqual(typeof capturedHookReturn.uploadFile, "function");
      assert.strictEqual(typeof capturedHookReturn.search, "function");
    });

    test("uses explicit businessId when provided in options", () => {
      let capturedHookReturn!: UseKnowledgeReturn;

      function TestComponent() {
        capturedHookReturn = useKnowledge({
          businessId: "biz-explicit-101",
          client: mockClient,
          autoFetch: false,
          autoPoll: false,
        });
        return React.createElement("div", null, "rendered");
      }

      renderToStaticMarkup(React.createElement(TestComponent));
      assert.strictEqual(capturedHookReturn.store.getBusinessId(), "biz-explicit-101");
    });

    test("resolves businessId dynamically from BusinessContext when inside a provider", () => {
      let capturedHookReturn!: UseKnowledgeReturn;

      function TestComponent() {
        capturedHookReturn = useKnowledge({ client: mockClient, autoFetch: false, autoPoll: false });
        return React.createElement(
          "div",
          null,
          capturedHookReturn.store.getBusinessId() || "none"
        );
      }

      const mockBusinessContextValue: BusinessContextType = {
        businesses: [sampleBusiness],
        currentBusiness: sampleBusiness,
        isLoadingBusiness: false,
        businessError: null,
        refreshBusinesses: async () => {},
        createBusiness: async () => sampleBusiness,
      };

      const html = renderToStaticMarkup(
        React.createElement(
          BusinessContext.Provider,
          { value: mockBusinessContextValue },
          React.createElement(TestComponent)
        )
      );

      assert.ok(html.includes("biz-context-id"));
      assert.strictEqual(capturedHookReturn.store.getBusinessId(), "biz-context-id");
    });

    test("computes isPolling true when files contain pending status", () => {
      let capturedHookReturn!: UseKnowledgeReturn;
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [sampleFilePending],
      });

      function TestComponent() {
        capturedHookReturn = useKnowledge({
          store,
          autoFetch: false,
          autoPoll: false,
        });
        return React.createElement("div", null, "rendered");
      }

      renderToStaticMarkup(React.createElement(TestComponent));
      assert.strictEqual(capturedHookReturn.isPolling, true);
    });

    test("computes isPolling true when files contain processing status", () => {
      let capturedHookReturn!: UseKnowledgeReturn;
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [{ ...sampleFilePending, processing_status: "processing" }],
      });

      function TestComponent() {
        capturedHookReturn = useKnowledge({
          store,
          autoFetch: false,
          autoPoll: false,
        });
        return React.createElement("div", null, "rendered");
      }

      renderToStaticMarkup(React.createElement(TestComponent));
      assert.strictEqual(capturedHookReturn.isPolling, true);
    });

    test("computes isPolling false when all files are ready or failed", () => {
      let capturedHookReturn!: UseKnowledgeReturn;
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-alpha" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [
          sampleFileReady,
          { ...sampleFilePending, id: "file-failed-1", processing_status: "failed" },
        ],
      });

      function TestComponent() {
        capturedHookReturn = useKnowledge({
          store,
          autoFetch: false,
          autoPoll: false,
        });
        return React.createElement("div", null, "rendered");
      }

      renderToStaticMarkup(React.createElement(TestComponent));
      assert.strictEqual(capturedHookReturn.isPolling, false);
    });
  });
});
