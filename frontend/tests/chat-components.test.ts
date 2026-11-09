import test, { describe } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ChatEmptyState,
  ChatHeader,
  ChatMessageItem,
  ChatMessageList,
  ChatInput,
  ChatPreviewDrawer,
} from "../components/chat";
import type { ChatUIMessage } from "../types/chat";

describe("Dashboard Chat UI Components (Phase 7 - Step 7C)", () => {
  describe("ChatEmptyState", () => {
    test("renders welcome title, description, and suggested prompts", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatEmptyState, { onSelectPrompt: () => {} })
      );

      assert.ok(html.includes("Preview AI Assistant"));
      assert.ok(html.includes("Test your business knowledge base"));
      assert.ok(html.includes("Suggested Prompts"));
      assert.ok(html.includes("What services do you provide?"));
      assert.ok(html.includes("What are your operating hours?"));
      assert.ok(html.includes("کیا آپ کے پاس ڈاکٹر دستیاب ہیں؟"));
      assert.ok(html.includes("اپوائنٹمنٹ کیسے بک کریں؟"));
    });

    test("applies correct text direction to Urdu and English prompt buttons", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatEmptyState, { onSelectPrompt: () => {} })
      );

      // Urdu prompts must have dir="rtl"
      assert.ok(html.includes('dir="rtl"'));
      // English prompts must have dir="ltr"
      assert.ok(html.includes('dir="ltr"'));
    });
  });

  describe("ChatMessageItem", () => {
    const sampleUserMessage: ChatUIMessage = {
      id: "msg-user-1",
      role: "user",
      content: "Can I book an appointment?",
      createdAt: "2026-11-09T10:30:00.000Z",
      status: "sent",
      direction: "ltr",
      requestId: "req-user-1",
    };

    const sampleAssistantMessage: ChatUIMessage = {
      id: "msg-asst-1",
      role: "assistant",
      content: "Yes, our clinic is open tomorrow from 9 AM.",
      createdAt: "2026-11-09T10:30:05.000Z",
      status: "sent",
      direction: "ltr",
    };

    const sampleUrduMessage: ChatUIMessage = {
      id: "msg-urdu-1",
      role: "user",
      content: "کیا آپ مجھے فیس بتا سکتے ہیں؟",
      createdAt: "2026-11-09T10:31:00.000Z",
      status: "sent",
      direction: "rtl",
      requestId: "req-urdu-1",
    };

    test("renders user message with right alignment and cherry background", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatMessageItem, { message: sampleUserMessage })
      );

      assert.ok(html.includes("Can I book an appointment?"));
      assert.ok(html.includes("ml-auto flex-row-reverse"));
      assert.ok(html.includes("bg-cherry text-white"));
      assert.ok(html.includes('dir="ltr"'));
    });

    test("renders assistant message with left alignment, card border, and Sparkles icon", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatMessageItem, { message: sampleAssistantMessage })
      );

      assert.ok(html.includes("Yes, our clinic is open tomorrow from 9 AM."));
      assert.ok(html.includes("mr-auto flex-row"));
      assert.ok(html.includes("bg-white border border-border-main"));
      // Avatar check
      assert.ok(html.includes("<svg"));
    });

    test("applies dir=rtl to Urdu message bubble", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatMessageItem, { message: sampleUrduMessage })
      );

      assert.ok(html.includes("کیا آپ مجھے فیس بتا سکتے ہیں؟"));
      assert.ok(html.includes('dir="rtl"'));
    });

    test("renders sending state indicator when status is sending", () => {
      const sendingMessage: ChatUIMessage = {
        ...sampleUserMessage,
        status: "sending",
      };
      const html = renderToStaticMarkup(
        React.createElement(ChatMessageItem, { message: sendingMessage })
      );

      assert.ok(html.includes("Sending..."));
      assert.ok(html.includes("opacity-80"));
    });

    test("renders error message when status is error", () => {
      const errorMessage: ChatUIMessage = {
        ...sampleUserMessage,
        status: "error",
        errorMessage: "Network connection lost",
      };
      const html = renderToStaticMarkup(
        React.createElement(ChatMessageItem, { message: errorMessage })
      );

      assert.ok(html.includes("Network connection lost"));
      assert.ok(html.includes("border-status-error"));
    });
  });

  describe("ChatHeader", () => {
    test("renders header title and online status badge when ready", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatHeader, {
          status: "ready",
          isSending: false,
          onClear: () => {},
          title: "Acme Dental Assistant",
        })
      );

      assert.ok(html.includes("Acme Dental Assistant"));
      assert.ok(html.includes("Online"));
      assert.ok(html.includes("Clear conversation thread"));
    });

    test("renders thinking status when isSending is true", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatHeader, {
          status: "ready",
          isSending: true,
          onClear: () => {},
        })
      );

      assert.ok(html.includes("Thinking..."));
    });

    test("renders connecting status when loading_token", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatHeader, {
          status: "loading_token",
          isSending: false,
          onClear: () => {},
        })
      );

      assert.ok(html.includes("Connecting..."));
    });

    test("renders error status when status is error", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatHeader, {
          status: "error",
          isSending: false,
          onClear: () => {},
        })
      );

      assert.ok(html.includes("Error"));
    });

    test("renders close button when onClose callback is provided", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatHeader, {
          status: "ready",
          onClear: () => {},
          onClose: () => {},
        })
      );

      assert.ok(html.includes("Close preview"));
    });
  });

  describe("ChatMessageList", () => {
    test("renders ChatEmptyState when messages array is empty", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatMessageList, {
          messages: [],
          isSending: false,
          canRetry: false,
          onRetry: () => {},
          onSelectPrompt: () => {},
        })
      );

      assert.ok(html.includes("Preview AI Assistant"));
      assert.ok(html.includes("Suggested Prompts"));
    });

    test("renders message items and accessibility attributes when messages exist", () => {
      const messages: ChatUIMessage[] = [
        {
          id: "1",
          role: "user",
          content: "Hello",
          createdAt: "2026-11-09T10:00:00Z",
          status: "sent",
          direction: "ltr",
        },
        {
          id: "2",
          role: "assistant",
          content: "Hi there! How can I help?",
          createdAt: "2026-11-09T10:00:02Z",
          status: "sent",
          direction: "ltr",
        },
      ];

      const html = renderToStaticMarkup(
        React.createElement(ChatMessageList, {
          messages,
          isSending: false,
          canRetry: false,
          onRetry: () => {},
          onSelectPrompt: () => {},
        })
      );

      assert.ok(html.includes('role="log"'));
      assert.ok(html.includes('aria-live="polite"'));
      assert.ok(html.includes("Hello"));
      assert.ok(html.includes("Hi there! How can I help?"));
    });

    test("renders assistant typing indicator when isSending is true", () => {
      const messages: ChatUIMessage[] = [
        {
          id: "1",
          role: "user",
          content: "Processing question",
          createdAt: "2026-11-09T10:00:00Z",
          status: "sending",
          direction: "ltr",
        },
      ];

      const html = renderToStaticMarkup(
        React.createElement(ChatMessageList, {
          messages,
          isSending: true,
          canRetry: false,
          onRetry: () => {},
          onSelectPrompt: () => {},
        })
      );

      assert.ok(html.includes('aria-label="Assistant is typing"'));
      assert.ok(html.includes("animate-bounce"));
    });

    test("renders retry banner and button when canRetry is true", () => {
      const messages: ChatUIMessage[] = [
        {
          id: "1",
          role: "user",
          content: "Failed message",
          createdAt: "2026-11-09T10:00:00Z",
          status: "error",
          direction: "ltr",
        },
      ];

      const html = renderToStaticMarkup(
        React.createElement(ChatMessageList, {
          messages,
          isSending: false,
          canRetry: true,
          onRetry: () => {},
          onSelectPrompt: () => {},
        })
      );

      assert.ok(html.includes('role="alert"'));
      assert.ok(html.includes("Message could not be delivered"));
      assert.ok(html.includes("Retry sending failed message"));
    });
  });

  describe("ChatInput", () => {
    test("renders textarea, send button, and keyboard hints", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatInput, {
          onSend: async () => {},
          isSending: false,
          status: "ready",
        })
      );

      assert.ok(html.includes('aria-label="Chat message input"'));
      assert.ok(html.includes('aria-label="Send message"'));
      assert.ok(html.includes("Shift + Enter"));
    });

    test("disables textarea and send button when isSending is true", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatInput, {
          onSend: async () => {},
          isSending: true,
          status: "sending",
        })
      );

      // The textarea must be disabled
      assert.ok(html.includes("<textarea"));
      assert.ok(html.includes("disabled"));
      // The send button must have a spinner and disabled
      assert.ok(html.includes("animate-spin"));
    });
  });

  describe("ChatPreviewDrawer", () => {
    test("renders drawer in open state with visible backdrop and translate-x-0 panel", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: true,
          onClose: () => {},
          title: "Dental Care Preview",
        })
      );

      assert.ok(html.includes('role="dialog"'));
      assert.ok(html.includes('aria-modal="true"'));
      assert.ok(html.includes('aria-hidden="false"'));
      assert.ok(html.includes("visible pointer-events-auto"));
      assert.ok(html.includes("translate-x-0"));
      assert.ok(html.includes("opacity-100"));
      assert.ok(html.includes("Dental Care Preview"));
    });

    test("preserves DOM mounting in closed state with invisible classes and translate-x-full", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: false,
          onClose: () => {},
          title: "Dental Care Preview",
        })
      );

      // Invariant: The drawer remains in the DOM to preserve in-memory state,
      // but is hidden visually and accessible-wise.
      assert.ok(html.includes('role="dialog"'));
      assert.ok(html.includes('aria-hidden="true"'));
      assert.ok(html.includes("invisible pointer-events-none"));
      assert.ok(html.includes("translate-x-full"));
      assert.ok(html.includes("opacity-0"));
    });
  });
});
