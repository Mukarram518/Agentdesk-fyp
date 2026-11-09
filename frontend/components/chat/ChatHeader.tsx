"use client";

import React from "react";
import type { ChatStatus } from "@/types/chat";
import { SparklesIcon, TrashIcon, CloseIcon } from "@/components/ui/icons";

export interface ChatHeaderProps {
  status: ChatStatus;
  isSending?: boolean;
  onClear: () => void;
  onClose?: () => void;
  title?: string;
}

export function ChatHeader({
  status,
  isSending = false,
  onClear,
  onClose,
  title = "AgentDesk AI Assistant",
}: ChatHeaderProps) {
  const getStatusBadge = () => {
    if (isSending || status === "sending") {
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-cherry">
          <span className="w-1.5 h-1.5 rounded-full bg-cherry animate-pulse" />
          <span>Thinking...</span>
        </span>
      );
    }
    if (status === "loading_token") {
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-secondary-text">
          <span className="w-1.5 h-1.5 rounded-full bg-border-main animate-ping" />
          <span>Connecting...</span>
        </span>
      );
    }
    if (status === "error") {
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-status-error">
          <span className="w-1.5 h-1.5 rounded-full bg-status-error" />
          <span>Error</span>
        </span>
      );
    }
    // "ready" or "idle"
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-status-success">
        <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
        <span>Online</span>
      </span>
    );
  };

  return (
    <header className="px-5 py-3.5 border-b border-border-main bg-white flex items-center justify-between gap-3 shrink-0">
      {/* Title & Status */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-8 h-8 rounded-xl bg-cherry-soft border border-border-soft flex items-center justify-center text-cherry shrink-0">
          <SparklesIcon className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-main-text truncate leading-tight">
            {title}
          </h2>
          <div className="mt-0.5">{getStatusBadge()}</div>
        </div>
      </div>

      {/* Header Actions */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          type="button"
          onClick={onClear}
          disabled={isSending}
          className="p-2 rounded-lg text-secondary-text hover:text-main-text hover:bg-cherry-soft transition disabled:opacity-40 disabled:cursor-not-allowed"
          title="Clear conversation thread"
          aria-label="Clear conversation thread"
        >
          <TrashIcon className="w-4 h-4" />
        </button>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-secondary-text hover:text-main-text hover:bg-cherry-soft transition"
            title="Close preview"
            aria-label="Close preview"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        )}
      </div>
    </header>
  );
}
