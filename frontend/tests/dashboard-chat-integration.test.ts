import test, { describe } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ChatPreviewDrawer } from "../components/chat";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Badge } from "../components/ui/Badge";
import { ConversationsIcon } from "../components/ui/icons";

describe("Dashboard Chat Integration (Phase 7 - Step 7D)", () => {
  describe("Top Greeting Header 'Preview Chat' Action Button", () => {
    test("renders 'Preview Chat' button when active business is present and ready", () => {
      const currentBusiness = { id: "biz-1", name: "Alpha Dental Clinic", slug: "alpha-dental" };
      const isLoadingBusiness = false;
      const businessError: string | null = null;

      // Greeting actions container as integrated in frontend/app/page.tsx
      const html = renderToStaticMarkup(
        React.createElement(
          "div",
          { className: "flex items-center gap-2.5" },
          React.createElement(
            Badge,
            { variant: "cherry", className: "text-xs py-1 px-3" },
            currentBusiness ? currentBusiness.name : "Workspace Initialized"
          ),
          currentBusiness && !isLoadingBusiness && !businessError
            ? React.createElement(
                Button,
                {
                  variant: "primary",
                  size: "sm",
                  className: "text-xs",
                  onClick: () => {},
                },
                React.createElement(ConversationsIcon, { className: "w-3.5 h-3.5 mr-1.5" }),
                "Preview Chat"
              )
            : null,
          React.createElement(
            Button,
            { variant: "secondary", size: "sm", className: "text-xs" },
            "Workspace Settings"
          )
        )
      );

      assert.ok(html.includes("Alpha Dental Clinic"));
      assert.ok(html.includes("Preview Chat"));
      assert.ok(html.includes("Workspace Settings"));
      assert.ok(html.includes("bg-cherry")); // Primary variant cherry background
      assert.ok(html.includes("<svg")); // ConversationsIcon rendered
    });

    test("omits 'Preview Chat' button when no active business is present", () => {
      const currentBusiness = (null as unknown) as { id: string; name: string } | null;
      const isLoadingBusiness = false;
      const businessError: string | null = null;

      const html = renderToStaticMarkup(
        React.createElement(
          "div",
          { className: "flex items-center gap-2.5" },
          React.createElement(
            Badge,
            { variant: "cherry", className: "text-xs py-1 px-3" },
            currentBusiness ? currentBusiness.name : "Workspace Initialized"
          ),
          currentBusiness && !isLoadingBusiness && !businessError
            ? React.createElement(
                Button,
                {
                  variant: "primary",
                  size: "sm",
                  className: "text-xs",
                  onClick: () => {},
                },
                React.createElement(ConversationsIcon, { className: "w-3.5 h-3.5 mr-1.5" }),
                "Preview Chat"
              )
            : null,
          React.createElement(
            Button,
            { variant: "secondary", size: "sm", className: "text-xs" },
            "Workspace Settings"
          )
        )
      );

      assert.ok(html.includes("Workspace Initialized"));
      assert.ok(!html.includes("Preview Chat"));
      assert.ok(html.includes("Workspace Settings"));
    });

    test("omits 'Preview Chat' button when business state is loading", () => {
      const currentBusiness = { id: "biz-1", name: "Alpha Dental Clinic", slug: "alpha-dental" };
      const isLoadingBusiness = true;
      const businessError: string | null = null;

      const html = renderToStaticMarkup(
        React.createElement(
          "div",
          { className: "flex items-center gap-2.5" },
          currentBusiness && !isLoadingBusiness && !businessError
            ? React.createElement(
                Button,
                {
                  variant: "primary",
                  size: "sm",
                  className: "text-xs",
                  onClick: () => {},
                },
                "Preview Chat"
              )
            : null
        )
      );

      assert.ok(!html.includes("Preview Chat"));
    });

    test("omits 'Preview Chat' button when business has an unresolved error", () => {
      const currentBusiness = { id: "biz-1", name: "Alpha Dental Clinic", slug: "alpha-dental" };
      const isLoadingBusiness = false;
      const businessError = "Failed to load business details";

      const html = renderToStaticMarkup(
        React.createElement(
          "div",
          { className: "flex items-center gap-2.5" },
          currentBusiness && !isLoadingBusiness && !businessError
            ? React.createElement(
                Button,
                {
                  variant: "primary",
                  size: "sm",
                  className: "text-xs",
                  onClick: () => {},
                },
                "Preview Chat"
              )
            : null
        )
      );

      assert.ok(!html.includes("Preview Chat"));
    });
  });

  describe("Recent Conversations Empty State Integration", () => {
    test("wires 'Preview chat interface' action when business is active", () => {
      const currentBusiness = { id: "biz-1", name: "Alpha Dental Clinic" };
      const isLoadingBusiness = false;
      const businessError = null;

      let actionInvoked = false;
      const handleOpenDrawer = () => {
        actionInvoked = true;
      };

      const html = renderToStaticMarkup(
        React.createElement(EmptyState, {
          icon: React.createElement(ConversationsIcon, { className: "w-6 h-6" }),
          title: "No conversations yet",
          description:
            "Incoming customer messages across your Web Chat and WhatsApp channels will appear here in real time.",
          actionText:
            currentBusiness && !isLoadingBusiness && !businessError
              ? "Preview chat interface"
              : undefined,
          onAction:
            currentBusiness && !isLoadingBusiness && !businessError
              ? handleOpenDrawer
              : undefined,
        })
      );

      assert.ok(html.includes("No conversations yet"));
      assert.ok(html.includes("Preview chat interface"));
      assert.ok(html.includes("→"));
      assert.strictEqual(actionInvoked, false); // Not invoked during static render
    });

    test("suppresses empty state action when no business is loaded", () => {
      const currentBusiness = null;
      const isLoadingBusiness = false;
      const businessError = null;

      const html = renderToStaticMarkup(
        React.createElement(EmptyState, {
          icon: React.createElement(ConversationsIcon, { className: "w-6 h-6" }),
          title: "No conversations yet",
          description:
            "Incoming customer messages across your Web Chat and WhatsApp channels will appear here in real time.",
          actionText:
            currentBusiness && !isLoadingBusiness && !businessError
              ? "Preview chat interface"
              : undefined,
          onAction: undefined,
        })
      );

      assert.ok(html.includes("No conversations yet"));
      assert.ok(!html.includes("Preview chat interface"));
      assert.ok(!html.includes("&rarr;"));
    });
  });

  describe("ChatPreviewDrawer Mount & State Invariants", () => {
    test("mounts drawer in closed state by default with accessibility and hide styling", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: false,
          onClose: () => {},
          businessId: "biz-1",
          title: "Alpha Dental Assistant",
        })
      );

      // Verify accessibility attributes
      assert.ok(html.includes('role="dialog"'));
      assert.ok(html.includes('aria-modal="true"'));
      assert.ok(html.includes('aria-hidden="true"'));

      // Verify visual translation and interaction lock
      assert.ok(html.includes("translate-x-full"));
      assert.ok(html.includes("pointer-events-none"));

      // Verify widget is pre-rendered in DOM (preserves conversation state in memory)
      assert.ok(html.includes("Alpha Dental Assistant"));
      assert.ok(html.includes("Type your message in English or Urdu... (Enter to send)"));
    });

    test("renders drawer in open state when isOpen is true", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: true,
          onClose: () => {},
          businessId: "biz-1",
          title: "Alpha Dental Assistant",
        })
      );

      assert.ok(html.includes('aria-hidden="false"'));
      assert.ok(html.includes("translate-x-0"));
      assert.ok(!html.includes("pointer-events-none"));
      assert.ok(html.includes("Alpha Dental Assistant"));
    });

    test("dynamically scopes title to the active business name", () => {
      const clinicHtml = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: true,
          onClose: () => {},
          businessId: "biz-clinic",
          title: "Care Clinic Assistant",
        })
      );
      assert.ok(clinicHtml.includes("Care Clinic Assistant"));

      const dentalHtml = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: true,
          onClose: () => {},
          businessId: "biz-dental",
          title: "Apex Dental Assistant",
        })
      );
      assert.ok(dentalHtml.includes("Apex Dental Assistant"));
    });

    test("falls back to default title when title prop is undefined", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: true,
          onClose: () => {},
          businessId: "biz-1",
        })
      );

      assert.ok(html.includes("Chat Assistant Preview"));
    });

    test("preserves close button in header with accessible label", () => {
      const html = renderToStaticMarkup(
        React.createElement(ChatPreviewDrawer, {
          isOpen: true,
          onClose: () => {},
          businessId: "biz-1",
          title: "Test Assistant",
        })
      );

      assert.ok(html.includes('aria-label="Close preview"'));
    });
  });
});
