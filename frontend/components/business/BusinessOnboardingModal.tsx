"use client";

import React, { useState, useEffect, useRef } from "react";
import { useBusiness } from "@/lib/business/BusinessContext";
import {
  generateSlug,
  validateBusinessName,
  validateBusinessSlug,
} from "@/lib/business/slug";
import { isApiClientError } from "@/lib/api/client";
import type { BusinessCreatePayload } from "@/types/business";
import { Button } from "@/components/ui/Button";
import { CloseIcon, SparklesIcon } from "@/components/ui/icons";

export interface BusinessOnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function BusinessOnboardingModal({
  isOpen,
  onClose,
}: BusinessOnboardingModalProps) {
  const { createBusiness } = useBusiness();

  const [name, setName] = useState("");
  const [customSlug, setCustomSlug] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [slugError, setSlugError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nameInputRef = useRef<HTMLInputElement>(null);

  // Suggested slug dynamically derived from business name
  const suggestedSlug = generateSlug(name);

  const resetForm = () => {
    setName("");
    setCustomSlug("");
    setNameError(null);
    setSlugError(null);
    setSubmitError(null);
    setIsSubmitting(false);
  };

  const handleClose = () => {
    if (isSubmitting) return;
    resetForm();
    onClose();
  };

  // Keyboard shortcut: Escape to close when not submitting
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isSubmitting) {
        handleClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting]);

  // Focus business name input when modal opens
  useEffect(() => {
    if (isOpen) {
      const frame = requestAnimationFrame(() => {
        nameInputRef.current?.focus();
      });
      return () => cancelAnimationFrame(frame);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setName(e.target.value);
    if (nameError) setNameError(null);
    if (submitError) setSubmitError(null);
  };

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCustomSlug(e.target.value);
    if (slugError) setSlugError(null);
    if (submitError) setSubmitError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    // Reset previous errors
    setNameError(null);
    setSlugError(null);
    setSubmitError(null);

    // Validate name and optional custom slug
    const nameValidation = validateBusinessName(name);
    const slugValidation = validateBusinessSlug(customSlug);

    let hasValidationError = false;

    if (!nameValidation.isValid) {
      setNameError(nameValidation.error);
      hasValidationError = true;
    }

    if (!slugValidation.isValid) {
      setSlugError(slugValidation.error);
      hasValidationError = true;
    }

    if (hasValidationError) {
      return;
    }

    const payload: BusinessCreatePayload = {
      name: nameValidation.cleaned!,
      ...(slugValidation.cleaned ? { slug: slugValidation.cleaned } : {}),
    };

    setIsSubmitting(true);

    try {
      await createBusiness(payload);
      // On success, close the modal and clear form state
      resetForm();
      onClose();
    } catch (err: unknown) {
      // On failure, preserve form state and show mapped error
      if (isApiClientError(err)) {
        if (err.statusCode === 409) {
          setSubmitError(
            "A business with this name or slug already exists. Please choose a different name or slug."
          );
        } else if (err.statusCode === 422) {
          setSubmitError(
            err.message || "Invalid business details. Please check your entries."
          );
        } else {
          setSubmitError(
            err.message || "Unable to create business. Please try again."
          );
        }
      } else {
        setSubmitError(
          "A network error occurred. Please check your connection and try again."
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-main-text/40 backdrop-blur-xs transition-opacity"
      onClick={handleClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-modal-title"
        aria-describedby="onboarding-modal-desc"
        className="w-full max-w-lg bg-card-bg rounded-2xl border border-border-main p-6 sm:p-8 shadow-xl relative animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={handleClose}
          disabled={isSubmitting}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-secondary-text hover:text-main-text hover:bg-cherry-soft transition disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Close dialog"
        >
          <CloseIcon className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-cherry-soft border border-border-soft w-fit mb-3">
          <SparklesIcon className="w-3.5 h-3.5 text-cherry" />
          <span className="text-xs font-medium text-cherry">Workspace Setup</span>
        </div>

        <h2
          id="onboarding-modal-title"
          className="text-xl sm:text-2xl font-bold text-main-text tracking-tight"
        >
          Set up your business
        </h2>

        <p
          id="onboarding-modal-desc"
          className="mt-1.5 text-xs sm:text-sm text-secondary-text leading-relaxed"
        >
          Configure your business workspace to begin connecting AI agents, knowledge base,
          and customer communication channels.
        </p>

        {/* Form Submission Error Alert */}
        {submitError && (
          <div
            role="alert"
            className="mt-5 p-3.5 rounded-lg bg-status-error/10 border border-status-error/20 text-status-error text-xs flex items-start gap-2.5"
          >
            <svg
              className="w-4 h-4 shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span className="font-medium leading-relaxed">{submitError}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-5" noValidate>
          {/* Business Name Field */}
          <div>
            <label
              htmlFor="business-name-input"
              className="block text-xs font-semibold text-main-text uppercase tracking-wider mb-1.5"
            >
              Business Name <span className="text-cherry">*</span>
            </label>
            <input
              ref={nameInputRef}
              id="business-name-input"
              name="name"
              type="text"
              required
              disabled={isSubmitting}
              value={name}
              onChange={handleNameChange}
              placeholder="e.g. Acme Dental Care"
              aria-invalid={!!nameError}
              aria-describedby={nameError ? "business-name-error" : undefined}
              className="w-full px-3.5 py-2.5 rounded-lg bg-warm-ivory border border-border-main text-sm text-main-text placeholder:text-muted-text focus:outline-none focus:border-cherry focus:ring-1 focus:ring-cherry transition disabled:opacity-50"
            />
            {nameError && (
              <p
                id="business-name-error"
                className="mt-1.5 text-xs text-status-error font-medium"
              >
                {nameError}
              </p>
            )}
          </div>

          {/* Custom Slug Field */}
          <div>
            <label
              htmlFor="business-slug-input"
              className="block text-xs font-semibold text-main-text uppercase tracking-wider mb-1.5"
            >
              Custom Slug{" "}
              <span className="text-muted-text font-normal normal-case">
                (optional)
              </span>
            </label>
            <p
              id="business-slug-hint"
              className="text-[11px] text-secondary-text mb-2 leading-normal"
            >
              Leave empty to automatically generate from your business name, or specify a custom URL-friendly identifier.
            </p>
            <input
              id="business-slug-input"
              name="slug"
              type="text"
              disabled={isSubmitting}
              value={customSlug}
              onChange={handleSlugChange}
              placeholder={suggestedSlug || "acme-dental-care"}
              aria-invalid={!!slugError}
              aria-describedby={
                slugError ? "business-slug-error" : "business-slug-hint"
              }
              className="w-full px-3.5 py-2.5 rounded-lg bg-warm-ivory border border-border-main text-sm text-main-text placeholder:text-muted-text focus:outline-none focus:border-cherry focus:ring-1 focus:ring-cherry transition disabled:opacity-50"
            />

            {/* Inline validation error */}
            {slugError && (
              <p
                id="business-slug-error"
                className="mt-1.5 text-xs text-status-error font-medium"
              >
                {slugError}
              </p>
            )}

            {/* Suggested slug preview when no custom slug is entered */}
            {!slugError && suggestedSlug && !customSlug && (
              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-secondary-text">
                <span className="text-muted-text">Suggested identifier:</span>
                <span className="font-mono text-cherry font-medium bg-cherry-soft px-1.5 py-0.5 rounded border border-border-soft">
                  {suggestedSlug}
                </span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={isSubmitting}
              className="min-w-[140px]"
            >
              {isSubmitting ? (
                <span className="inline-flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Creating workspace...</span>
                </span>
              ) : (
                <span>Create Workspace</span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
