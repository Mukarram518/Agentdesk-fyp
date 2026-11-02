/**
 * AgentDesk Business Slug & Validation Utilities.
 * Pure, reusable functions for generating and validating business names and URL slugs.
 * Aligns strictly with FastAPI validation schemas in backend/app/schemas/business.py.
 */

export const SLUG_REGEX = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export interface ValidationResult {
  isValid: boolean;
  error: string | null;
  cleaned?: string;
}

/**
 * Converts a business name into a lowercase, URL-friendly slug.
 * - Trims leading and trailing whitespace.
 * - Strips apostrophes (e.g. "Mukarram's" -> "mukarrams").
 * - Replaces unsupported characters and runs of spaces with a single hyphen.
 * - Prevents leading, trailing, or repeated hyphens.
 * - Returns an empty string if no valid alphanumeric characters exist.
 */
export function generateSlug(text?: string | null): string {
  if (!text || typeof text !== "string") {
    return "";
  }

  return text
    .toLowerCase()
    .trim()
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Functional alias for generateSlug.
 */
export const slugify = generateSlug;

/**
 * Validates a business name for onboarding.
 * - Trims the input before validation.
 * - Requires 2–255 characters after trimming.
 * - Return a clear validation result suitable for displaying an inline form error.
 * - Does not silently truncate input.
 */
export function validateBusinessName(name?: string | null): ValidationResult {
  if (name === undefined || name === null || !name.trim()) {
    return {
      isValid: false,
      error: "Business name cannot be empty.",
    };
  }

  const cleaned = name.trim();

  if (cleaned.length < 2) {
    return {
      isValid: false,
      error: "Business name must be at least 2 characters.",
    };
  }

  if (cleaned.length > 255) {
    return {
      isValid: false,
      error: "Business name cannot exceed 255 characters.",
    };
  }

  return {
    isValid: true,
    error: null,
    cleaned,
  };
}

/**
 * Validates an optional custom business slug.
 * - An empty or whitespace-only slug is allowed because the backend can generate one.
 * - Otherwise trims the input and requires 2–100 characters.
 * - Allows only lowercase ASCII letters, numbers, and single hyphens between alphanumeric segments: ^[a-z0-9]+(?:-[a-z0-9]+)*$
 * - Does not silently convert an explicitly entered invalid slug into a different value.
 */
export function validateBusinessSlug(slug?: string | null): ValidationResult {
  if (slug === undefined || slug === null || !slug.trim()) {
    return {
      isValid: true,
      error: null,
      cleaned: "",
    };
  }

  const cleaned = slug.trim();

  if (cleaned.length < 2) {
    return {
      isValid: false,
      error: "Business slug must be at least 2 characters.",
    };
  }

  if (cleaned.length > 100) {
    return {
      isValid: false,
      error: "Business slug cannot exceed 100 characters.",
    };
  }

  if (!SLUG_REGEX.test(cleaned)) {
    return {
      isValid: false,
      error:
        "Business slug must contain only lowercase alphanumeric characters and hyphens.",
    };
  }

  return {
    isValid: true,
    error: null,
    cleaned,
  };
}
