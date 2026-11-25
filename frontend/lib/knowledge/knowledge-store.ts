/**
 * AgentDesk Knowledge State Store.
 * Centralized, observable state store for FAQ management, document files, and semantic search.
 *
 * Guarantees:
 * 1. Business-tenant scoped state lifecycle (resets on business switch or logout).
 * 2. Stale-response protection across asynchronous network calls.
 * 3. Atomic transition handling for loading, mutating, and error states.
 * 4. SSR-safe snapshot caching for useSyncExternalStore.
 * 5. Automatic document chunk and file status synchronization.
 */

import type {
  FAQCreatePayload,
  FAQUpdatePayload,
  FAQResponse,
  ListFaqsParams,
  KnowledgeSearchRequest,
  KnowledgeSearchResultItem,
  KnowledgeFileResponse,
  ListFilesParams,
} from "@/types/knowledge";
import { apiClient, ApiHttpError, isApiClientError, type ApiClient } from "@/lib/api/client";

export interface KnowledgeState {
  faqs: FAQResponse[];
  files: KnowledgeFileResponse[];
  filesTotal: number;
  searchResults: KnowledgeSearchResultItem[] | null;
  searchQuery: string | null;
  isLoadingFaqs: boolean;
  isLoadingFiles: boolean;
  isSearching: boolean;
  isMutating: boolean;
  isUploading: boolean;
  error: string | null;
  successMessage: string | null;
}

export const INITIAL_KNOWLEDGE_STATE: KnowledgeState = Object.freeze({
  faqs: [],
  files: [],
  filesTotal: 0,
  searchResults: null,
  searchQuery: null,
  isLoadingFaqs: false,
  isLoadingFiles: false,
  isSearching: false,
  isMutating: false,
  isUploading: false,
  error: null,
  successMessage: null,
});

/**
 * Extracts a human-readable error message from an API error or exception.
 */
export function extractApiErrorMessage(
  error: unknown,
  fallback = "An unexpected error occurred."
): string {
  if (error instanceof ApiHttpError) {
    if (error.data && typeof error.data === "object") {
      const payload = error.data as Record<string, unknown>;
      if (typeof payload.detail === "string") {
        return payload.detail;
      }
      if (Array.isArray(payload.detail) && payload.detail.length > 0) {
        const first = payload.detail[0];
        if (first && typeof first === "object" && "msg" in first) {
          return String(first.msg);
        }
      }
      if (typeof payload.message === "string") {
        return payload.message;
      }
    }
    return error.message || fallback;
  }
  if (isApiClientError(error) || error instanceof Error) {
    return error.message;
  }
  return fallback;
}

export interface KnowledgeStoreOptions {
  client?: ApiClient;
  businessId?: string | null;
}

export class KnowledgeStore {
  private state: KnowledgeState;
  private listeners = new Set<() => void>();
  private activeFaqsRequestId = 0;
  private activeFilesRequestId = 0;
  private activeSearchRequestId = 0;
  private currentBusinessId: string | null = null;
  private client: ApiClient;

  constructor(options: KnowledgeStoreOptions = {}) {
    this.client = options.client || apiClient;
    this.state = INITIAL_KNOWLEDGE_STATE;
    this.currentBusinessId = options.businessId ?? null;
  }

  getSnapshot = (): KnowledgeState => {
    return this.state;
  };

  getServerSnapshot = (): KnowledgeState => {
    return INITIAL_KNOWLEDGE_STATE;
  };

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private setState(partial: Partial<KnowledgeState>): void {
    this.state = { ...this.state, ...partial };
    for (const listener of this.listeners) {
      listener();
    }
  }

  getBusinessId(): string | null {
    return this.currentBusinessId;
  }

  /**
   * Sets the active business ID.
   * If the business ID changes, wipes state immediately to avoid cross-tenant leakage.
   */
  setBusinessId(newBusinessId: string | null, autoFetch = true): void {
    if (this.currentBusinessId === newBusinessId) {
      return;
    }

    this.activeFaqsRequestId++;
    this.activeFilesRequestId++;
    this.activeSearchRequestId++;
    this.currentBusinessId = newBusinessId;

    // Immediately reset to initial state to ensure zero stale cross-tenant leakage
    this.setState({
      ...INITIAL_KNOWLEDGE_STATE,
    });

    if (autoFetch && newBusinessId) {
      void this.fetchAll().catch(() => {});
    }
  }

  /**
   * Fetches FAQs for the active business.
   */
  async fetchFaqs(params?: ListFaqsParams): Promise<FAQResponse[] | null> {
    if (!this.currentBusinessId) {
      this.setState({ faqs: [], isLoadingFaqs: false });
      return null;
    }

    const requestId = ++this.activeFaqsRequestId;
    this.setState({ isLoadingFaqs: true, error: null });

    try {
      const faqs = await this.client.listFaqs(params);
      if (requestId === this.activeFaqsRequestId) {
        this.setState({ faqs, isLoadingFaqs: false });
      }
      return faqs;
    } catch (err: unknown) {
      if (requestId === this.activeFaqsRequestId) {
        const errorMsg = extractApiErrorMessage(err, "Failed to load FAQs.");
        this.setState({ isLoadingFaqs: false, error: errorMsg });
      }
      throw err;
    }
  }

  /**
   * Fetches uploaded document files for the active business.
   */
  async fetchFiles(params?: ListFilesParams): Promise<KnowledgeFileResponse[] | null> {
    if (!this.currentBusinessId) {
      this.setState({ files: [], filesTotal: 0, isLoadingFiles: false });
      return null;
    }

    const requestId = ++this.activeFilesRequestId;
    this.setState({ isLoadingFiles: true, error: null });

    try {
      const response = await this.client.listKnowledgeFiles(params);
      if (requestId === this.activeFilesRequestId) {
        this.setState({
          files: response.items,
          filesTotal: response.total,
          isLoadingFiles: false,
        });
      }
      return response.items;
    } catch (err: unknown) {
      if (requestId === this.activeFilesRequestId) {
        const errorMsg = extractApiErrorMessage(err, "Failed to load documents.");
        this.setState({ isLoadingFiles: false, error: errorMsg });
      }
      throw err;
    }
  }

  /**
   * Fetches both FAQs and document files in parallel for the active business.
   */
  async fetchAll(
    faqParams?: ListFaqsParams,
    fileParams?: ListFilesParams
  ): Promise<void> {
    if (!this.currentBusinessId) {
      return;
    }

    await Promise.allSettled([
      this.fetchFaqs(faqParams),
      this.fetchFiles(fileParams),
    ]);
  }

  /**
   * Background poll for file statuses without triggering the full page loading spinner.
   */
  async pollFiles(params?: ListFilesParams): Promise<KnowledgeFileResponse[] | null> {
    if (!this.currentBusinessId) {
      return null;
    }

    const requestId = this.activeFilesRequestId;
    try {
      const response = await this.client.listKnowledgeFiles(params);
      if (requestId === this.activeFilesRequestId) {
        this.setState({
          files: response.items,
          filesTotal: response.total,
        });
      }
      return response.items;
    } catch {
      // Background poll silently avoids clobbering visible state on transient network blips
      return null;
    }
  }

  /**
   * Creates a new FAQ entry and prepends it to the list.
   */
  async createFaq(payload: FAQCreatePayload): Promise<FAQResponse> {
    if (!this.currentBusinessId) {
      throw new Error("No active business selected.");
    }

    this.setState({ isMutating: true, error: null });
    try {
      const created = await this.client.createFaq(payload);
      this.setState({
        faqs: [created, ...this.state.faqs],
        isMutating: false,
        successMessage: "FAQ created successfully.",
      });
      return created;
    } catch (err: unknown) {
      const errorMsg = extractApiErrorMessage(err, "Failed to create FAQ.");
      this.setState({ isMutating: false, error: errorMsg });
      throw err;
    }
  }

  /**
   * Updates an existing FAQ entry.
   */
  async updateFaq(
    knowledgeId: string,
    payload: FAQUpdatePayload
  ): Promise<FAQResponse> {
    if (!this.currentBusinessId) {
      throw new Error("No active business selected.");
    }

    this.setState({ isMutating: true, error: null });
    try {
      const updated = await this.client.updateFaq(knowledgeId, payload);
      this.setState({
        faqs: this.state.faqs.map((faq) => (faq.id === knowledgeId ? updated : faq)),
        isMutating: false,
        successMessage: "FAQ updated successfully.",
      });
      return updated;
    } catch (err: unknown) {
      const errorMsg = extractApiErrorMessage(err, "Failed to update FAQ.");
      this.setState({ isMutating: false, error: errorMsg });
      throw err;
    }
  }

  /**
   * Deletes an existing FAQ entry.
   */
  async deleteFaq(knowledgeId: string): Promise<void> {
    if (!this.currentBusinessId) {
      throw new Error("No active business selected.");
    }

    this.setState({ isMutating: true, error: null });
    try {
      await this.client.deleteFaq(knowledgeId);
      this.setState({
        faqs: this.state.faqs.filter((faq) => faq.id !== knowledgeId),
        isMutating: false,
        successMessage: "FAQ deleted successfully.",
      });
    } catch (err: unknown) {
      const errorMsg = extractApiErrorMessage(err, "Failed to delete FAQ.");
      this.setState({ isMutating: false, error: errorMsg });
      throw err;
    }
  }

  /**
   * Executes a semantic search query across the active business's knowledge base.
   */
  async search(
    query: string,
    top_k = 5,
    score_threshold?: number | null
  ): Promise<KnowledgeSearchResultItem[]> {
    if (!this.currentBusinessId) {
      throw new Error("No active business selected.");
    }

    const trimmed = query.trim();
    if (!trimmed) {
      this.clearSearch();
      return [];
    }

    const requestId = ++this.activeSearchRequestId;
    this.setState({ isSearching: true, searchQuery: trimmed, error: null });

    try {
      const payload: KnowledgeSearchRequest = {
        query: trimmed,
        top_k,
        score_threshold,
      };
      const response = await this.client.searchKnowledge(payload);
      if (requestId === this.activeSearchRequestId) {
        this.setState({
          searchResults: response.results,
          isSearching: false,
        });
      }
      return response.results;
    } catch (err: unknown) {
      if (requestId === this.activeSearchRequestId) {
        const errorMsg = extractApiErrorMessage(err, "Search failed.");
        this.setState({ isSearching: false, error: errorMsg });
      }
      throw err;
    }
  }

  /**
   * Clears the active search query and results.
   */
  clearSearch(): void {
    this.setState({
      searchResults: null,
      searchQuery: null,
      isSearching: false,
    });
  }

  /**
   * Uploads a document file and prepends it to the list in pending status.
   */
  async uploadFile(file: File | Blob, filename?: string): Promise<KnowledgeFileResponse> {
    if (!this.currentBusinessId) {
      throw new Error("No active business selected.");
    }

    this.setState({ isUploading: true, error: null });
    try {
      const uploaded = await this.client.uploadKnowledgeFile(file, filename);
      this.setState({
        files: [uploaded, ...this.state.files],
        filesTotal: this.state.filesTotal + 1,
        isUploading: false,
        successMessage: `File "${uploaded.filename}" uploaded successfully. Processing started.`,
      });
      return uploaded;
    } catch (err: unknown) {
      const errorMsg = extractApiErrorMessage(err, "Failed to upload document.");
      this.setState({ isUploading: false, error: errorMsg });
      throw err;
    }
  }

  /**
   * Deletes a document file and removes associated document chunks from state.
   */
  async deleteFile(fileId: string): Promise<void> {
    if (!this.currentBusinessId) {
      throw new Error("No active business selected.");
    }

    this.setState({ isMutating: true, error: null });
    try {
      await this.client.deleteKnowledgeFile(fileId);
      this.setState({
        files: this.state.files.filter((f) => f.id !== fileId),
        filesTotal: Math.max(0, this.state.filesTotal - 1),
        // Cascade delete chunks associated with this file if present in FAQs view
        faqs: this.state.faqs.filter((faq) => faq.source_file_id !== fileId),
        isMutating: false,
        successMessage: "Document deleted successfully.",
      });
    } catch (err: unknown) {
      const errorMsg = extractApiErrorMessage(err, "Failed to delete document.");
      this.setState({ isMutating: false, error: errorMsg });
      throw err;
    }
  }

  /**
   * Refreshes the status of a single knowledge file.
   */
  async refreshFileStatus(fileId: string): Promise<KnowledgeFileResponse | null> {
    if (!this.currentBusinessId) {
      return null;
    }

    try {
      const updated = await this.client.getKnowledgeFileStatus(fileId);
      this.setState({
        files: this.state.files.map((f) => (f.id === fileId ? updated : f)),
      });
      return updated;
    } catch {
      return null;
    }
  }

  /**
   * Updates an in-memory file object in the list.
   */
  updateFileInList(updatedFile: KnowledgeFileResponse): void {
    this.setState({
      files: this.state.files.map((f) => (f.id === updatedFile.id ? updatedFile : f)),
    });
  }

  clearError(): void {
    if (this.state.error) {
      this.setState({ error: null });
    }
  }

  clearSuccessMessage(): void {
    if (this.state.successMessage) {
      this.setState({ successMessage: null });
    }
  }

  reset(): void {
    this.activeFaqsRequestId++;
    this.activeFilesRequestId++;
    this.activeSearchRequestId++;
    this.setState(INITIAL_KNOWLEDGE_STATE);
  }
}
