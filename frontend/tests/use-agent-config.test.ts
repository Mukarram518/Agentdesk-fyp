import test, { describe, beforeEach } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useAgentConfig, type UseAgentConfigReturn } from "../lib/agents/use-agent-config";
import { AgentConfigStore, INITIAL_AGENT_CONFIG_STATE } from "../lib/agents/agent-config-store";
import { BusinessContext, type BusinessContextType } from "../lib/business/BusinessContext";
import { ApiClient } from "../lib/api/client";
import type { AgentConfigResponse, BusinessResponse } from "../types";

describe("Frontend useAgentConfig Hook Integration", () => {
  let mockClient: ApiClient;

  const sampleConfig: AgentConfigResponse = {
    business_id: "biz-1234",
    voice_enabled: true,
    chat_enabled: true,
    lead_enabled: true,
    voice_id: null,
    tone: "helpful",
    greeting: "Welcome to AgentDesk!",
    language_priority: ["en", "ur"],
    created_at: "2026-11-10T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
  };

  const sampleBusiness: BusinessResponse = {
    id: "biz-context-id",
    name: "Apex Healthcare",
    slug: "apex-healthcare",
    is_active: true,
    role: "owner",
    created_at: "2026-10-13T10:00:00Z",
    updated_at: "2026-10-13T10:00:00Z",
  };

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  test("renders safely outside of BusinessProvider without throwing", () => {
    let capturedHookReturn!: UseAgentConfigReturn;

    function TestComponent() {
      capturedHookReturn = useAgentConfig({ client: mockClient, autoFetch: false });
      return React.createElement("div", null, "rendered");
    }

    const html = renderToStaticMarkup(React.createElement(TestComponent));
    assert.ok(html.includes("rendered"));
    assert.strictEqual(capturedHookReturn.config, null);
    assert.strictEqual(capturedHookReturn.isLoading, false);
    assert.strictEqual(capturedHookReturn.isSaving, false);
    assert.strictEqual(capturedHookReturn.error, null);
    assert.strictEqual(typeof capturedHookReturn.fetchConfig, "function");
    assert.strictEqual(typeof capturedHookReturn.updateConfig, "function");
    assert.strictEqual(typeof capturedHookReturn.patchConfig, "function");
    assert.strictEqual(typeof capturedHookReturn.clearError, "function");
    assert.strictEqual(typeof capturedHookReturn.reset, "function");
  });

  test("uses explicit businessId when provided in options", () => {
    let capturedHookReturn!: UseAgentConfigReturn;

    function TestComponent() {
      capturedHookReturn = useAgentConfig({
        businessId: "biz-explicit-99",
        client: mockClient,
        autoFetch: false,
      });
      return React.createElement("div", null, "rendered");
    }

    renderToStaticMarkup(React.createElement(TestComponent));
    assert.strictEqual(capturedHookReturn.store.getBusinessId(), "biz-explicit-99");
  });

  test("resolves businessId dynamically from BusinessContext when inside a provider", () => {
    let capturedHookReturn!: UseAgentConfigReturn;

    function TestComponent() {
      capturedHookReturn = useAgentConfig({ client: mockClient, autoFetch: false });
      return React.createElement(
        "div",
        null,
        capturedHookReturn.store.getBusinessId() || "none"
      );
    }

    const mockBusinessContextValue: BusinessContextType = {
      businesses: [sampleBusiness],
      currentBusiness: sampleBusiness,
      isLoadingBusiness: false,
      businessError: null,
      refreshBusinesses: async () => {},
      createBusiness: async () => sampleBusiness,
    };

    const html = renderToStaticMarkup(
      React.createElement(
        BusinessContext.Provider,
        { value: mockBusinessContextValue },
        React.createElement(TestComponent)
      )
    );

    assert.ok(html.includes("biz-context-id"));
    assert.strictEqual(capturedHookReturn.store.getBusinessId(), "biz-context-id");
  });

  test("supports custom injected store instance and SSR snapshot stability", () => {
    const customStore = new AgentConfigStore({ client: mockClient, businessId: "custom-biz" });
    (
      customStore as unknown as {
        setState: (p: { config: AgentConfigResponse }) => void;
      }
    ).setState({ config: sampleConfig });

    let capturedHookReturn!: UseAgentConfigReturn;

    function TestComponent() {
      capturedHookReturn = useAgentConfig({ store: customStore, autoFetch: false });
      return React.createElement(
        "div",
        null,
        capturedHookReturn.config ? capturedHookReturn.config.tone : "ssr-initial"
      );
    }

    const html = renderToStaticMarkup(React.createElement(TestComponent));
    // During SSR, useSyncExternalStore safely yields getServerSnapshot()
    assert.ok(html.includes("ssr-initial"));
    assert.strictEqual(capturedHookReturn.store, customStore);
    assert.strictEqual(capturedHookReturn.store.getSnapshot().config?.tone, "helpful");
    assert.strictEqual(capturedHookReturn.store.getServerSnapshot(), INITIAL_AGENT_CONFIG_STATE);
  });
});
