/**
 * AgentDesk API Contract Types.
 * Matches backend FastAPI schemas defined in docs/05_API_DESIGN.md.
 */

export type HealthStatus = "healthy" | "unhealthy" | "degraded";

export interface DatabaseHealth {
  status: string;
  pgvector?: string;
  error?: string;
}

export interface RedisHealth {
  status: string;
  error?: string;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
  timestamp: string;
  database?: DatabaseHealth | null;
  redis?: RedisHealth | null;
}

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export interface ApiErrorPayload {
  detail?: string | ApiErrorDetail[];
  message?: string;
  status_code?: number;
}

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "HEAD";

export interface RequestOptions extends Omit<RequestInit, "body" | "method"> {
  method?: HttpMethod;
  params?: Record<string, string | number | boolean | undefined | null>;
  timeoutMs?: number;
  body?: unknown;
}
