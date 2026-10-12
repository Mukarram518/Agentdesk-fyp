/**
 * AgentDesk Authentication Types.
 * Matches backend FastAPI authentication schemas.
 */

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  verified: boolean;
  is_active: boolean;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface AuthResponse {
  user: AuthUser;
}

export interface LogoutResponse {
  success: boolean;
}

export interface GoogleAuthUrlResponse {
  authorization_url: string;
}
