/**
 * AgentDesk Business Types.
 * Matches backend FastAPI business schemas defined in app/schemas/business.py.
 */

export type BusinessRole = "owner" | "admin" | "member";

export interface BusinessCreatePayload {
  name: string;
  slug?: string;
}

export interface BusinessResponse {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  role?: BusinessRole | null;
  created_at: string;
  updated_at: string;
}

export type Business = BusinessResponse;
