"use client";

import React, { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  ConversationsIcon,
  LeadsIcon,
  PhoneIcon,
  CheckCircleIcon,
  AlertCircleIcon,
  RefreshIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  SparklesIcon,
} from "@/components/ui/icons";
import { useAuth } from "@/lib/auth/AuthContext";
import { useBusiness } from "@/lib/business/BusinessContext";
import { useAgentConfig } from "@/lib/agents/use-agent-config";
import type { AgentTone, AgentConfigResponse, AgentConfigUpdate } from "@/types/agents";
import { VALID_AGENT_TONES } from "@/types/agents";

interface FormState {
  chat_enabled: boolean;
  lead_enabled: boolean;
  voice_enabled: boolean;
  tone: AgentTone;
  greeting: string;
  language_priority: string[];
  voice_id: string;
}

const TONE_DESCRIPTIONS: Record<AgentTone, { label: string; description: string }> = {
  helpful: {
    label: "Helpful",
    description: "Balanced, polite, and customer-focused. Great for general business support.",
  },
  professional: {
    label: "Professional",
    description: "Formal, concise, and enterprise-grade. Ideal for corporate and medical clinics.",
  },
  friendly: {
    label: "Friendly",
    description: "Warm, conversational, and approachable. Perfect for hospitality and retail.",
  },
  direct: {
    label: "Direct",
    description: "Clear, straight to the point, minimal fluff. Best for fast transactional inquiries.",
  },
};

const LANGUAGE_LABELS: Record<string, { name: string; nativeName: string }> = {
  en: { name: "English", nativeName: "English" },
  ur: { name: "Urdu", nativeName: "اردو" },
};

function configToFormState(config: AgentConfigResponse): FormState {
  return {
    chat_enabled: Boolean(config.chat_enabled),
    lead_enabled: Boolean(config.lead_enabled),
    voice_enabled: Boolean(config.voice_enabled),
    tone: (config.tone as AgentTone) || "helpful",
    greeting: config.greeting || "",
    language_priority:
      config.language_priority && config.language_priority.length > 0
        ? [...config.language_priority]
        : ["en", "ur"],
    voice_id: config.voice_id || "",
  };
}

interface AgentConfigEditorProps {
  initialConfig: AgentConfigResponse;
  businessName: string;
  isSaving: boolean;
  isConfigLoading: boolean;
  apiError: string | null;
  onSave: (payload: AgentConfigUpdate) => Promise<void>;
  onRefresh: () => Promise<unknown>;
  onClearError: () => void;
}

export function AgentConfigEditor({
  initialConfig,
  businessName,
  isSaving,
  isConfigLoading,
  apiError,
  onSave,
  onRefresh,
  onClearError,
}: AgentConfigEditorProps) {
  const [form, setForm] = useState<FormState>(() => configToFormState(initialConfig));
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [localValidationError, setLocalValidationError] = useState<string | null>(null);

  // Compute dirty (unsaved changes) state
  const isDirty = useMemo(() => {
    const base = configToFormState(initialConfig);

    if (form.chat_enabled !== base.chat_enabled) return true;
    if (form.lead_enabled !== base.lead_enabled) return true;
    if (form.voice_enabled !== base.voice_enabled) return true;
    if (form.tone !== base.tone) return true;
    if (form.greeting !== base.greeting) return true;
    if (form.voice_id !== base.voice_id) return true;

    if (form.language_priority.length !== base.language_priority.length) return true;
    for (let i = 0; i < form.language_priority.length; i++) {
      if (form.language_priority[i] !== base.language_priority[i]) return true;
    }

    return false;
  }, [initialConfig, form]);

  const handleToggleChannel = (channel: "chat_enabled" | "lead_enabled" | "voice_enabled") => {
    setSuccessMessage(null);
    setLocalValidationError(null);
    setForm((prev) => ({
      ...prev,
      [channel]: !prev[channel],
    }));
  };

  const handleToneChange = (tone: AgentTone) => {
    setSuccessMessage(null);
    setLocalValidationError(null);
    setForm((prev) => ({ ...prev, tone }));
  };

  const handleGreetingChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setSuccessMessage(null);
    setLocalValidationError(null);
    setForm((prev) => ({ ...prev, greeting: e.target.value }));
  };

  const handleVoiceIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSuccessMessage(null);
    setLocalValidationError(null);
    setForm((prev) => ({ ...prev, voice_id: e.target.value }));
  };

  const handleSwapLanguagePriority = () => {
    setSuccessMessage(null);
    setLocalValidationError(null);
    setForm((prev) => {
      const current = [...prev.language_priority];
      if (current.length >= 2) {
        const [first, second] = current;
        return { ...prev, language_priority: [second, first] };
      }
      return prev;
    });
  };

  const handleReset = () => {
    setForm(configToFormState(initialConfig));
    setSuccessMessage(null);
    setLocalValidationError(null);
    onClearError();
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSuccessMessage(null);
    setLocalValidationError(null);
    onClearError();

    // Client-side validations
    if (form.greeting.length > 1000) {
      setLocalValidationError("Greeting message cannot exceed 1000 characters.");
      return;
    }
    if (form.voice_id.length > 100) {
      setLocalValidationError("Voice ID cannot exceed 100 characters.");
      return;
    }
    if (form.language_priority.length === 0) {
      setLocalValidationError("At least one language priority must be specified.");
      return;
    }

    const payload: AgentConfigUpdate = {
      chat_enabled: form.chat_enabled,
      lead_enabled: form.lead_enabled,
      voice_enabled: form.voice_enabled,
      tone: form.tone,
      greeting: form.greeting.trim() || null,
      language_priority: form.language_priority,
      voice_id: form.voice_id.trim() || null,
    };

    try {
      await onSave(payload);
      setSuccessMessage("Agent configuration saved successfully.");
    } catch {
      // Error is caught and surfaced via apiError prop
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Header & Save Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-border-main">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold text-main-text tracking-tight">
              AI Agents Configuration
            </h1>
            <Badge variant="cherry" className="text-xs">
              {businessName}
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-secondary-text mt-1 max-w-2xl">
            Configure communication channels, conversational tone, greeting message, language
            fallback priority, and browser voice simulation.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isConfigLoading || isSaving}
            aria-label="Refresh configuration from server"
            title="Refresh configuration from server"
          >
            <RefreshIcon
              className={`w-3.5 h-3.5 mr-1.5 ${isConfigLoading ? "animate-spin" : ""}`}
            />
            <span>Refresh</span>
          </Button>

          {isDirty && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={isSaving}
            >
              Discard
            </Button>
          )}

          <Button
            type="button"
            id="save-agent-config-btn"
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            disabled={isSaving || !isDirty}
            className="min-w-[120px]"
          >
            {isSaving ? (
              <>
                <div className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin mr-1.5" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <CheckCircleIcon className="w-3.5 h-3.5 mr-1.5" />
                <span>Save Changes</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Status / Alert Messages */}
      {successMessage && (
        <div
          role="status"
          className="flex items-center justify-between p-3.5 rounded-xl bg-status-success/10 border border-status-success/20 text-status-success text-xs sm:text-sm shadow-xs transition"
        >
          <div className="flex items-center gap-2.5">
            <CheckCircleIcon className="w-4 h-4 shrink-0" />
            <span className="font-medium">{successMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            className="text-status-success/70 hover:text-status-success text-xs font-semibold px-2 py-0.5 rounded cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {(localValidationError || apiError) && (
        <div
          role="alert"
          className="flex items-center justify-between p-3.5 rounded-xl bg-status-error/10 border border-status-error/20 text-status-error text-xs sm:text-sm shadow-xs transition"
        >
          <div className="flex items-center gap-2.5">
            <AlertCircleIcon className="w-4 h-4 shrink-0" />
            <span className="font-medium">{localValidationError || apiError}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setLocalValidationError(null);
              onClearError();
            }}
            className="text-status-error/70 hover:text-status-error text-xs font-semibold px-2 py-0.5 rounded cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {isDirty && !successMessage && !localValidationError && !apiError && (
        <div className="flex items-center justify-between px-4 py-2.5 rounded-xl bg-status-warning/10 border border-status-warning/20 text-status-warning text-xs shadow-xs">
          <span className="font-medium">
            You have unsaved changes. Remember to click &ldquo;Save Changes&rdquo; to apply them to your AI agents.
          </span>
          <span className="text-[11px] underline cursor-pointer" onClick={handleReset}>
            Reset
          </span>
        </div>
      )}

      {/* Section 1: Agent Channel Controls */}
      <div>
        <div className="mb-4">
          <h2 className="text-base font-semibold text-main-text">
            Agent Channel Controls
          </h2>
          <p className="text-xs text-secondary-text mt-0.5">
            Enable or disable specialized AI agents individually according to your business needs.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* 1. Chat Agent */}
          <Card hoverEffect className="relative flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-cherry-soft text-cherry border border-border-soft flex items-center justify-center shrink-0">
                  <ConversationsIcon className="w-5 h-5" />
                </div>
                <Badge variant={form.chat_enabled ? "success" : "default"}>
                  {form.chat_enabled ? "Active" : "Disabled"}
                </Badge>
              </div>

              <h3 className="text-sm font-semibold text-main-text">Web Chat Agent</h3>
              <p className="text-xs text-secondary-text mt-1.5 leading-relaxed">
                Handles customer inquiries, provides automated answers using your business knowledge base, and delivers 24/7 web assistance.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-border-soft flex items-center justify-between">
              <span className="text-xs font-medium text-main-text">Channel Status</span>
              <button
                type="button"
                id="toggle-chat-agent"
                role="switch"
                aria-checked={form.chat_enabled}
                aria-label="Toggle Web Chat Agent"
                onClick={() => handleToggleChannel("chat_enabled")}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-cherry/30 ${
                  form.chat_enabled ? "bg-cherry" : "bg-border-main"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-xs ring-0 transition duration-200 ease-in-out ${
                    form.chat_enabled ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          </Card>

          {/* 2. Lead Agent */}
          <Card hoverEffect className="relative flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-cherry-soft text-cherry border border-border-soft flex items-center justify-center shrink-0">
                  <LeadsIcon className="w-5 h-5" />
                </div>
                <Badge variant={form.lead_enabled ? "success" : "default"}>
                  {form.lead_enabled ? "Active" : "Disabled"}
                </Badge>
              </div>

              <h3 className="text-sm font-semibold text-main-text">Lead Qualification Agent</h3>
              <p className="text-xs text-secondary-text mt-1.5 leading-relaxed">
                Identifies purchase intent, asks qualifying questions, and collects contact details. If disabled, conversations continue without lead extraction.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-border-soft flex items-center justify-between">
              <span className="text-xs font-medium text-main-text">Channel Status</span>
              <button
                type="button"
                id="toggle-lead-agent"
                role="switch"
                aria-checked={form.lead_enabled}
                aria-label="Toggle Lead Qualification Agent"
                onClick={() => handleToggleChannel("lead_enabled")}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-cherry/30 ${
                  form.lead_enabled ? "bg-cherry" : "bg-border-main"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-xs ring-0 transition duration-200 ease-in-out ${
                    form.lead_enabled ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          </Card>

          {/* 3. Voice Agent */}
          <Card hoverEffect className="relative flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-cherry-soft text-cherry border border-border-soft flex items-center justify-center shrink-0">
                  <PhoneIcon className="w-5 h-5" />
                </div>
                <Badge variant={form.voice_enabled ? "success" : "default"}>
                  {form.voice_enabled ? "Active" : "Disabled"}
                </Badge>
              </div>

              <h3 className="text-sm font-semibold text-main-text">Voice Simulation Agent</h3>
              <p className="text-xs text-secondary-text mt-1.5 leading-relaxed">
                Enables simulated voice calling with STT, neural TTS, and bilingual responses. If disabled, new voice sessions are blocked server-side.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-border-soft flex items-center justify-between">
              <span className="text-xs font-medium text-main-text">Channel Status</span>
              <button
                type="button"
                id="toggle-voice-agent"
                role="switch"
                aria-checked={form.voice_enabled}
                aria-label="Toggle Voice Simulation Agent"
                onClick={() => handleToggleChannel("voice_enabled")}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-cherry/30 ${
                  form.voice_enabled ? "bg-cherry" : "bg-border-main"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-xs ring-0 transition duration-200 ease-in-out ${
                    form.voice_enabled ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          </Card>
        </div>
      </div>

      {/* Section 2: Conversational Tone Selector */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Conversational Tone</CardTitle>
            <p className="text-xs text-secondary-text mt-1">
              Select how your AI agent presents itself during conversations with customers.
            </p>
          </div>
          <Badge variant="indigo" className="text-[11px] capitalize">
            Current: {form.tone}
          </Badge>
        </CardHeader>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {VALID_AGENT_TONES.map((toneKey) => {
            const info = TONE_DESCRIPTIONS[toneKey];
            const isSelected = form.tone === toneKey;

            return (
              <button
                key={toneKey}
                type="button"
                id={`tone-option-${toneKey}`}
                role="radio"
                aria-checked={isSelected}
                onClick={() => handleToneChange(toneKey)}
                className={`p-4 rounded-xl border text-left transition duration-150 flex flex-col justify-between group focus:outline-none focus:ring-2 focus:ring-cherry/30 cursor-pointer ${
                  isSelected
                    ? "bg-cherry-soft/70 border-cherry shadow-xs"
                    : "bg-white border-border-main hover:border-cherry/40 hover:bg-warm-ivory/50"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`text-sm font-semibold capitalize ${
                        isSelected ? "text-cherry" : "text-main-text"
                      }`}
                    >
                      {info.label}
                    </span>
                    <span
                      className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                        isSelected
                          ? "border-cherry bg-cherry text-white"
                          : "border-border-main bg-white group-hover:border-cherry/40"
                      }`}
                    >
                      {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                    </span>
                  </div>
                  <p className="text-xs text-secondary-text leading-relaxed">
                    {info.description}
                  </p>
                </div>

                {isSelected && (
                  <span className="text-[10px] text-cherry font-medium mt-3 flex items-center gap-1">
                    <SparklesIcon className="w-3 h-3" /> Selected tone
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </Card>

      {/* Section 3: Initial Greeting Message */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Initial Greeting Message</CardTitle>
            <p className="text-xs text-secondary-text mt-1">
              The welcoming message automatically sent to customers when they begin a new conversation.
            </p>
          </div>
          <span className="text-xs text-secondary-text">
            <span
              className={
                form.greeting.length > 1000
                  ? "text-status-error font-semibold"
                  : "text-secondary-text"
              }
            >
              {form.greeting.length}
            </span>
            /1000
          </span>
        </CardHeader>

        <div className="space-y-3">
          <textarea
            id="agent-greeting-input"
            rows={4}
            value={form.greeting}
            onChange={handleGreetingChange}
            maxLength={1000}
            placeholder="e.g. Hello! Welcome to our clinic. How can our AI assistant help you today?"
            className="w-full p-3.5 rounded-xl border border-border-main bg-warm-ivory/30 text-main-text text-sm focus:outline-none focus:ring-2 focus:ring-cherry/30 focus:border-cherry/60 transition resize-y leading-relaxed"
          />

          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted-text">Quick templates:</span>
              <button
                type="button"
                onClick={() =>
                  setForm((prev) => ({
                    ...prev,
                    greeting: "Hello! Welcome to our store. How can we assist you today?",
                  }))
                }
                className="text-[11px] text-cherry hover:underline font-medium cursor-pointer"
              >
                General Business
              </button>
              <span className="text-border-main">•</span>
              <button
                type="button"
                onClick={() =>
                  setForm((prev) => ({
                    ...prev,
                    greeting:
                      "Welcome to our clinic. You can ask questions about our services or book an appointment.",
                  }))
                }
                className="text-[11px] text-cherry hover:underline font-medium cursor-pointer"
              >
                Clinic / Healthcare
              </button>
            </div>

            {form.greeting && (
              <button
                type="button"
                onClick={() => setForm((prev) => ({ ...prev, greeting: "" }))}
                className="text-[11px] text-secondary-text hover:text-main-text cursor-pointer"
              >
                Clear message
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Section 4: Language Priority & Voice ID */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Language Priority Selector */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Language Priority</CardTitle>
              <p className="text-xs text-secondary-text mt-1">
                Order of language preference for greetings, retrieval fallback, and voice generation.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleSwapLanguagePriority}
              aria-label="Swap language priority order"
            >
              <ArrowUpIcon className="w-3 h-3 mr-1" />
              <ArrowDownIcon className="w-3 h-3 mr-1.5" />
              <span>Swap Order</span>
            </Button>
          </CardHeader>

          <div className="space-y-3">
            {form.language_priority.map((langCode, index) => {
              const lang = LANGUAGE_LABELS[langCode] || {
                name: langCode.toUpperCase(),
                nativeName: langCode,
              };
              const isPrimary = index === 0;

              return (
                <div
                  key={langCode}
                  className={`flex items-center justify-between p-3.5 rounded-xl border transition ${
                    isPrimary
                      ? "bg-cherry-soft/50 border-cherry/40"
                      : "bg-white border-border-main"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-6 h-6 rounded-full text-xs font-semibold flex items-center justify-center ${
                        isPrimary
                          ? "bg-cherry text-white"
                          : "bg-border-soft text-secondary-text"
                      }`}
                    >
                      {index + 1}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-main-text">
                          {lang.name}
                        </span>
                        <span className="text-xs text-secondary-text font-mono">
                          ({langCode})
                        </span>
                      </div>
                      <span className="text-xs text-muted-text">
                        {lang.nativeName}
                      </span>
                    </div>
                  </div>

                  <Badge variant={isPrimary ? "cherry" : "outline"} className="text-[11px]">
                    {isPrimary ? "Primary Language" : "Secondary Language"}
                  </Badge>
                </div>
              );
            })}

            <p className="text-[11px] text-muted-text mt-2 leading-relaxed">
              AgentDesk dynamically understands Urdu and English. The primary language dictates default bot initializations and voice fallback synthesis.
            </p>
          </div>
        </Card>

        {/* Voice ID Configuration */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Voice Simulation Settings</CardTitle>
              <p className="text-xs text-secondary-text mt-1">
                Configure custom voice identifiers for browser-based voice synthesis.
              </p>
            </div>
            <Badge variant={form.voice_enabled ? "success" : "default"}>
              {form.voice_enabled ? "Voice Enabled" : "Voice Disabled"}
            </Badge>
          </CardHeader>

          <div className="space-y-4">
            <div>
              <label
                htmlFor="voice-id-input"
                className="block text-xs font-semibold text-main-text mb-1"
              >
                Voice ID (ElevenLabs Identifier)
              </label>
              <input
                id="voice-id-input"
                type="text"
                value={form.voice_id}
                onChange={handleVoiceIdChange}
                maxLength={100}
                placeholder="e.g. 21m00Tcm4TlvDq8ikWAM (Optional)"
                className="w-full px-3.5 py-2.5 rounded-xl border border-border-main bg-warm-ivory/30 text-main-text text-sm focus:outline-none focus:ring-2 focus:ring-cherry/30 focus:border-cherry/60 transition"
              />
              <p className="text-[11px] text-muted-text mt-1.5 leading-relaxed">
                Optional custom voice identifier. If left empty, AgentDesk will use the default business voice synthesis model.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-warm-ivory border border-border-soft flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-main-text">ElevenLabs Integration</p>
                <p className="text-[11px] text-secondary-text">
                  Neural multi-lingual speech with natural conversational cadence.
                </p>
              </div>
              <Badge variant="indigo" className="text-[10px]">
                v2 Multi-lingual
              </Badge>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function AgentConfigPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const { currentBusiness, isLoadingBusiness, businessError } = useBusiness();

  const {
    config,
    isLoading: isConfigLoading,
    isSaving,
    error: apiError,
    updateConfig,
    fetchConfig,
    clearError,
  } = useAgentConfig();

  // Redirect to login if unauthenticated
  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthLoading, isAuthenticated, router]);

  // Auth loading state
  if (isAuthLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-warm-ivory">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-cherry border-t-transparent animate-spin" />
          <p className="text-xs text-secondary-text font-medium">Verifying session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <AppShell activeItem="agents">
      <div className="space-y-8">
        {/* Workspace Error Alert */}
        {businessError && (
          <div
            role="alert"
            className="flex items-center gap-2.5 p-3.5 rounded-xl bg-status-error/10 border border-status-error/20 text-status-error text-xs sm:text-sm shadow-xs"
          >
            <AlertCircleIcon className="w-4 h-4 shrink-0" />
            <span className="font-medium">{businessError}</span>
          </div>
        )}

        {/* Configuration Error Alert (Initial Load Failure) */}
        {apiError && !config && currentBusiness && (
          <div
            role="alert"
            className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-status-error/10 border border-status-error/20 text-status-error text-xs sm:text-sm shadow-xs"
          >
            <div className="flex items-center gap-2.5">
              <AlertCircleIcon className="w-4 h-4 shrink-0" />
              <span className="font-medium">{apiError}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void fetchConfig()}
              className="text-xs shrink-0"
            >
              Retry
            </Button>
          </div>
        )}

        {/* Empty Workspace State */}
        {!isLoadingBusiness && !currentBusiness && (
          <EmptyState
            title="No Active Workspace Selected"
            description="Please select or set up a business workspace to manage and configure your AI agents."
            actionText="Go to Dashboard"
            onAction={() => router.push("/")}
          />
        )}

        {/* Loading Skeleton */}
        {(isConfigLoading || isLoadingBusiness) && !config && currentBusiness && (
          <div className="space-y-6 animate-pulse">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="h-44 rounded-xl bg-white border border-border-main p-6" />
              <div className="h-44 rounded-xl bg-white border border-border-main p-6" />
              <div className="h-44 rounded-xl bg-white border border-border-main p-6" />
            </div>
            <div className="h-56 rounded-xl bg-white border border-border-main p-6" />
            <div className="h-48 rounded-xl bg-white border border-border-main p-6" />
          </div>
        )}

        {/* Active Editor */}
        {currentBusiness && config && (
          <AgentConfigEditor
            key={`${config.business_id}-${config.updated_at}`}
            initialConfig={config}
            businessName={currentBusiness.name}
            isSaving={isSaving}
            isConfigLoading={isConfigLoading}
            apiError={apiError}
            onSave={async (payload) => {
              await updateConfig(payload);
            }}
            onRefresh={async () => {
              await fetchConfig();
            }}
            onClearError={clearError}
          />
        )}
      </div>
    </AppShell>
  );
}
