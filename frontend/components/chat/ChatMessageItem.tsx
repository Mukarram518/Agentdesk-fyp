"use client";

import React from "react";
import type { ChatUIMessage } from "@/types/chat";
import { SparklesIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

export interface ChatMessageItemProps {
  message: ChatUIMessage;
}

function formatMessageTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return "";
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function ChatMessageItem({ message }: ChatMessageItemProps) {
  const isUser = message.role === "user";
  const formattedTime = formatMessageTime(message.createdAt);

  return (
    <div
      className={cn(
        "flex gap-2.5 max-w-[85%] sm:max-w-[75%]",
        isUser ? "ml-auto flex-row-reverse" : "mr-auto flex-row"
      )}
      data-testid={`chat-message-${message.role}`}
    >
      {/* Assistant Avatar */}
      {!isUser && (
        <div
          className="w-7 h-7 rounded-lg bg-cherry-soft border border-border-soft flex items-center justify-center text-cherry shrink-0 mt-0.5 shadow-2xs"
          aria-hidden="true"
        >
          <SparklesIcon className="w-3.5 h-3.5" />
        </div>
      )}

      {/* Bubble + Metadata Container */}
      <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
        {/* Message Bubble */}
        <div
          dir={message.direction}
          className={cn(
            "px-4 py-2.5 rounded-2xl text-xs sm:text-sm leading-relaxed whitespace-pre-wrap break-words shadow-2xs",
            isUser
              ? "bg-cherry text-white rounded-br-xs"
              : "bg-white border border-border-main text-main-text rounded-bl-xs",
            message.status === "sending" && "opacity-80",
            message.status === "error" && "border-status-error/40 bg-cherry/90"
          )}
        >
          {message.content}
        </div>

        {/* Status / Timestamp Footer */}
        <div
          className={cn(
            "mt-1 px-1 flex items-center gap-1.5 text-[10px] text-muted-text font-mono",
            isUser ? "justify-end" : "justify-start"
          )}
        >
          {message.status === "sending" && (
            <span className="text-cherry font-sans flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-cherry animate-ping" />
              <span>Sending...</span>
            </span>
          )}

          {message.status === "error" && (
            <span className="text-status-error font-sans font-medium">
              {message.errorMessage || "Failed to send"}
            </span>
          )}

          {message.status === "sent" && formattedTime && (
            <span>{formattedTime}</span>
          )}
        </div>
      </div>
    </div>
  );
}
