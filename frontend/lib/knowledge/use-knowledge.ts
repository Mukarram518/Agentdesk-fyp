"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import type {
  FAQCreatePayload,
  FAQUpdatePayload,
  FAQResponse,
  ListFaqsParams,
  KnowledgeSearchResultItem,
  KnowledgeFileResponse,
  ListFilesParams,
} from "@/types/knowledge";
import { KnowledgeStore, type KnowledgeState } from "./knowledge-store";
import { BusinessContext } from "@/lib/business/BusinessContext";
import type { ApiClient } from "@/lib/api/client";

export interface UseKnowledgeOptions {
  /**
   * Explicit business ID to manage.
   * If omitted, defaults dynamically to the active `currentBusiness` from `BusinessContext`.
   */
  businessId?: string | null;
  /**
   * Optional custom ApiClient instance (e.g. for testing or isolated sessions).
   */
  client?: ApiClient;
  /**
   * Whether to automatically fetch FAQs and documents on mount or when the business changes.
   * Defaults to true.
   */
  autoFetch?: boolean;
  /**
   * Whether to automatically poll file statuses while any document is pending or processing.
   * Defaults to true.
   */
  autoPoll?: boolean;
  /**
   * Interval in milliseconds for polling pending/processing files.
   * Defaults to 3000ms.
   */
  pollIntervalMs?: number;
  /**
   * Optional custom KnowledgeStore instance (useful for unit testing and state sharing).
   */
  store?: KnowledgeStore;
}

export interface UseKnowledgeReturn {
  // State slices
  faqs: FAQResponse[];
  files: KnowledgeFileResponse[];
  filesTotal: number;
  searchResults: KnowledgeSearchResultItem[] | null;
  searchQuery: string | null;
  isLoading: boolean;
  isLoadingFaqs: boolean;
  isLoadingFiles: boolean;
  isSearching: boolean;
  isMutating: boolean;
  isUploading: boolean;
  error: string | null;
  successMessage: string | null;
  isPolling: boolean;

  // Actions
  fetchFaqs: (params?: ListFaqsParams) => Promise<FAQResponse[] | null>;
  fetchFiles: (params?: ListFilesParams) => Promise<KnowledgeFileResponse[] | null>;
  fetchAll: (faqParams?: ListFaqsParams, fileParams?: ListFilesParams) => Promise<void>;
  createFaq: (payload: FAQCreatePayload) => Promise<FAQResponse>;
  updateFaq: (knowledgeId: string, payload: FAQUpdatePayload) => Promise<FAQResponse>;
  deleteFaq: (knowledgeId: string) => Promise<void>;
  search: (query: string, top_k?: number, score_threshold?: number | null) => Promise<KnowledgeSearchResultItem[]>;
  clearSearch: () => void;
  uploadFile: (file: File | Blob, filename?: string) => Promise<KnowledgeFileResponse>;
  deleteFile: (fileId: string) => Promise<void>;
  refreshFileStatus: (fileId: string) => Promise<KnowledgeFileResponse | null>;
  clearError: () => void;
  clearSuccessMessage: () => void;
  reset: () => void;
  store: KnowledgeStore;
}

export const KnowledgeContext = createContext<UseKnowledgeReturn | null>(null);

/**
 * Reusable React hook for business Knowledge Base state management.
 * Provides typed access to FAQs, uploaded documents, semantic search,
 * automatic background polling of pending files, and tenant-safe business switching.
 */
export function useKnowledge(options: UseKnowledgeOptions = {}): UseKnowledgeReturn {
  const {
    businessId: explicitBusinessId,
    client,
    autoFetch = true,
    autoPoll = true,
    pollIntervalMs = 3000,
    store: injectedStore,
  } = options;

  const businessContext = useContext(BusinessContext);
  const resolvedBusinessId =
    explicitBusinessId !== undefined
      ? explicitBusinessId
      : (businessContext?.currentBusiness?.id ?? null);

  const store = useMemo(() => {
    return (
      injectedStore ??
      new KnowledgeStore({
        businessId: resolvedBusinessId,
        client,
      })
    );
  }, [injectedStore, resolvedBusinessId, client]);

  // Synchronize store business ID whenever the resolved business ID changes
  useEffect(() => {
    if (store.getBusinessId() !== resolvedBusinessId) {
      store.setBusinessId(resolvedBusinessId, autoFetch);
    } else if (
      autoFetch &&
      resolvedBusinessId &&
      store.getSnapshot().faqs.length === 0 &&
      store.getSnapshot().files.length === 0 &&
      !store.getSnapshot().isLoadingFaqs &&
      !store.getSnapshot().isLoadingFiles &&
      !store.getSnapshot().error
    ) {
      void store.fetchAll().catch(() => {});
    }
  }, [store, resolvedBusinessId, autoFetch]);

  const state: KnowledgeState = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot
  );

  // Background polling for documents with pending or processing status
  const isPollingRef = useRef<boolean>(false);
  const prevPendingCountRef = useRef<number>(0);

  const effectiveFiles = state.files.length > 0 ? state.files : store.getSnapshot().files;
  const effectiveFaqs = state.faqs.length > 0 ? state.faqs : store.getSnapshot().faqs;
  const snapshot = store.getSnapshot();
  const effectiveIsLoadingFaqs = state.isLoadingFaqs || snapshot.isLoadingFaqs;
  const effectiveIsLoadingFiles = state.isLoadingFiles || snapshot.isLoadingFiles;
  const effectiveIsSearching = state.isSearching || snapshot.isSearching;
  const effectiveIsMutating = state.isMutating || snapshot.isMutating;
  const effectiveIsUploading = state.isUploading || snapshot.isUploading;
  const effectiveError = state.error || snapshot.error;
  const effectiveSuccessMessage = state.successMessage || snapshot.successMessage;

  const hasPendingOrProcessing = useMemo(() => {
    return effectiveFiles.some(
      (f) => f.processing_status === "pending" || f.processing_status === "processing"
    );
  }, [effectiveFiles]);

  useEffect(() => {
    if (!autoPoll || !resolvedBusinessId || !hasPendingOrProcessing) {
      return;
    }

    let isMounted = true;
    const intervalId = setInterval(async () => {
      // Prevent overlapping polling requests
      if (isPollingRef.current || !isMounted) {
        return;
      }

      isPollingRef.current = true;
      try {
        const updatedFiles = await store.pollFiles();
        if (!isMounted || !updatedFiles) {
          return;
        }

        // If files transitioned to ready, refresh FAQs so new document chunks appear
        const currentPendingCount = updatedFiles.filter(
          (f) => f.processing_status === "pending" || f.processing_status === "processing"
        ).length;

        if (prevPendingCountRef.current > 0 && currentPendingCount < prevPendingCountRef.current) {
          void store.fetchFaqs().catch(() => {});
        }
        prevPendingCountRef.current = currentPendingCount;
      } finally {
        isPollingRef.current = false;
      }
    }, pollIntervalMs);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
      isPollingRef.current = false;
    };
  }, [store, resolvedBusinessId, autoPoll, hasPendingOrProcessing, pollIntervalMs]);

  return {
    faqs: effectiveFaqs,
    files: effectiveFiles,
    filesTotal: state.filesTotal || snapshot.filesTotal,
    searchResults: state.searchResults ?? snapshot.searchResults,
    searchQuery: state.searchQuery ?? snapshot.searchQuery,
    isLoading: effectiveIsLoadingFaqs || effectiveIsLoadingFiles,
    isLoadingFaqs: effectiveIsLoadingFaqs,
    isLoadingFiles: effectiveIsLoadingFiles,
    isSearching: effectiveIsSearching,
    isMutating: effectiveIsMutating,
    isUploading: effectiveIsUploading,
    error: effectiveError,
    successMessage: effectiveSuccessMessage,
    isPolling: hasPendingOrProcessing,

    fetchFaqs: store.fetchFaqs.bind(store),
    fetchFiles: store.fetchFiles.bind(store),
    fetchAll: store.fetchAll.bind(store),
    createFaq: store.createFaq.bind(store),
    updateFaq: store.updateFaq.bind(store),
    deleteFaq: store.deleteFaq.bind(store),
    search: store.search.bind(store),
    clearSearch: store.clearSearch.bind(store),
    uploadFile: store.uploadFile.bind(store),
    deleteFile: store.deleteFile.bind(store),
    refreshFileStatus: store.refreshFileStatus.bind(store),
    clearError: store.clearError.bind(store),
    clearSuccessMessage: store.clearSuccessMessage.bind(store),
    reset: store.reset.bind(store),
    store,
  };
}
