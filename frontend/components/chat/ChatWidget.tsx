"use client";

import React from "react";
import { useChat } from "@/lib/chat/use-chat";
import { ChatHeader } from "./ChatHeader";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";
import { cn } from "@/lib/utils";

export interface ChatWidgetProps {
  businessId?: string;
  onClose?: () => void;
  className?: string;
  title?: string;
}

/**
 * Master chat widget container.
 * The ONLY component that consumes the useChat hook.
 */
export function ChatWidget({
  businessId,
  onClose,
  className,
  title,
}: ChatWidgetProps) {
  const {
    messages,
    status,
    isSending,
    canRetry,
    sendMessage,
    retryLastMessage,
    clearConversation,
  } = useChat({ businessId });

  return (
    <div
      className={cn(
        "flex flex-col h-full bg-white rounded-xl border border-border-main overflow-hidden shadow-xs",
        className
      )}
      data-testid="chat-widget"
    >
      {/* Top Header */}
      <ChatHeader
        status={status}
        isSending={isSending}
        onClear={clearConversation}
        onClose={onClose}
        title={title}
      />

      {/* Message Viewport */}
      <ChatMessageList
        messages={messages}
        isSending={isSending}
        canRetry={canRetry}
        onRetry={retryLastMessage}
        onSelectPrompt={sendMessage}
      />

      {/* Bottom Input */}
      <ChatInput
        onSend={sendMessage}
        isSending={isSending}
        status={status}
      />
    </div>
  );
}
