"use client";

import React, { useEffect, useRef } from "react";
import type { ChatUIMessage } from "@/types/chat";
import { ChatMessageItem } from "./ChatMessageItem";
import { ChatEmptyState } from "./ChatEmptyState";
import { RefreshIcon, SparklesIcon } from "@/components/ui/icons";

export interface ChatMessageListProps {
  messages: ChatUIMessage[];
  isSending: boolean;
  canRetry: boolean;
  onRetry: () => void;
  onSelectPrompt: (promptText: string) => void;
}

export function ChatMessageList({
  messages,
  isSending,
  canRetry,
  onRetry,
  onSelectPrompt,
}: ChatMessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);

  // Monitor scroll position to avoid forcing auto-scroll when user reviews history
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
    userScrolledUpRef.current = distanceFromBottom > 100;
  };

  // Auto-scroll when new messages arrive or when sending starts, unless user scrolled up
  useEffect(() => {
    if (!userScrolledUpRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isSending]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col overflow-y-auto bg-warm-ivory/30">
        <ChatEmptyState onSelectPrompt={onSelectPrompt} />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      role="log"
      aria-live="polite"
      aria-label="Conversation history"
      className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 bg-warm-ivory/30"
      data-testid="chat-message-list"
    >
      {/* Messages */}
      {messages.map((message) => (
        <ChatMessageItem key={message.id || message.requestId} message={message} />
      ))}

      {/* Assistant Typing Indicator Bubble */}
      {isSending && (
        <div
          className="flex items-center gap-2 mr-auto"
          aria-label="Assistant is typing"
          data-testid="assistant-typing-indicator"
        >
          <div className="w-7 h-7 rounded-lg bg-cherry-soft border border-border-soft flex items-center justify-center text-cherry shrink-0 shadow-2xs">
            <SparklesIcon className="w-3.5 h-3.5" />
          </div>
          <div className="px-4 py-3 rounded-2xl rounded-bl-xs bg-white border border-border-main flex items-center gap-1.5 shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-cherry animate-bounce [animation-delay:-0.3s]" />
            <span className="w-1.5 h-1.5 rounded-full bg-cherry animate-bounce [animation-delay:-0.15s]" />
            <span className="w-1.5 h-1.5 rounded-full bg-cherry animate-bounce" />
          </div>
        </div>
      )}

      {/* Turn Delivery Failure / Retry Banner */}
      {canRetry && (
        <div
          role="alert"
          className="p-3 rounded-xl bg-status-error/10 border border-status-error/20 flex items-center justify-between gap-3 text-xs text-status-error"
          data-testid="chat-retry-banner"
        >
          <span className="font-medium">
            Message could not be delivered. Please try again.
          </span>
          <button
            type="button"
            onClick={onRetry}
            disabled={isSending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-status-error/30 text-status-error font-medium hover:bg-status-error/10 transition shadow-2xs disabled:opacity-50"
            aria-label="Retry sending failed message"
          >
            <RefreshIcon className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {/* Auto-scroll anchor */}
      <div ref={messagesEndRef} aria-hidden="true" />
    </div>
  );
}
