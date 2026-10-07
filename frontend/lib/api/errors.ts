/**
 * AgentDesk API Error Hierarchy.
 * Provides distinct, typed error classes for network, HTTP, parse, and timeout failures.
 */

export type ApiErrorCode =
  | "NETWORK_ERROR"
  | "HTTP_ERROR"
  | "PARSE_ERROR"
  | "TIMEOUT_ERROR"
  | "UNKNOWN_ERROR";

export class ApiClientError extends Error {
  readonly code: ApiErrorCode;
  readonly status?: number;
  readonly details?: unknown;

  constructor(
    message: string,
    code: ApiErrorCode = "UNKNOWN_ERROR",
    status?: number,
    details?: unknown
  ) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;

    // Restore prototype chain for instanceof checks
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class ApiHttpError extends ApiClientError {
  readonly statusText: string;
  readonly data?: unknown;

  constructor(status: number, statusText: string, data?: unknown) {
    let message = `Request failed with status ${status} (${statusText})`;
    if (data && typeof data === "object") {
      const payload = data as Record<string, unknown>;
      if (typeof payload.message === "string") {
        message = payload.message;
      } else if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    }

    super(message, "HTTP_ERROR", status, data);
    this.name = "ApiHttpError";
    this.statusText = statusText;
    this.data = data;
    Object.setPrototypeOf(this, ApiHttpError.prototype);
  }
}

export class ApiNetworkError extends ApiClientError {
  readonly originalError?: unknown;

  constructor(message = "Network connection failed. Please check your connection.", originalError?: unknown) {
    super(message, "NETWORK_ERROR", undefined, originalError);
    this.name = "ApiNetworkError";
    this.originalError = originalError;
    Object.setPrototypeOf(this, ApiNetworkError.prototype);
  }
}

export class ApiParseError extends ApiClientError {
  readonly rawText?: string;

  constructor(message = "Failed to parse API response as JSON.", rawText?: string) {
    super(message, "PARSE_ERROR", undefined, { rawText });
    this.name = "ApiParseError";
    this.rawText = rawText;
    Object.setPrototypeOf(this, ApiParseError.prototype);
  }
}

export class ApiTimeoutError extends ApiClientError {
  readonly timeoutMs: number;

  constructor(timeoutMs: number) {
    super(`Request timed out after ${timeoutMs}ms.`, "TIMEOUT_ERROR");
    this.name = "ApiTimeoutError";
    this.timeoutMs = timeoutMs;
    Object.setPrototypeOf(this, ApiTimeoutError.prototype);
  }
}

export function isApiClientError(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError;
}
