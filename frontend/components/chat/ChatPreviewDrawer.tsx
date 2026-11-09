"use client";

import React, { useEffect, useRef } from "react";
import { ChatWidget } from "./ChatWidget";
import { cn } from "@/lib/utils";

export interface ChatPreviewDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  businessId?: string;
  title?: string;
}

/**
 * Slide-over drawer container for the dashboard chat preview.
 *
 * Lifecycle & Persistence Invariants:
 * 1. Keeps ChatWidget mounted in the React tree at all times so in-memory
 *    conversation state is preserved when closing and reopening the drawer.
 * 2. In-flight AI turns complete in the background even if closed mid-request.
 * 3. Hides visually (translate-x-full) and disables pointer/keyboard interaction when closed.
 * 4. Preserves and restores DOM focus to the triggering element upon closure.
 */
export function ChatPreviewDrawer({
  isOpen,
  onClose,
  businessId,
  title = "Chat Assistant Preview",
}: ChatPreviewDrawerProps) {
  const drawerPanelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);

  // Capture trigger focus and handle Escape key
  useEffect(() => {
    if (isOpen) {
      // Remember active element to restore focus on close
      previouslyFocusedElementRef.current = document.activeElement as HTMLElement | null;

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          onClose();
        }
      };

      window.addEventListener("keydown", handleKeyDown);
      return () => {
        window.removeEventListener("keydown", handleKeyDown);
      };
    } else {
      // Restore focus to opener when drawer closes
      if (previouslyFocusedElementRef.current && typeof previouslyFocusedElementRef.current.focus === "function") {
        previouslyFocusedElementRef.current.focus();
        previouslyFocusedElementRef.current = null;
      }
    }
  }, [isOpen, onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="chat-drawer-title"
      aria-hidden={!isOpen}
      className={cn(
        "fixed inset-0 z-50 transition-all duration-300",
        isOpen ? "visible pointer-events-auto" : "invisible pointer-events-none"
      )}
      data-testid="chat-preview-drawer"
    >
      {/* Background Backdrop Blur */}
      <div
        className={cn(
          "fixed inset-0 bg-main-text/40 backdrop-blur-xs transition-opacity duration-300",
          isOpen ? "opacity-100" : "opacity-0"
        )}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-Over Panel */}
      <div
        ref={drawerPanelRef}
        className={cn(
          "fixed inset-y-0 right-0 w-full sm:max-w-lg bg-card-bg shadow-2xl transition-transform duration-300 ease-in-out flex flex-col z-10",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        <span id="chat-drawer-title" className="sr-only">
          {title}
        </span>
        <ChatWidget
          businessId={businessId}
          onClose={onClose}
          title={title}
          className="h-full rounded-none border-0 sm:border-l sm:border-border-main"
        />
      </div>
    </div>
  );
}
