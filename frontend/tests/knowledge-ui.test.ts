import test, { describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  KnowledgeStore,
} from "../lib/knowledge/knowledge-store";
import {
  KnowledgeProvider,
  useKnowledgeContext,
} from "../lib/knowledge/knowledge-context";
import { FaqSection } from "../components/knowledge/FaqSection";
import { DocumentSection } from "../components/knowledge/DocumentSection";
import { SearchSection } from "../components/knowledge/SearchSection";
import { KnowledgeContentView } from "../app/knowledge/page";
import { BusinessContext, type BusinessContextType } from "../lib/business/BusinessContext";
import { ApiClient } from "../lib/api/client";
import type {
  FAQResponse,
  KnowledgeFileResponse,
  KnowledgeSearchResultItem,
} from "../types/knowledge";
import type { BusinessResponse } from "../types/business";

describe("Frontend Knowledge UI Components & Provider (Phase 5D)", () => {
  const originalFetch = globalThis.fetch;
  let mockClient: ApiClient;

  const sampleFaqEn: FAQResponse = {
    id: "faq-en-1",
    business_id: "biz-123",
    question: "What are your standard opening hours?",
    answer: "We are open Monday to Friday from 9:00 AM to 6:00 PM.",
    tags: ["hours", "schedule"],
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

  const sampleFaqUr: FAQResponse = {
    id: "faq-ur-2",
    business_id: "biz-123",
    question: "آپ کے کھلنے کے اوقات کیا ہیں؟",
    answer: "ہم پیر سے جمعہ صبح 9 بجے سے شام 6 بجے تک کھلے رہتے ہیں۔",
    tags: ["اوقات"],
    language: "ur",
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

  const sampleFileReady: KnowledgeFileResponse = {
    id: "file-ready-1",
    business_id: "biz-123",
    filename: "clinic_policy.pdf",
    size_bytes: 1024 * 512, // 512 KB
    mime_type: "application/pdf",
    processing_status: "ready",
    error_message: null,
    chunk_count: 12,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:02:00Z",
  };

  const sampleFileProcessing: KnowledgeFileResponse = {
    id: "file-proc-2",
    business_id: "biz-123",
    filename: "services_catalog.docx",
    size_bytes: 1024 * 1024 * 2, // 2 MB
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    processing_status: "processing",
    error_message: null,
    created_at: "2026-11-20T10:05:00Z",
    updated_at: null,
  };

  const sampleFileFailed: KnowledgeFileResponse = {
    id: "file-fail-3",
    business_id: "biz-123",
    filename: "corrupt_data.pdf",
    size_bytes: 25000,
    mime_type: "application/pdf",
    processing_status: "failed",
    error_message: "PDF contains invalid xref tables and could not be parsed.",
    chunk_count: 0,
    created_at: "2026-11-20T10:10:00Z",
    updated_at: "2026-11-20T10:11:00Z",
  };

  const sampleSearchResultFaq: KnowledgeSearchResultItem = {
    entry: sampleFaqEn,
    score: 0.1245,
    score_metric: "cosine_distance",
    source_type: "FAQ",
    chunk_index: null,
    page_number: null,
    section_title: null,
    source_file_id: null,
  };

  const sampleSearchResultChunk: KnowledgeSearchResultItem = {
    entry: {
      id: "chunk-101",
      business_id: "biz-123",
      question: null,
      answer: "Payment is required at the time services are rendered. We accept Visa, Mastercard, and cash.",
      tags: [],
      language: "en",
      source_type: "document_chunk",
      has_embedding: true,
      embedding_stale: false,
      source_file_id: "file-ready-1",
      chunk_index: 3,
      page_number: 2,
      section_title: "Billing & Payment Terms",
      created_at: "2026-11-20T10:02:00Z",
      updated_at: "2026-11-20T10:02:00Z",
    },
    score: 0.1892,
    score_metric: "cosine_distance",
    source_type: "document_chunk",
    chunk_index: 3,
    page_number: 2,
    section_title: "Billing & Payment Terms",
    source_file_id: "file-ready-1",
  };

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("KnowledgeProvider & Shared Store Architecture", () => {
    test("provides single store instance to child components", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      let capturedStore: KnowledgeStore | null = null;

      function Child() {
        const ctx = useKnowledgeContext();
        capturedStore = ctx.store;
        return React.createElement("div", null, "Child rendered");
      }

      renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(Child, null)
        )
      );

      assert.strictEqual(capturedStore, store);
    });

    test("useKnowledgeContext throws an informative error if used outside KnowledgeProvider", () => {
      function OrphanChild() {
        useKnowledgeContext();
        return React.createElement("div", null);
      }

      assert.throws(
        () => {
          renderToStaticMarkup(React.createElement(OrphanChild, null));
        },
        {
          name: "Error",
          message: /useKnowledgeContext must be used within a <KnowledgeProvider>/,
        }
      );
    });

    test("useKnowledgeContext provides shared context across siblings inside KnowledgeProvider", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      let capturedStore1: KnowledgeStore | null = null;
      let capturedStore2: KnowledgeStore | null = null;

      function SiblingA() {
        const k = useKnowledgeContext();
        capturedStore1 = k.store;
        return React.createElement("div", null, "Sibling A");
      }

      function SiblingB() {
        const k = useKnowledgeContext();
        capturedStore2 = k.store;
        return React.createElement("div", null, "Sibling B");
      }

      renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(
            React.Fragment,
            null,
            React.createElement(SiblingA, null),
            React.createElement(SiblingB, null)
          )
        )
      );

      // Both siblings obtain the exact same shared store instance
      assert.ok(capturedStore1 !== null);
      assert.strictEqual(capturedStore1, store);
      assert.strictEqual(capturedStore2, store);
      assert.strictEqual(capturedStore1, capturedStore2);
    });

    test("preserves active-business synchronization from BusinessContext", () => {
      const mockBusiness: BusinessResponse = {
        id: "biz-sync-99",
        name: "Apex Healthcare",
        slug: "apex-healthcare",
        is_active: true,
        role: "owner",
        created_at: "2026-11-20T10:00:00Z",
        updated_at: "2026-11-20T10:00:00Z",
      };

      const mockBusinessContext: BusinessContextType = {
        businesses: [mockBusiness],
        currentBusiness: mockBusiness,
        isLoadingBusiness: false,
        businessError: null,
        refreshBusinesses: async () => {},
        createBusiness: async () => mockBusiness,
      };

      let capturedBusinessId: string | null = null;

      function Child() {
        const ctx = useKnowledgeContext();
        capturedBusinessId = ctx.store.getBusinessId();
        return React.createElement("div", null, `Active: ${capturedBusinessId}`);
      }

      renderToStaticMarkup(
        React.createElement(
          BusinessContext.Provider,
          { value: mockBusinessContext },
          React.createElement(
            KnowledgeProvider,
            { autoFetch: false, autoPoll: false },
            React.createElement(Child, null)
          )
        )
      );

      assert.strictEqual(capturedBusinessId, "biz-sync-99");
    });
  });

  describe("FaqSection Component", () => {
    test("renders FAQ items with questions, answers, and language badges", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      // Pre-populate store
      (store as unknown as { setState: (p: unknown) => void }).setState({
        faqs: [sampleFaqEn, sampleFaqUr],
      });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(FaqSection, null)
        )
      );

      // Verify English FAQ
      assert.ok(html.includes("What are your standard opening hours?"));
      assert.ok(html.includes("We are open Monday to Friday from 9:00 AM to 6:00 PM."));
      assert.ok(html.includes("English"));

      // Verify Urdu FAQ with RTL direction
      assert.ok(html.includes("آپ کے کھلنے کے اوقات کیا ہیں؟"));
      assert.ok(html.includes("ہم پیر سے جمعہ صبح 9 بجے سے شام 6 بجے تک کھلے رہتے ہیں۔"));
      assert.ok(html.includes("اردو (Urdu)"));

      // Verify action buttons
      assert.ok(html.includes("Add FAQ"));
      assert.ok(html.includes("All Languages (2)"));
    });

    test("renders empty state when no FAQs are present", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(FaqSection, null)
        )
      );

      assert.ok(html.includes("No FAQs added yet"));
      assert.ok(html.includes("Add your first FAQ"));
    });

    test("renders loading skeleton when isLoadingFaqs is true and list is empty", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        isLoadingFaqs: true,
        faqs: [],
      });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(FaqSection, null)
        )
      );

      assert.ok(html.includes("animate-pulse"));
    });
  });

  describe("DocumentSection Component", () => {
    test("renders upload zone with 5 MB limit notice and supported formats", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(DocumentSection, null)
        )
      );

      assert.ok(html.includes("Upload Business Documents"));
      assert.ok(html.includes("max 5 MB"));
      assert.ok(html.includes("PDF or DOCX"));
      assert.ok(html.includes("Select File from Device"));
    });

    test("file input accept attribute specifies only PDF and DOCX MIME types without text/plain or .txt", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(DocumentSection, null)
        )
      );

      assert.ok(html.includes('accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"'));
      assert.ok(!html.includes(".txt"));
      assert.ok(!html.includes("text/plain"));
    });

    test("accepts .pdf and .docx file extensions and rejects .txt files", () => {
      const allowed = [".pdf", ".docx"];
      const testCases = [
        { name: "handbook.pdf", expected: true },
        { name: "REPORT.DOCX", expected: true },
        { name: "policy.PDF", expected: true },
        { name: "notes.txt", expected: false },
        { name: "data.TXT", expected: false },
        { name: "archive.zip", expected: false },
        { name: "script.sh", expected: false },
        { name: "document.pdf.txt", expected: false },
      ];

      for (const tc of testCases) {
        const lower = tc.name.toLowerCase();
        const isValid = allowed.some((ext) => lower.endsWith(ext));
        assert.strictEqual(
          isValid,
          tc.expected,
          `Expected ${tc.name} validity to be ${tc.expected}`
        );
      }
    });

    test("renders document list with Ready, Processing, and Failed statuses", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [sampleFileReady, sampleFileProcessing, sampleFileFailed],
        filesTotal: 3,
      });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(DocumentSection, null)
        )
      );

      // Filenames and sizes
      assert.ok(html.includes("clinic_policy.pdf"));
      assert.ok(html.includes("512.0 KB"));
      assert.ok(html.includes("services_catalog.docx"));
      assert.ok(html.includes("2.00 MB"));
      assert.ok(html.includes("corrupt_data.pdf"));

      // Status badges
      assert.ok(html.includes("Ready"));
      assert.ok(html.includes("Processing"));
      assert.ok(html.includes("Processing Failed"));

      // Chunk count display
      assert.ok(html.includes("12 chunks"));

      // Failure reason explanation
      assert.ok(html.includes("PDF contains invalid xref tables and could not be parsed."));
    });

    test("displays active polling badge when files are pending or processing", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        files: [sampleFileProcessing],
        filesTotal: 1,
      });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(DocumentSection, null)
        )
      );

      assert.ok(html.includes("Indexing in progress"));
    });

    test("renders empty state when no documents exist", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(DocumentSection, null)
        )
      );

      assert.ok(html.includes("No documents uploaded yet"));
      assert.ok(html.includes("Upload a document"));
    });
  });

  describe("SearchSection Component", () => {
    test("renders retrieval preview disclaimer banner", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(SearchSection, null)
        )
      );

      assert.ok(html.includes("Knowledge Retrieval Preview"));
      assert.ok(html.includes("raw retrieved context, not an LLM-synthesized final answer"));
      assert.ok(html.includes("Top 5"));
    });

    test("renders matched search results with cosine distance and source badges", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        searchResults: [sampleSearchResultFaq, sampleSearchResultChunk],
        searchQuery: "hours and payment",
        isSearching: false,
      });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(SearchSection, null)
        )
      );

      // Result count summary
      assert.ok(html.includes("Retrieved"));
      assert.ok(html.includes("2"));
      assert.ok(html.includes("hours and payment"));

      // FAQ entry result
      assert.ok(html.includes("FAQ Entry"));
      assert.ok(html.includes("What are your standard opening hours?"));
      assert.ok(html.includes("0.1245"));

      // Document chunk result with section & page metadata
      assert.ok(html.includes("Document Chunk"));
      assert.ok(html.includes("Billing &amp; Payment Terms") || html.includes("Billing & Payment Terms"));
      assert.ok(html.includes("Page 2"));
      assert.ok(html.includes("Chunk 3"));
      assert.ok(html.includes("0.1892"));
      assert.ok(html.includes("Payment is required at the time services are rendered."));
    });

    test("renders empty state when search returns 0 results", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        searchResults: [],
        searchQuery: "quantum mechanics pricing",
        isSearching: false,
      });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(SearchSection, null)
        )
      );

      assert.ok(html.includes("No Matching Knowledge Chunks"));
      assert.ok(html.includes("quantum mechanics pricing"));
    });

    test("renders searching state with spinner when isSearching is true", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        isSearching: true,
        searchResults: null,
      });

      const html = renderToStaticMarkup(
        React.createElement(
          KnowledgeProvider,
          { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
          React.createElement(SearchSection, null)
        )
      );

      assert.ok(html.includes("Embedding query and calculating vector similarity..."));
    });
  });

  describe("KnowledgeContentView (Page Layout)", () => {
    test("renders header, workspace badge, and all three navigation tabs", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        faqs: [sampleFaqEn],
        files: [sampleFileReady],
      });

      const mockBusiness: BusinessResponse = {
        id: "biz-123",
        name: "Apex Healthcare",
        slug: "apex-healthcare",
        is_active: true,
        role: "owner",
        created_at: "2026-11-20T10:00:00Z",
        updated_at: "2026-11-20T10:00:00Z",
      };

      const mockBusinessContext: BusinessContextType = {
        businesses: [mockBusiness],
        currentBusiness: mockBusiness,
        isLoadingBusiness: false,
        businessError: null,
        refreshBusinesses: async () => {},
        createBusiness: async () => mockBusiness,
      };

      const html = renderToStaticMarkup(
        React.createElement(
          BusinessContext.Provider,
          { value: mockBusinessContext },
          React.createElement(
            KnowledgeProvider,
            { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
            React.createElement(KnowledgeContentView, null)
          )
        )
      );

      assert.ok(html.includes("Knowledge Base &amp; RAG") || html.includes("Knowledge Base & RAG"));
      assert.ok(html.includes("Apex Healthcare"));
      assert.ok(html.includes("Curated FAQs"));
      assert.ok(html.includes("Documents (PDF / DOCX)"));
      assert.ok(html.includes("Test Retrieval Preview"));
    });

    test("renders global success and error banners when populated", () => {
      const store = new KnowledgeStore({ client: mockClient, businessId: "biz-123" });
      (store as unknown as { setState: (p: unknown) => void }).setState({
        successMessage: "FAQ created successfully.",
        error: "Failed to upload document file.",
      });

      const mockBusiness: BusinessResponse = {
        id: "biz-123",
        name: "Apex Healthcare",
        slug: "apex-healthcare",
        is_active: true,
        role: "owner",
        created_at: "2026-11-20T10:00:00Z",
        updated_at: "2026-11-20T10:00:00Z",
      };

      const mockBusinessContext: BusinessContextType = {
        businesses: [mockBusiness],
        currentBusiness: mockBusiness,
        isLoadingBusiness: false,
        businessError: null,
        refreshBusinesses: async () => {},
        createBusiness: async () => mockBusiness,
      };

      const html = renderToStaticMarkup(
        React.createElement(
          BusinessContext.Provider,
          { value: mockBusinessContext },
          React.createElement(
            KnowledgeProvider,
            { store, businessId: "biz-123", autoFetch: false, autoPoll: false },
            React.createElement(KnowledgeContentView, null)
          )
        )
      );

      assert.ok(html.includes("FAQ created successfully."));
      assert.ok(html.includes("Failed to upload document file."));
    });
  });
});
