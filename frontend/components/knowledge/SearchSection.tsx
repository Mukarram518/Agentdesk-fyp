"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  SearchIcon,
  CloseIcon,
  KnowledgeIcon,
  FileTextIcon,
  AlertCircleIcon,
  SparklesIcon,
} from "@/components/ui/icons";
import { useKnowledgeContext } from "@/lib/knowledge/knowledge-context";
import { detectTextDirection } from "@/lib/chat/text-direction";

export function SearchSection() {
  const {
    searchResults,
    searchQuery: activeQuery,
    isSearching,
    error,
    search,
    clearSearch,
    clearError,
  } = useKnowledgeContext();

  const [inputQuery, setInputQuery] = useState(activeQuery || "");
  const [topK, setTopK] = useState<number>(5);

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    const trimmed = inputQuery.trim();
    if (!trimmed) {
      clearSearch();
      return;
    }
    try {
      await search(trimmed, topK);
    } catch {
      // Store state handles error
    }
  };

  const handleClear = () => {
    setInputQuery("");
    clearSearch();
    clearError();
  };

  const queryDir = detectTextDirection(inputQuery);

  return (
    <div className="space-y-6">
      {/* Notice / Educational Callout */}
      <div className="p-4 rounded-xl bg-warm-ivory border border-border-main flex items-start gap-3 text-xs text-secondary-text">
        <SparklesIcon className="w-4 h-4 text-cherry shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-main-text">Knowledge Retrieval Preview</p>
          <p className="leading-relaxed">
            This tool performs a semantic similarity search across your vector database using AI embeddings.
            Results represent the exact context chunks retrieved by the orchestrator for customer inquiries in
            English, Urdu (اردو), or Roman Urdu. This preview displays raw retrieved context, not an LLM-synthesized final answer.
          </p>
        </div>
      </div>

      {/* Search Input Bar */}
      <form onSubmit={handleSearchSubmit} className="space-y-3">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary-text pointer-events-none" />
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask a question in English, Urdu (e.g. آپ کی فیس کتنی ہے؟), or Roman Urdu..."
              dir={queryDir}
              className="w-full pl-10 pr-10 py-2.5 text-xs rounded-xl border border-border-main focus:outline-none focus:ring-2 focus:ring-cherry/30 bg-white shadow-2xs text-main-text"
            />
            {inputQuery && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-secondary-text hover:text-main-text rounded-md"
                aria-label="Clear search input"
              >
                <CloseIcon className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="px-2.5 py-2.5 text-xs rounded-xl border border-border-main bg-white text-secondary-text focus:outline-none focus:ring-2 focus:ring-cherry/30 shadow-2xs"
              aria-label="Number of results"
            >
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
            </select>

            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={isSearching || !inputQuery.trim()}
              className="text-xs px-4 py-2.5 h-auto gap-1.5"
            >
              {isSearching ? (
                <div className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
              ) : (
                <SearchIcon className="w-3.5 h-3.5" />
              )}
              <span>{isSearching ? "Searching..." : "Search"}</span>
            </Button>
          </div>
        </div>
      </form>

      {/* Error Banner */}
      {error && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-status-error/10 border border-status-error/20 flex items-start gap-3 text-xs text-status-error"
        >
          <AlertCircleIcon className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Retrieval Error: </span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={clearError}
            className="text-xs underline hover:no-underline font-medium"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Search State & Results Display */}
      {isSearching ? (
        <div className="p-8 rounded-xl border border-border-main bg-white flex flex-col items-center justify-center text-center space-y-3">
          <div className="w-8 h-8 rounded-full border-2 border-cherry border-t-transparent animate-spin" />
          <p className="text-xs font-medium text-main-text">
            Embedding query and calculating vector similarity...
          </p>
          <p className="text-[11px] text-secondary-text">
            Executing cosine distance search across business knowledge partitions
          </p>
        </div>
      ) : searchResults === null ? (
        <EmptyState
          icon={<SearchIcon className="w-6 h-6 text-cherry" />}
          title="Test Semantic Vector Retrieval"
          description="Type a question above in English, Urdu, or Roman Urdu to inspect how the orchestrator retrieves matching FAQs and document chunks."
        />
      ) : searchResults.length === 0 ? (
        <EmptyState
          icon={<SearchIcon className="w-6 h-6 text-secondary-text" />}
          title="No Matching Knowledge Chunks"
          description={`No entries matched "${activeQuery || inputQuery}". Consider adding a new FAQ or uploading related business documents.`}
        />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-secondary-text px-1">
            <span>
              Retrieved <strong className="text-main-text font-semibold">{searchResults.length}</strong> matched context chunks for &quot;{activeQuery}&quot;
            </span>
            <button
              type="button"
              onClick={handleClear}
              className="text-xs text-cherry hover:underline font-medium"
            >
              Clear Results
            </button>
          </div>

          <div className="space-y-3">
            {searchResults.map((item, index) => {
              const isFaq = item.entry.source_type?.toLowerCase() === "faq" || !item.entry.source_file_id;
              const isUrdu = item.entry.language === "ur";
              const textContent = item.entry.answer;
              const textDir = detectTextDirection(textContent);

              return (
                <Card
                  key={`${item.entry.id}-${index}`}
                  className="p-4 sm:p-5 hover:border-cherry/40 transition duration-150 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-border-soft">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-bold text-cherry bg-cherry-soft px-2 py-0.5 rounded border border-border-soft">
                        #{index + 1}
                      </span>

                      {/* Source Type */}
                      <Badge
                        variant={isFaq ? "cherry" : "indigo"}
                        className="text-[10px] font-semibold gap-1"
                      >
                        {isFaq ? (
                          <KnowledgeIcon className="w-3 h-3 text-cherry" />
                        ) : (
                          <FileTextIcon className="w-3 h-3 text-cherry" />
                        )}
                        <span>{isFaq ? "FAQ Entry" : "Document Chunk"}</span>
                      </Badge>

                      {/* Language Badge */}
                      <Badge variant="default" className="text-[10px]">
                        {isUrdu ? "اردو (Urdu)" : item.entry.language === "en" ? "English" : item.entry.language}
                      </Badge>

                      {/* Chunk / Section Metadata */}
                      {item.section_title && (
                        <span className="text-[11px] text-secondary-text bg-warm-ivory px-2 py-0.5 rounded border border-border-soft">
                          Section: {item.section_title}
                        </span>
                      )}
                      {item.page_number !== undefined && item.page_number !== null && (
                        <span className="text-[11px] text-secondary-text bg-warm-ivory px-2 py-0.5 rounded border border-border-soft">
                          Page {item.page_number}
                        </span>
                      )}
                      {item.chunk_index !== undefined && item.chunk_index !== null && (
                        <span className="text-[11px] text-secondary-text bg-warm-ivory px-2 py-0.5 rounded border border-border-soft">
                          Chunk {item.chunk_index}
                        </span>
                      )}
                    </div>

                    {/* Exact Similarity Score */}
                    <div className="flex items-center gap-1.5 text-xs text-secondary-text font-mono">
                      <span>Distance:</span>
                      <Badge
                        variant={item.score < 0.25 ? "success" : item.score < 0.4 ? "warning" : "default"}
                        className="text-[10px] font-semibold"
                      >
                        {item.score.toFixed(4)}
                      </Badge>
                    </div>
                  </div>

                  {/* Question (if FAQ) */}
                  {item.entry.question && (
                    <div>
                      <h4
                        className="text-xs font-semibold text-main-text"
                        dir={detectTextDirection(item.entry.question)}
                      >
                        Q: {item.entry.question}
                      </h4>
                    </div>
                  )}

                  {/* Retrieved Text Body */}
                  <div className="p-3 rounded-lg bg-warm-ivory/50 border border-border-soft">
                    <p
                      className="text-xs text-main-text leading-relaxed whitespace-pre-wrap"
                      dir={textDir}
                    >
                      {textContent}
                    </p>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
