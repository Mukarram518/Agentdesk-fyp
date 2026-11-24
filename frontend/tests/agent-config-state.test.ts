import test, { describe, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  AgentConfigStore,
  INITIAL_AGENT_CONFIG_STATE,
  extractApiErrorMessage,
} from "../lib/agents/agent-config-store";
import {
  ApiClient,
  ApiHttpError,
  ApiNetworkError,
} from "../lib/api/client";
import {
  isAgentTone,
  isSupportedLanguage,
  type AgentConfigResponse,
} from "../types/agents";

function setTestState(
  store: AgentConfigStore,
  partial: {
    config?: AgentConfigResponse | null;
    isLoading?: boolean;
    isSaving?: boolean;
    error?: string | null;
  }
): void {
  (
    store as unknown as {
      setState: (p: {
        config?: AgentConfigResponse | null;
        isLoading?: boolean;
        isSaving?: boolean;
        error?: string | null;
      }) => void;
    }
  ).setState(partial);
}

describe("Frontend AgentConfig State Store", () => {
  let mockClient: ApiClient;

  const sampleConfig: AgentConfigResponse = {
    business_id: "biz-alpha",
    voice_enabled: true,
    chat_enabled: true,
    lead_enabled: true,
    voice_id: null,
    tone: "helpful",
    greeting: "Welcome to Alpha Clinic! How may we assist you?",
    language_priority: ["en", "ur"],
    created_at: "2026-11-10T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
  };

  const sampleConfigBeta: AgentConfigResponse = {
    business_id: "biz-beta",
    voice_enabled: false,
    chat_enabled: true,
    lead_enabled: false,
    voice_id: "voice-beta",
    tone: "professional",
    greeting: "Welcome to Beta Corp.",
    language_priority: ["ur", "en"],
    created_at: "2026-11-10T11:00:00Z",
    updated_at: "2026-11-10T11:00:00Z",
  };

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  describe("Initial State & Snapshots", () => {
    test("initializes with null config, false loading flags, and null error", () => {
      const store = new AgentConfigStore({ client: mockClient });
      const state = store.getSnapshot();

      assert.strictEqual(state.config, null);
      assert.strictEqual(state.isLoading, false);
      assert.strictEqual(state.isSaving, false);
      assert.strictEqual(state.error, null);
      assert.strictEqual(store.getBusinessId(), null);
    });

    test("getServerSnapshot returns stable, frozen reference", () => {
      const store = new AgentConfigStore({ client: mockClient });
      const snap1 = store.getServerSnapshot();
      const snap2 = store.getServerSnapshot();

      assert.strictEqual(snap1, snap2);
      assert.strictEqual(snap1, INITIAL_AGENT_CONFIG_STATE);
    });

    test("notifies listeners on state changes and allows unsubscribe", () => {
      const store = new AgentConfigStore({ client: mockClient });
      let callCount = 0;

      const unsubscribe = store.subscribe(() => {
        callCount++;
      });

      store.setBusinessId("biz-1", false);
      assert.strictEqual(callCount, 1);

      unsubscribe();
      store.setBusinessId("biz-2", false);
      assert.strictEqual(callCount, 1);
    });
  });

  describe("fetchConfig & Loading Behavior", () => {
    test("fetchConfig returns null and does not load if no businessId is set", async () => {
      let apiCalled = false;
      mockClient.getAgentConfig = async () => {
        apiCalled = true;
        return sampleConfig;
      };

      const store = new AgentConfigStore({ client: mockClient });
      const result = await store.fetchConfig();

      assert.strictEqual(apiCalled, false);
      assert.strictEqual(result, null);
      assert.strictEqual(store.getSnapshot().config, null);
      assert.strictEqual(store.getSnapshot().isLoading, false);
    });

    test("loads configuration successfully for active business", async () => {
      mockClient.getAgentConfig = async () => sampleConfig;

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      const result = await store.fetchConfig();

      assert.strictEqual(result?.business_id, "biz-alpha");
      const state = store.getSnapshot();
      assert.strictEqual(state.isLoading, false);
      assert.strictEqual(state.error, null);
      assert.deepStrictEqual(state.config, sampleConfig);
    });

    test("handles API errors during fetch and records clean error message", async () => {
      mockClient.getAgentConfig = async () => {
        throw new ApiHttpError(403, "Forbidden", {
          detail: "Only the business owner or admin can access agent configuration.",
        });
      };

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      const result = await store.fetchConfig();

      assert.strictEqual(result, null);
      const state = store.getSnapshot();
      assert.strictEqual(state.isLoading, false);
      assert.strictEqual(state.config, null);
      assert.strictEqual(
        state.error,
        "Only the business owner or admin can access agent configuration."
      );
    });

    test("handles network failure during fetch", async () => {
      mockClient.getAgentConfig = async () => {
        throw new ApiNetworkError("Connection refused");
      };

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      const result = await store.fetchConfig();

      assert.strictEqual(result, null);
      const state = store.getSnapshot();
      assert.strictEqual(state.isLoading, false);
      assert.strictEqual(state.config, null);
      assert.strictEqual(state.error, "Connection refused");
    });
  });

  describe("Business Switching & Stale Response Protection", () => {
    test("setting businessId to null wipes state immediately", () => {
      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      // Simulate existing loaded state
      setTestState(store, { config: sampleConfig, error: "stale error" });

      store.setBusinessId(null);

      const state = store.getSnapshot();
      assert.strictEqual(state.config, null);
      assert.strictEqual(state.isLoading, false);
      assert.strictEqual(state.isSaving, false);
      assert.strictEqual(state.error, null);
      assert.strictEqual(store.getBusinessId(), null);
    });

    test("setting identical businessId is a no-op", () => {
      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      let callCount = 0;
      store.subscribe(() => {
        callCount++;
      });

      store.setBusinessId("biz-alpha");
      assert.strictEqual(callCount, 0);
    });

    test("stale in-flight fetch from previous business cannot overwrite state after business switch", async () => {
      let resolveAlpha!: (cfg: AgentConfigResponse) => void;
      mockClient.getAgentConfig = () => {
        return new Promise<AgentConfigResponse>((resolve) => {
          resolveAlpha = resolve;
        });
      };

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      const fetchPromiseAlpha = store.fetchConfig();

      assert.strictEqual(store.getSnapshot().isLoading, true);

      // User immediately switches to biz-beta before biz-alpha finishes loading
      mockClient.getAgentConfig = async () => sampleConfigBeta;
      store.setBusinessId("biz-beta", true);

      // Wait a tick for beta to settle
      await new Promise((r) => setTimeout(r, 10));

      const stateAfterBeta = store.getSnapshot();
      assert.strictEqual(stateAfterBeta.config?.business_id, "biz-beta");

      // Now biz-alpha finishes late
      resolveAlpha(sampleConfig);
      await fetchPromiseAlpha;

      // Ensure state is NOT overwritten by biz-alpha
      const stateFinal = store.getSnapshot();
      assert.strictEqual(stateFinal.config?.business_id, "biz-beta");
      assert.strictEqual(stateFinal.config?.greeting, "Welcome to Beta Corp.");
    });

    test("stale error from cancelled request does not overwrite active state", async () => {
      let rejectAlpha!: (err: unknown) => void;
      mockClient.getAgentConfig = () => {
        return new Promise<AgentConfigResponse>((_, reject) => {
          rejectAlpha = reject;
        });
      };

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      const fetchPromiseAlpha = store.fetchConfig();

      // Switch to biz-beta
      mockClient.getAgentConfig = async () => sampleConfigBeta;
      store.setBusinessId("biz-beta", true);

      await new Promise((r) => setTimeout(r, 10));

      // Reject biz-alpha after switch
      rejectAlpha(new ApiHttpError(500, "Internal Server Error"));
      await fetchPromiseAlpha;

      const state = store.getSnapshot();
      assert.strictEqual(state.error, null);
      assert.strictEqual(state.config?.business_id, "biz-beta");
    });
  });

  describe("updateConfig (PUT) & patchConfig (PATCH)", () => {
    test("updateConfig throws error if no business is selected", async () => {
      const store = new AgentConfigStore({ client: mockClient });

      await assert.rejects(
        async () => {
          await store.updateConfig({ tone: "friendly" });
        },
        /No active business selected/
      );
    });

    test("updateConfig performs PUT and updates local config state", async () => {
      const updatedConfig: AgentConfigResponse = {
        ...sampleConfig,
        tone: "friendly",
        updated_at: "2026-11-10T12:00:00Z",
      };

      mockClient.updateAgentConfig = async (payload) => {
        assert.strictEqual(payload.tone, "friendly");
        return updatedConfig;
      };

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      setTestState(store, { config: sampleConfig });

      const result = await store.updateConfig({ tone: "friendly" });

      assert.strictEqual(result.tone, "friendly");
      const state = store.getSnapshot();
      assert.strictEqual(state.isSaving, false);
      assert.strictEqual(state.error, null);
      assert.strictEqual(state.config?.tone, "friendly");
      assert.strictEqual(state.config?.updated_at, "2026-11-10T12:00:00Z");
    });

    test("patchConfig performs PATCH and updates local config state", async () => {
      const patchedConfig: AgentConfigResponse = {
        ...sampleConfig,
        chat_enabled: false,
        updated_at: "2026-11-10T13:00:00Z",
      };

      mockClient.patchAgentConfig = async (payload) => {
        assert.strictEqual(payload.chat_enabled, false);
        return patchedConfig;
      };

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      setTestState(store, { config: sampleConfig });

      const result = await store.patchConfig({ chat_enabled: false });

      assert.strictEqual(result.chat_enabled, false);
      const state = store.getSnapshot();
      assert.strictEqual(state.isSaving, false);
      assert.strictEqual(state.error, null);
      assert.strictEqual(state.config?.chat_enabled, false);
    });

    test("updateConfig on API error records error and rethrows", async () => {
      mockClient.updateAgentConfig = async () => {
        throw new ApiHttpError(422, "Unprocessable Entity", {
          detail: [{ loc: ["body", "greeting"], msg: "Greeting message cannot exceed 1000 characters." }],
        });
      };

      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });

      await assert.rejects(
        async () => {
          await store.updateConfig({ greeting: "x".repeat(1001) });
        },
        (err: unknown) => {
          assert.ok(err instanceof ApiHttpError);
          return true;
        }
      );

      const state = store.getSnapshot();
      assert.strictEqual(state.isSaving, false);
      assert.strictEqual(
        state.error,
        "Greeting message cannot exceed 1000 characters."
      );
    });

    test("clearError resets error field to null", () => {
      const store = new AgentConfigStore({ client: mockClient });
      setTestState(store, { error: "Something broke" });

      assert.strictEqual(store.getSnapshot().error, "Something broke");
      store.clearError();
      assert.strictEqual(store.getSnapshot().error, null);
    });

    test("reset clears all state and increments active request counter", () => {
      const store = new AgentConfigStore({ client: mockClient, businessId: "biz-alpha" });
      setTestState(store, {
        config: sampleConfig,
        isLoading: true,
        isSaving: true,
        error: "failed",
      });

      store.reset();

      const state = store.getSnapshot();
      assert.strictEqual(state.config, null);
      assert.strictEqual(state.isLoading, false);
      assert.strictEqual(state.isSaving, false);
      assert.strictEqual(state.error, null);
    });
  });

  describe("Error Message Extraction Helper", () => {
    test("extracts string detail from ApiHttpError", () => {
      const err = new ApiHttpError(400, "Bad Request", { detail: "Custom error detail" });
      assert.strictEqual(extractApiErrorMessage(err), "Custom error detail");
    });

    test("extracts first validation error from Pydantic detail array", () => {
      const err = new ApiHttpError(422, "Validation Error", {
        detail: [
          { loc: ["body", "tone"], msg: "Tone cannot be empty" },
          { loc: ["body", "voice_id"], msg: "Voice ID invalid" },
        ],
      });
      assert.strictEqual(extractApiErrorMessage(err), "Tone cannot be empty");
    });

    test("falls back to error.message if no detail object is present", () => {
      const err = new ApiHttpError(500, "Internal Server Error");
      assert.strictEqual(extractApiErrorMessage(err), "Request failed with status 500 (Internal Server Error)");
    });

    test("handles standard Error instances", () => {
      const err = new Error("General disk fault");
      assert.strictEqual(extractApiErrorMessage(err), "General disk fault");
    });

    test("handles non-error objects with default fallback", () => {
      assert.strictEqual(extractApiErrorMessage("random string"), "An unexpected error occurred.");
      assert.strictEqual(extractApiErrorMessage(null, "Custom fallback"), "Custom fallback");
    });
  });

  describe("Type Guards & Validation Helpers", () => {
    test("isAgentTone accepts valid tones and normalizes case/whitespace", () => {
      assert.strictEqual(isAgentTone("helpful"), true);
      assert.strictEqual(isAgentTone("professional"), true);
      assert.strictEqual(isAgentTone("friendly"), true);
      assert.strictEqual(isAgentTone("direct"), true);
      assert.strictEqual(isAgentTone("  HELPFUL  "), true);
      assert.strictEqual(isAgentTone("Friendly"), true);

      assert.strictEqual(isAgentTone("sarcastic"), false);
      assert.strictEqual(isAgentTone(""), false);
      assert.strictEqual(isAgentTone(null), false);
      assert.strictEqual(isAgentTone(123), false);
    });

    test("isSupportedLanguage accepts en and ur and normalizes case/whitespace", () => {
      assert.strictEqual(isSupportedLanguage("en"), true);
      assert.strictEqual(isSupportedLanguage("ur"), true);
      assert.strictEqual(isSupportedLanguage("EN"), true);
      assert.strictEqual(isSupportedLanguage(" ur "), true);

      assert.strictEqual(isSupportedLanguage("fr"), false);
      assert.strictEqual(isSupportedLanguage("es"), false);
      assert.strictEqual(isSupportedLanguage(""), false);
      assert.strictEqual(isSupportedLanguage(undefined), false);
    });
  });
});
