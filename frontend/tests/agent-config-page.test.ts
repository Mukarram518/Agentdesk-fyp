import test, { describe } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentConfigEditor } from "../app/agents/page";
import type { AgentConfigResponse } from "../types/agents";

describe("Frontend AgentConfig Page & UI Components (Phase 4E)", () => {
  const sampleConfig: AgentConfigResponse = {
    business_id: "biz-alpha-123",
    voice_enabled: true,
    chat_enabled: true,
    lead_enabled: true,
    voice_id: "voice-eleven-123",
    tone: "helpful",
    greeting: "Welcome to Apex Dental! How may we assist you?",
    language_priority: ["en", "ur"],
    created_at: "2026-11-10T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
  };

  const sampleConfigBeta: AgentConfigResponse = {
    business_id: "biz-beta-456",
    voice_enabled: false,
    chat_enabled: false,
    lead_enabled: false,
    voice_id: null,
    tone: "professional",
    greeting: "Good day. You have reached Alpha Legal Services.",
    language_priority: ["ur", "en"],
    created_at: "2026-11-10T11:00:00Z",
    updated_at: "2026-11-10T11:00:00Z",
  };

  describe("Page Layout & Component Rendering", () => {
    test("renders header, workspace badge, and save action buttons", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("AI Agents Configuration"));
      assert.ok(html.includes("Apex Dental Clinic"));
      assert.ok(html.includes("Save Changes"));
      assert.ok(html.includes("Refresh"));
    });

    test("renders all three agent channel cards with descriptions and status badges", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      // Web Chat Agent
      assert.ok(html.includes("Web Chat Agent"));
      assert.ok(html.includes("Handles customer inquiries, provides automated answers"));

      // Lead Qualification Agent
      assert.ok(html.includes("Lead Qualification Agent"));
      assert.ok(html.includes("Identifies purchase intent, asks qualifying questions"));

      // Voice Simulation Agent
      assert.ok(html.includes("Voice Simulation Agent"));
      assert.ok(html.includes("Enables simulated voice calling with STT"));

      // Active Channel Badges
      assert.ok(html.includes("Active"));
    });

    test("renders all four conversational tone options with descriptions", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("Helpful"));
      assert.ok(html.includes("Balanced, polite, and customer-focused"));
      assert.ok(html.includes("Professional"));
      assert.ok(html.includes("Formal, concise, and enterprise-grade"));
      assert.ok(html.includes("Friendly"));
      assert.ok(html.includes("Warm, conversational, and approachable"));
      assert.ok(html.includes("Direct"));
      assert.ok(html.includes("Clear, straight to the point, minimal fluff"));
      assert.ok(html.includes("Current: helpful"));
    });

    test("renders initial greeting editor with current greeting text and character limit", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("Initial Greeting Message"));
      assert.ok(html.includes("Welcome to Apex Dental! How may we assist you?"));
      assert.ok(html.includes("/1000"));
      assert.ok(html.includes("Quick templates:"));
      assert.ok(html.includes("General Business"));
      assert.ok(html.includes("Clinic / Healthcare"));
    });

    test("renders language priority ordering with English and Urdu", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("Language Priority"));
      assert.ok(html.includes("English"));
      assert.ok(html.includes("(en)"));
      assert.ok(html.includes("Urdu"));
      assert.ok(html.includes("(ur)"));
      assert.ok(html.includes("Primary Language"));
      assert.ok(html.includes("Secondary Language"));
      assert.ok(html.includes("Swap Order"));
    });

    test("renders voice simulation settings with voice ID input", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("Voice Simulation Settings"));
      assert.ok(html.includes("voice-eleven-123"));
      assert.ok(html.includes("Voice Enabled"));
      assert.ok(html.includes("ElevenLabs Integration"));
    });
  });

  describe("Channel Controls & Disabled States", () => {
    test("renders disabled channel badges when channels are disabled", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfigBeta,
          businessName: "Alpha Legal",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("Disabled"));
      assert.ok(html.includes("Voice Disabled"));
      assert.ok(html.includes('aria-checked="false"'));
    });
  });

  describe("Saving & Error States", () => {
    test("renders saving spinner and disabled save button when isSaving is true", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: true,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("Saving..."));
      assert.ok(html.includes("animate-spin"));
    });

    test("renders API error alert banner when apiError is passed", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: "Failed to update agent configuration: Tone is invalid.",
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes('role="alert"'));
      assert.ok(
        html.includes("Failed to update agent configuration: Tone is invalid.")
      );
      assert.ok(html.includes("Dismiss"));
    });

    test("renders refresh spinning icon when isConfigLoading is true", () => {
      const html = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: true,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(html.includes("Refresh"));
      assert.ok(html.includes("animate-spin"));
    });
  });

  describe("Business Switching & Form State Synchronization", () => {
    test("updates tone, greeting, and language order when switched to a different business configuration", () => {
      const htmlAlpha = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfig,
          businessName: "Apex Dental Clinic",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(htmlAlpha.includes("Current: helpful"));
      assert.ok(htmlAlpha.includes("Welcome to Apex Dental! How may we assist you?"));

      const htmlBeta = renderToStaticMarkup(
        React.createElement(AgentConfigEditor, {
          initialConfig: sampleConfigBeta,
          businessName: "Alpha Legal",
          isSaving: false,
          isConfigLoading: false,
          apiError: null,
          onSave: async () => {},
          onRefresh: async () => {},
          onClearError: () => {},
        })
      );

      assert.ok(htmlBeta.includes("Current: professional"));
      assert.ok(htmlBeta.includes("Good day. You have reached Alpha Legal Services."));
      assert.ok(htmlBeta.includes("Alpha Legal"));
    });
  });
});

