/**
 * AgentDesk Agent Configuration Types.
 * Defines TypeScript contracts matching backend Pydantic schemas:
 * - AgentConfigResponse
 * - AgentConfigUpdate
 * - Allowed tones, languages, and channel enablement flags.
 */

export type AgentTone = "helpful" | "professional" | "friendly" | "direct";

export type SupportedLanguage = "en" | "ur";

export const VALID_AGENT_TONES: readonly AgentTone[] = Object.freeze([
  "helpful",
  "professional",
  "friendly",
  "direct",
] as const);

export const SUPPORTED_AGENT_LANGUAGES: readonly SupportedLanguage[] = Object.freeze([
  "en",
  "ur",
] as const);

export const DEFAULT_LANGUAGE_PRIORITY: readonly SupportedLanguage[] = Object.freeze([
  "en",
  "ur",
] as const);

export const DEFAULT_TONE: AgentTone = "helpful";

/**
 * Public agent configuration representation returned to authenticated users.
 * Matches backend `AgentConfigResponse`.
 */
export interface AgentConfigResponse {
  business_id: string;
  voice_enabled: boolean;
  chat_enabled: boolean;
  lead_enabled: boolean;
  voice_id: string | null;
  tone: AgentTone | string;
  greeting: string | null;
  language_priority: string[];
  created_at: string;
  updated_at: string;
}

/**
 * Payload for updating agent configuration settings.
 * Matches backend `AgentConfigUpdate`.
 */
export interface AgentConfigUpdate {
  voice_enabled?: boolean;
  chat_enabled?: boolean;
  lead_enabled?: boolean;
  voice_id?: string | null;
  tone?: AgentTone;
  greeting?: string | null;
  language_priority?: string[];
}

/**
 * Channel toggles subset of agent configuration.
 */
export interface AgentChannelToggles {
  voice_enabled: boolean;
  chat_enabled: boolean;
  lead_enabled: boolean;
}

/**
 * Type guard for AgentTone.
 */
export function isAgentTone(value: unknown): value is AgentTone {
  return (
    typeof value === "string" &&
    VALID_AGENT_TONES.includes(value.trim().toLowerCase() as AgentTone)
  );
}

/**
 * Type guard for SupportedLanguage.
 */
export function isSupportedLanguage(value: unknown): value is SupportedLanguage {
  return (
    typeof value === "string" &&
    SUPPORTED_AGENT_LANGUAGES.includes(value.trim().toLowerCase() as SupportedLanguage)
  );
}

