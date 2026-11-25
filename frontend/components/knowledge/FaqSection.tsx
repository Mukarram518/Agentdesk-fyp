"use client";

import React, { useState, useMemo } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  KnowledgeIcon,
  PlusIcon,
  EditIcon,
  TrashIcon,
  CloseIcon,
  AlertCircleIcon,
  CheckCircleIcon,
} from "@/components/ui/icons";
import { useKnowledgeContext } from "@/lib/knowledge/knowledge-context";
import { detectTextDirection } from "@/lib/chat/text-direction";
import type { FAQResponse, KnowledgeLanguage } from "@/types/knowledge";

export function FaqSection() {
  const {
    faqs,
    isLoadingFaqs,
    isMutating,
    error,
    createFaq,
    updateFaq,
    deleteFaq,
    clearError,
  } = useKnowledgeContext();

  const [languageFilter, setLanguageFilter] = useState<"all" | "en" | "ur">("all");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<FAQResponse | null>(null);
  const [deletingFaq, setDeletingFaq] = useState<FAQResponse | null>(null);

  // Form state
  const [formQuestion, setFormQuestion] = useState("");
  const [formAnswer, setFormAnswer] = useState("");
  const [formLanguage, setFormLanguage] = useState<KnowledgeLanguage>("en");
  const [formTags, setFormTags] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const filteredFaqs = useMemo(() => {
    if (languageFilter === "all") return faqs;
    return faqs.filter((faq) => faq.language === languageFilter);
  }, [faqs, languageFilter]);

  const openCreateModal = () => {
    setEditingFaq(null);
    setFormQuestion("");
    setFormAnswer("");
    setFormLanguage("en");
    setFormTags("");
    setValidationError(null);
    clearError();
    setIsModalOpen(true);
  };

  const openEditModal = (faq: FAQResponse) => {
    setEditingFaq(faq);
    setFormQuestion(faq.question || "");
    setFormAnswer(faq.answer);
    setFormLanguage(faq.language as KnowledgeLanguage);
    setFormTags(faq.tags ? faq.tags.join(", ") : "");
    setValidationError(null);
    clearError();
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingFaq(null);
    setValidationError(null);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const trimmedAnswer = formAnswer.trim();
    if (!trimmedAnswer) {
      setValidationError("Answer is required.");
      return;
    }
    if (formQuestion.length > 500) {
      setValidationError("Question cannot exceed 500 characters.");
      return;
    }
    if (trimmedAnswer.length > 2000) {
      setValidationError("Answer cannot exceed 2000 characters.");
      return;
    }

    const tagsArray = formTags
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    const payload = {
      question: formQuestion.trim() || null,
      answer: trimmedAnswer,
      language: formLanguage,
      tags: tagsArray,
    };

    try {
      if (editingFaq) {
        await updateFaq(editingFaq.id, payload);
      } else {
        await createFaq(payload);
      }
      closeModal();
    } catch {
      // Error is captured in store state
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingFaq) return;
    try {
      await deleteFaq(deletingFaq.id);
      setDeletingFaq(null);
    } catch {
      // Error is captured in store state
    }
  };

  return (
    <div className="space-y-6">
      {/* Action Bar & Language Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-1.5 p-1 bg-warm-ivory border border-border-main rounded-lg w-fit">
          <button
            type="button"
            onClick={() => setLanguageFilter("all")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
              languageFilter === "all"
                ? "bg-white text-main-text shadow-2xs font-semibold"
                : "text-secondary-text hover:text-main-text"
            }`}
          >
            All Languages ({faqs.length})
          </button>
          <button
            type="button"
            onClick={() => setLanguageFilter("en")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
              languageFilter === "en"
                ? "bg-white text-main-text shadow-2xs font-semibold"
                : "text-secondary-text hover:text-main-text"
            }`}
          >
            English ({faqs.filter((f) => f.language === "en").length})
          </button>
          <button
            type="button"
            onClick={() => setLanguageFilter("ur")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
              languageFilter === "ur"
                ? "bg-white text-main-text shadow-2xs font-semibold"
                : "text-secondary-text hover:text-main-text"
            }`}
          >
            اردو / Urdu ({faqs.filter((f) => f.language === "ur").length})
          </button>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={openCreateModal}
          className="text-xs gap-1.5 self-start sm:self-auto"
        >
          <PlusIcon className="w-3.5 h-3.5" />
          <span>Add FAQ</span>
        </Button>
      </div>

      {/* Loading Skeleton */}
      {isLoadingFaqs && faqs.length === 0 ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="p-5 rounded-xl border border-border-main bg-white space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="w-20 h-4 bg-warm-ivory border border-border-soft rounded" />
                <div className="w-16 h-4 bg-warm-ivory border border-border-soft rounded" />
              </div>
              <div className="w-3/4 h-5 bg-warm-ivory border border-border-soft rounded" />
              <div className="w-full h-12 bg-warm-ivory border border-border-soft rounded" />
            </div>
          ))}
        </div>
      ) : filteredFaqs.length === 0 ? (
        <EmptyState
          icon={<KnowledgeIcon className="w-6 h-6 text-cherry" />}
          title={
            languageFilter === "all"
              ? "No FAQs added yet"
              : `No FAQs found for ${languageFilter === "en" ? "English" : "Urdu"}`
          }
          description="Add structured questions and answers to give your AI agents accurate, curated business context."
          actionText="Add your first FAQ"
          onAction={openCreateModal}
        />
      ) : (
        <div className="space-y-3">
          {filteredFaqs.map((faq) => {
            const isUrdu = faq.language === "ur";
            const qDir = detectTextDirection(faq.question || "");
            const aDir = detectTextDirection(faq.answer);

            return (
              <Card
                key={faq.id}
                className="p-5 hover:border-cherry/40 transition duration-150"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="flex-1 space-y-2 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={isUrdu ? "indigo" : "default"}
                        className="text-[11px] font-medium"
                      >
                        {isUrdu ? "اردو (Urdu)" : faq.language === "en" ? "English" : faq.language}
                      </Badge>
                      {faq.has_embedding ? (
                        <Badge variant="success" className="text-[10px]">
                          <CheckCircleIcon className="w-3 h-3 text-status-success" />
                          <span>Indexed</span>
                        </Badge>
                      ) : (
                        <Badge variant="warning" className="text-[10px]">
                          <span>Pending Embedding</span>
                        </Badge>
                      )}
                      {faq.tags &&
                        faq.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-[10px] px-2 py-0.5 rounded bg-warm-ivory text-secondary-text border border-border-soft"
                          >
                            #{tag}
                          </span>
                        ))}
                    </div>

                    {faq.question && (
                      <h4
                        className="text-sm font-semibold text-main-text leading-snug"
                        dir={qDir}
                      >
                        {faq.question}
                      </h4>
                    )}

                    <p
                      className="text-xs text-secondary-text leading-relaxed whitespace-pre-wrap"
                      dir={aDir}
                    >
                      {faq.answer}
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5 self-end sm:self-start shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditModal(faq)}
                      aria-label="Edit FAQ"
                      className="text-xs p-1.5 h-auto text-secondary-text hover:text-main-text"
                    >
                      <EditIcon className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeletingFaq(faq)}
                      aria-label="Delete FAQ"
                      className="text-xs p-1.5 h-auto text-secondary-text hover:text-status-error"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create / Edit FAQ Modal */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="faq-modal-title"
          className="fixed inset-0 z-50 bg-main-text/40 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto"
        >
          <div className="bg-white rounded-2xl border border-border-main p-6 max-w-lg w-full shadow-lg space-y-5 my-8">
            <div className="flex items-center justify-between pb-3 border-b border-border-soft">
              <h3
                id="faq-modal-title"
                className="text-base font-semibold text-main-text"
              >
                {editingFaq ? "Edit FAQ" : "Add New FAQ"}
              </h3>
              <button
                type="button"
                onClick={closeModal}
                className="p-1 rounded-md text-secondary-text hover:text-main-text hover:bg-warm-ivory transition"
                aria-label="Close dialog"
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>

            {(validationError || error) && (
              <div
                role="alert"
                className="p-3 rounded-lg bg-status-error/10 border border-status-error/20 flex items-start gap-2.5 text-xs text-status-error"
              >
                <AlertCircleIcon className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{validationError || error}</span>
              </div>
            )}

            <form onSubmit={handleFormSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="faq-question"
                  className="block text-xs font-medium text-main-text mb-1"
                >
                  Question (Optional for generic knowledge)
                </label>
                <input
                  id="faq-question"
                  type="text"
                  value={formQuestion}
                  onChange={(e) => setFormQuestion(e.target.value)}
                  placeholder="e.g. What are your delivery hours? / آپ کے ڈیلیوری کے اوقات کیا ہیں؟"
                  dir={detectTextDirection(formQuestion)}
                  maxLength={500}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-border-main focus:outline-none focus:ring-2 focus:ring-cherry/30 bg-warm-ivory/30"
                />
              </div>

              <div>
                <label
                  htmlFor="faq-answer"
                  className="block text-xs font-medium text-main-text mb-1"
                >
                  Answer <span className="text-cherry">*</span>
                </label>
                <textarea
                  id="faq-answer"
                  required
                  rows={4}
                  value={formAnswer}
                  onChange={(e) => setFormAnswer(e.target.value)}
                  placeholder="Detailed business information provided to customers during inquiries..."
                  dir={detectTextDirection(formAnswer)}
                  maxLength={2000}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-border-main focus:outline-none focus:ring-2 focus:ring-cherry/30 bg-warm-ivory/30 leading-relaxed"
                />
                <span className="text-[10px] text-secondary-text mt-1 block text-right">
                  {formAnswer.length} / 2000 characters
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="faq-language"
                    className="block text-xs font-medium text-main-text mb-1"
                  >
                    Language
                  </label>
                  <select
                    id="faq-language"
                    value={formLanguage}
                    onChange={(e) => setFormLanguage(e.target.value as KnowledgeLanguage)}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-border-main focus:outline-none focus:ring-2 focus:ring-cherry/30 bg-warm-ivory/30"
                  >
                    <option value="en">English (en)</option>
                    <option value="ur">اردو (Urdu - ur)</option>
                    <option value="mixed">Mixed (mixed)</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="faq-tags"
                    className="block text-xs font-medium text-main-text mb-1"
                  >
                    Tags (Comma-separated)
                  </label>
                  <input
                    id="faq-tags"
                    type="text"
                    value={formTags}
                    onChange={(e) => setFormTags(e.target.value)}
                    placeholder="pricing, hours, returns"
                    className="w-full px-3 py-2 text-xs rounded-lg border border-border-main focus:outline-none focus:ring-2 focus:ring-cherry/30 bg-warm-ivory/30"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-border-soft">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={closeModal}
                  disabled={isMutating}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={isMutating}
                  className="text-xs gap-1.5"
                >
                  {isMutating && (
                    <div className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  )}
                  <span>{editingFaq ? "Save Changes" : "Create FAQ"}</span>
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deletingFaq && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
          className="fixed inset-0 z-50 bg-main-text/40 backdrop-blur-xs flex items-center justify-center p-4"
        >
          <div className="bg-white rounded-2xl border border-border-main p-6 max-w-md w-full shadow-lg space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-status-error/10 text-status-error flex items-center justify-center shrink-0">
                <TrashIcon className="w-5 h-5" />
              </div>
              <div>
                <h3
                  id="delete-dialog-title"
                  className="text-sm font-semibold text-main-text"
                >
                  Delete FAQ
                </h3>
                <p className="text-xs text-secondary-text mt-0.5">
                  This FAQ will be removed from your knowledge base and vector index.
                </p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-warm-ivory/60 border border-border-soft text-xs text-secondary-text italic max-h-24 overflow-y-auto">
              &quot;{deletingFaq.question || deletingFaq.answer.slice(0, 100)}...&quot;
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setDeletingFaq(null)}
                disabled={isMutating}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleConfirmDelete}
                disabled={isMutating}
                className="text-xs bg-status-error hover:bg-status-error/90 border-transparent text-white gap-1.5"
              >
                {isMutating && (
                  <div className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                )}
                <span>Confirm Delete</span>
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
