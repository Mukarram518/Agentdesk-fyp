/**
 * AgentDesk Typed API Client.
 * Centralized HTTP layer between Next.js frontend and FastAPI backend.
 */

import type { HealthResponse, RequestOptions } from "@/types/api";
import type {
  AuthUser,
  RegisterPayload,
  LoginPayload,
  AuthResponse,
  LogoutResponse,
  GoogleAuthUrlResponse,
} from "@/types/auth";
import type {
  BusinessCreatePayload,
  BusinessResponse,
} from "@/types/business";
import {
  ApiHttpError,
  ApiNetworkError,
  ApiParseError,
  ApiTimeoutError,
} from "./errors";

export * from "./errors";
export type { HealthResponse } from "@/types/api";
export type {
  AuthUser,
  RegisterPayload,
  LoginPayload,
  AuthResponse,
  LogoutResponse,
  GoogleAuthUrlResponse,
} from "@/types/auth";
export type {
  BusinessCreatePayload,
  BusinessResponse,
  Business,
} from "@/types/business";

export const DEFAULT_BASE_URL = "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 15000;

/**
 * Resolves the default backend base URL for API requests.
 * In a browser environment, aligns the API host with the current frontend hostname
 * (e.g. http://localhost:8000 when accessed via localhost:3000) so that session cookies
 * are treated as same-site and not blocked by browser SameSite=Lax rules.
 */
export function resolveDefaultBaseUrl(): string {
  if (typeof window !== "undefined" && window.location?.hostname) {
    const protocol = window.location.protocol || "http:";
    return `${protocol}//${window.location.hostname}:8000`;
  }
  return DEFAULT_BASE_URL;
}

export class ApiClient {
  readonly baseUrl: string;
  private readonly defaultTimeoutMs: number;

  constructor(baseUrl?: string, defaultTimeoutMs: number = DEFAULT_TIMEOUT_MS) {
    const rawUrl =
      baseUrl ||
      (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim()) ||
      resolveDefaultBaseUrl();
    // Normalize by stripping trailing slash
    this.baseUrl = rawUrl.replace(/\/+$/, "");
    this.defaultTimeoutMs = defaultTimeoutMs;
  }

  /**
   * Executes a typed HTTP request against the backend.
   */
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const {
      method = "GET",
      params,
      headers: customHeaders,
      body,
      timeoutMs = this.defaultTimeoutMs,
      credentials = "include",
      ...fetchInit
    } = options;

    // Build URL with query parameters
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    const url = new URL(`${this.baseUrl}${cleanPath}`);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.set(key, String(value));
        }
      });
    }

    // Setup headers
    const headers = new Headers(customHeaders);
    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }

    let serializedBody: BodyInit | undefined;
    if (body !== undefined && body !== null) {
      if (typeof body === "string" || body instanceof FormData || body instanceof Blob) {
        serializedBody = body as BodyInit;
      } else {
        headers.set("Content-Type", "application/json");
        serializedBody = JSON.stringify(body);
      }
    }

    // Setup timeout controller
    const controller = new AbortController();
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    if (timeoutMs > 0) {
      timeoutId = setTimeout(() => {
        controller.abort();
      }, timeoutMs);
    }

    let response: Response;
    try {
      response = await fetch(url.toString(), {
        ...fetchInit,
        method,
        headers,
        body: serializedBody,
        signal: controller.signal,
        credentials,
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new ApiTimeoutError(timeoutMs);
      }
      throw new ApiNetworkError(
        "Unable to reach the AgentDesk backend server. Please verify network connectivity.",
        err
      );
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    }

    // Handle non-2xx HTTP responses
    if (!response.ok) {
      let errorData: unknown;
      try {
        errorData = await response.json();
      } catch {
        try {
          errorData = await response.text();
        } catch {
          errorData = undefined;
        }
      }
      throw new ApiHttpError(response.status, response.statusText, errorData);
    }

    // Return empty result for 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    // Parse JSON response
    try {
      return (await response.json()) as T;
    } catch (err: unknown) {
      throw new ApiParseError(
        "Response could not be parsed as valid JSON.",
        err instanceof Error ? err.message : String(err)
      );
    }
  }

  // Convenience HTTP methods
  get<T>(path: string, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  post<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return this.request<T>(path, { ...options, method: "POST", body });
  }

  put<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return this.request<T>(path, { ...options, method: "PUT", body });
  }

  patch<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return this.request<T>(path, { ...options, method: "PATCH", body });
  }

  delete<T>(path: string, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return this.request<T>(path, { ...options, method: "DELETE" });
  }

  // Domain-level helper methods for Foundation Health
  async getHealth(options: { full?: boolean } = { full: true }): Promise<HealthResponse> {
    return this.get<HealthResponse>("/health", {
      params: { full: options.full ?? true },
      cache: "no-store",
    });
  }

  async getV1Health(options: { full?: boolean } = { full: true }): Promise<HealthResponse> {
    return this.get<HealthResponse>("/api/v1/health", {
      params: { full: options.full ?? true },
      cache: "no-store",
    });
  }

  async checkOperationalStatus(): Promise<boolean> {
    try {
      const res = await this.get<{ status: string }>("/health", {
        params: { full: false },
        cache: "no-store",
        timeoutMs: 5000,
      });
      return res.status === "healthy";
    } catch {
      return false;
    }
  }

  // Authentication API methods
  async register(payload: RegisterPayload): Promise<AuthResponse> {
    return this.post<AuthResponse>("/api/v1/auth/register", payload);
  }

  async login(payload: LoginPayload): Promise<AuthResponse> {
    return this.post<AuthResponse>("/api/v1/auth/login", payload);
  }

  async logout(): Promise<LogoutResponse> {
    return this.post<LogoutResponse>("/api/v1/auth/logout");
  }

  async getCurrentUser(): Promise<AuthUser> {
    return this.get<AuthUser>("/api/v1/auth/me", { cache: "no-store" });
  }

  async getGoogleAuthUrl(): Promise<string> {
    const res = await this.get<GoogleAuthUrlResponse>("/api/v1/auth/google", {
      params: { redirect: false },
    });
    return res.authorization_url;
  }

  // Business API methods
  async createBusiness(payload: BusinessCreatePayload): Promise<BusinessResponse> {
    return this.post<BusinessResponse>("/api/v1/businesses", payload);
  }

  async listBusinesses(): Promise<BusinessResponse[]> {
    return this.get<BusinessResponse[]>("/api/v1/businesses", { cache: "no-store" });
  }

  async getCurrentBusiness(): Promise<BusinessResponse> {
    return this.get<BusinessResponse>("/api/v1/businesses/current", { cache: "no-store" });
  }

  async getBusinessById(businessId: string): Promise<BusinessResponse> {
    return this.get<BusinessResponse>(`/api/v1/businesses/${businessId}`, { cache: "no-store" });
  }
}

// Global default singleton instance configured from environment
export const apiClient = new ApiClient();

// Backward-compatible helper used across frontend
export async function fetchBackendHealth(): Promise<HealthResponse> {
  return apiClient.getHealth({ full: true });
}
