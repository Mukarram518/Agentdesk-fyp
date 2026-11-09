"use client";

import React, { useState, useRef, useEffect } from "react";
import type { ChatStatus } from "@/types/chat";
import { SendIcon } from "@/components/ui/icons";
import { detectTextDirection } from "@/lib/chat/text-direction";
import { cn } from "@/lib/utils";

export interface ChatInputProps {
  onSend: (message: string) => Promise<void>;
  isSending: boolean;
  status: ChatStatus;
  disabled?: boolean;
}

const MAX_MESSAGE_LENGTH = 2000;

export function ChatInput({
  onSend,
  isSending,
  disabled = false,
}: ChatInputProps) {
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const direction = detectTextDirection(draft);
  const isInputDisabled = disabled || isSending;
  const isOverLimit = draft.length > MAX_MESSAGE_LENGTH;
  const canSubmit = draft.trim().length > 0 && !isOverLimit && !isInputDisabled;

  // Auto-focus input on mount
  useEffect(() => {
    if (!isInputDisabled) {
      textareaRef.current?.focus();
    }
  }, [isInputDisabled]);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    const messageToSend = draft;
    setDraft("");

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      await onSend(messageToSend);
    } catch {
      // Restore draft if submission failed validation before turn began
      setDraft(messageToSend);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter key submits; Shift + Enter inserts newline
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    if (value.length <= MAX_MESSAGE_LENGTH + 50) {
      setDraft(value);
      // Auto-expand textarea
      e.target.style.height = "auto";
      e.target.style.height = `${Math.min(e.target.scrollHeight, 128)}px`;
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        handleSubmit();
      }}
      className="p-3.5 sm:p-4 border-t border-border-main bg-white"
      data-testid="chat-input-form"
    >
      <div className="relative flex items-end gap-2 p-1.5 rounded-2xl bg-warm-ivory border border-border-main focus-within:border-cherry focus-within:ring-1 focus-within:ring-cherry transition">
        {/* Multiline auto-expanding textarea */}
        <textarea
          ref={textareaRef}
          rows={1}
          dir={direction}
          disabled={isInputDisabled}
          value={draft}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Type your message in English or Urdu... (Enter to send)"
          aria-label="Chat message input"
          className={cn(
            "flex-1 px-3 py-2 text-xs sm:text-sm text-main-text placeholder:text-muted-text bg-transparent resize-none max-h-32 overflow-y-auto focus:outline-none disabled:opacity-50",
            direction === "rtl" ? "text-right" : "text-left"
          )}
        />

        {/* Send Button */}
        <button
          type="submit"
          disabled={!canSubmit}
          className="p-2.5 rounded-xl bg-cherry text-white hover:bg-cherry-hover disabled:opacity-40 disabled:cursor-not-allowed transition shadow-2xs shrink-0 active:scale-95 flex items-center justify-center"
          title="Send message"
          aria-label="Send message"
        >
          {isSending ? (
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <SendIcon className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Character limit notice */}
      <div className="mt-1.5 px-2 flex items-center justify-between text-[10px] text-muted-text">
        <span>Press <kbd className="font-mono bg-warm-ivory border border-border-soft px-1 rounded">Shift + Enter</kbd> for a new line</span>
        {draft.length >= 1500 && (
          <span
            className={cn(
              "font-mono",
              draft.length > MAX_MESSAGE_LENGTH ? "text-status-error font-semibold" : "text-muted-text"
            )}
          >
            {draft.length} / {MAX_MESSAGE_LENGTH}
          </span>
        )}
      </div>
    </form>
  );
}
