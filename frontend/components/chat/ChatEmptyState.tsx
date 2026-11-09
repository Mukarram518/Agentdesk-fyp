"use client";

import React from "react";
import { SparklesIcon, ConversationsIcon } from "@/components/ui/icons";

export interface ChatEmptyStateProps {
  onSelectPrompt: (promptText: string) => void;
}

const DEFAULT_SUGGESTED_PROMPTS = [
  {
    label: "What services do you provide?",
    prompt: "What services do you provide?",
    direction: "ltr" as const,
  },
  {
    label: "What are your operating hours?",
    prompt: "What are your operating hours?",
    direction: "ltr" as const,
  },
  {
    label: "کیا آپ کے پاس ڈاکٹر دستیاب ہیں؟",
    prompt: "کیا آپ کے پاس ڈاکٹر دستیاب ہیں؟",
    direction: "rtl" as const,
  },
  {
    label: "اپوائنٹمنٹ کیسے بک کریں؟",
    prompt: "اپوائنٹمنٹ کیسے بک کریں؟",
    direction: "rtl" as const,
  },
];

export function ChatEmptyState({ onSelectPrompt }: ChatEmptyStateProps) {
  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto"
      data-testid="chat-empty-state"
    >
      {/* Icon badge */}
      <div className="w-12 h-12 rounded-2xl bg-cherry-soft border border-border-soft flex items-center justify-center text-cherry mb-4 shadow-2xs">
        <ConversationsIcon className="w-6 h-6" />
      </div>

      <h3 className="text-base font-semibold text-main-text tracking-tight mb-1">
        Preview AI Assistant
      </h3>
      <p className="text-xs text-secondary-text leading-relaxed mb-6">
        Test your business knowledge base, conversational flows, and appointment scheduling in English or Urdu.
      </p>

      {/* Suggested prompts section */}
      <div className="w-full space-y-2">
        <div className="flex items-center justify-center gap-1.5 text-[11px] font-medium text-muted-text uppercase tracking-wider mb-2">
          <SparklesIcon className="w-3.5 h-3.5 text-cherry" />
          <span>Suggested Prompts</span>
        </div>

        <div className="flex flex-col gap-2 w-full">
          {DEFAULT_SUGGESTED_PROMPTS.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt(item.prompt)}
              dir={item.direction}
              className="w-full px-3.5 py-2.5 text-xs text-main-text bg-white hover:bg-cherry-soft/60 border border-border-main hover:border-cherry/40 rounded-xl text-left transition shadow-2xs active:scale-[0.99] flex items-center justify-between gap-2"
              aria-label={`Send suggested prompt: ${item.label}`}
            >
              <span className={item.direction === "rtl" ? "text-right w-full" : "text-left"}>
                {item.label}
              </span>
              <span className="text-muted-text text-[10px] shrink-0 font-mono">&rarr;</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
