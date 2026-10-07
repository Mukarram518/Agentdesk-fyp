/**
 * AgentDesk Core Types Foundation.
 */

export * from "./api";

export interface SystemHealth {
  status: "healthy" | "unhealthy" | "degraded";
  app: string;
  version: string;
  environment: string;
  timestamp: string;
  database?: {
    status: string;
    pgvector?: string;
    error?: string;
  };
  redis?: {
    status: string;
    error?: string;
  };
}
