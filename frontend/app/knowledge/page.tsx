"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import {
  KnowledgeIcon,
  FileTextIcon,
  SearchIcon,
  CheckCircleIcon,
  AlertCircleIcon,
  CloseIcon,
  SparklesIcon,
} from "@/components/ui/icons";
import { useAuth } from "@/lib/auth/AuthContext";
import { useBusiness } from "@/lib/business/BusinessContext";
import {
  KnowledgeProvider,
  useKnowledgeContext,
} from "@/lib/knowledge/knowledge-context";
import { FaqSection } from "@/components/knowledge/FaqSection";
import { DocumentSection } from "@/components/knowledge/DocumentSection";
import { SearchSection } from "@/components/knowledge/SearchSection";

type KnowledgeTab = "faqs" | "documents" | "search";

export function KnowledgeContentView() {
  const { currentBusiness, isLoadingBusiness } = useBusiness();
  const {
    faqs,
    files,
    isPolling,
    error,
    successMessage,
    clearError,
    clearSuccessMessage,
  } = useKnowledgeContext();

  const [activeTab, setActiveTab] = useState<KnowledgeTab>("faqs");

  return (
    <div className="space-y-6">
      {/* Top Header & Workspace Info */}
      <section className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-border-main">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-cherry text-white flex items-center justify-center font-bold shadow-xs">
              <KnowledgeIcon className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-main-text">
                Knowledge Base &amp; RAG
              </h2>
              <p className="text-xs text-secondary-text mt-0.5">
                Curate business FAQs, upload documents for AI indexing, and test vector retrieval.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <Badge variant="cherry" className="text-xs py-1 px-3">
            {currentBusiness ? currentBusiness.name : "Workspace"}
          </Badge>
          {isPolling && (
            <Badge variant="indigo" className="text-xs py-1 px-2.5 gap-1.5 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-cherry" />
              <span>Indexing Active</span>
            </Badge>
          )}
        </div>
      </section>

      {/* Global Success Banner */}
      {successMessage && (
        <div
          role="status"
          className="p-3.5 rounded-xl bg-status-success/10 border border-status-success/20 flex items-center justify-between text-xs text-status-success"
        >
          <div className="flex items-center gap-2">
            <CheckCircleIcon className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button
            type="button"
            onClick={clearSuccessMessage}
            className="p-1 rounded hover:bg-status-success/10 transition"
            aria-label="Dismiss success message"
          >
            <CloseIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Global Error Banner */}
      {error && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-status-error/10 border border-status-error/20 flex items-center justify-between text-xs text-status-error"
        >
          <div className="flex items-center gap-2">
            <AlertCircleIcon className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={clearError}
            className="p-1 rounded hover:bg-status-error/10 transition"
            aria-label="Dismiss error message"
          >
            <CloseIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Workspace Warning Banner if no business is selected */}
      {!currentBusiness && !isLoadingBusiness && (
        <div className="p-4 rounded-xl bg-warm-ivory border border-border-main flex items-center gap-3 text-xs text-secondary-text">
          <SparklesIcon className="w-5 h-5 text-cherry shrink-0" />
          <p>
            Please set up or select an active business workspace to view and manage your knowledge base.
          </p>
        </div>
      )}

      {/* Section Tabs */}
      <div className="flex border-b border-border-main gap-2 sm:gap-6 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab("faqs")}
          className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition whitespace-nowrap ${
            activeTab === "faqs"
              ? "border-cherry text-cherry"
              : "border-transparent text-secondary-text hover:text-main-text"
          }`}
        >
          <KnowledgeIcon className="w-4 h-4" />
          <span>Curated FAQs</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-warm-ivory text-secondary-text border border-border-soft">
            {faqs.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("documents")}
          className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition whitespace-nowrap ${
            activeTab === "documents"
              ? "border-cherry text-cherry"
              : "border-transparent text-secondary-text hover:text-main-text"
          }`}
        >
          <FileTextIcon className="w-4 h-4" />
          <span>Documents (PDF / DOCX)</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-warm-ivory text-secondary-text border border-border-soft">
            {files.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("search")}
          className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition whitespace-nowrap ${
            activeTab === "search"
              ? "border-cherry text-cherry"
              : "border-transparent text-secondary-text hover:text-main-text"
          }`}
        >
          <SearchIcon className="w-4 h-4" />
          <span>Test Retrieval Preview</span>
        </button>
      </div>

      {/* Tab Panes */}
      <div className="pt-2">
        {activeTab === "faqs" && <FaqSection />}
        {activeTab === "documents" && <DocumentSection />}
        {activeTab === "search" && <SearchSection />}
      </div>
    </div>
  );
}

export default function KnowledgePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-warm-ivory">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-cherry border-t-transparent animate-spin" />
          <p className="text-xs text-secondary-text font-medium">Verifying session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <AppShell activeItem="knowledge">
      <KnowledgeProvider>
        <KnowledgeContentView />
      </KnowledgeProvider>
    </AppShell>
  );
}
