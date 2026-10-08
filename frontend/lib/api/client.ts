/**
 * AgentDesk Typed API Client.
 * Centralized HTTP layer between Next.js frontend and FastAPI backend.
 */

import type { HealthResponse, RequestOptions } from "@/types/api";
import {
  ApiHttpError,
  ApiNetworkError,
  ApiParseError,
  ApiTimeoutError,
} from "./errors";

export * from "./errors";
export type { HealthResponse } from "@/types/api";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 15000;

export class ApiClient {
  readonly baseUrl: string;
  private readonly defaultTimeoutMs: number;

  constructor(baseUrl?: string, defaultTimeoutMs: number = DEFAULT_TIMEOUT_MS) {
    const rawUrl = baseUrl || process.env.NEXT_PUBLIC_API_URL || DEFAULT_BASE_URL;
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
        method,
        headers,
        body: serializedBody,
        signal: controller.signal,
        ...fetchInit,
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
}

// Global default singleton instance configured from environment
export const apiClient = new ApiClient();

// Backward-compatible helper used across frontend
export async function fetchBackendHealth(): Promise<HealthResponse> {
  return apiClient.getHealth({ full: true });
}
