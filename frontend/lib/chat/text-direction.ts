/**
 * Text direction detection utility for AgentDesk (Urdu RTL / English LTR).
 */

import type { TextDirection } from "@/types/chat";

// Unicode ranges covering Arabic, Urdu, Persian, and related RTL presentation forms
const RTL_REGEX = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/g;
const LTR_REGEX = /[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF]/g;

// Strong directional character testers for first-strong detection
const RTL_CHAR_TEST = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
const LTR_CHAR_TEST = /[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF]/;

/**
 * Detects whether the given text should be rendered RTL (e.g. Urdu, Arabic) or LTR (English).
 *
 * Rules:
 * 1. Empty, whitespace-only, or non-string input defaults to "ltr".
 * 2. Scans for first strong directional character.
 * 3. Counts RTL vs LTR characters: if RTL characters strictly exceed LTR characters, returns "rtl".
 *    (This handles Urdu queries that open with English brand names like "AgentDesk کے کیا فیچرز ہیں؟").
 * 4. If first strong directional character is RTL, returns "rtl".
 * 5. Otherwise defaults to "ltr".
 */
export function detectTextDirection(text: unknown): TextDirection {
  if (typeof text !== "string") {
    return "ltr";
  }

  const trimmed = text.trim();
  if (!trimmed) {
    return "ltr";
  }

  // Count directional characters
  const rtlMatches = trimmed.match(RTL_REGEX);
  const ltrMatches = trimmed.match(LTR_REGEX);

  const rtlCount = rtlMatches ? rtlMatches.length : 0;
  const ltrCount = ltrMatches ? ltrMatches.length : 0;

  // Rule: If RTL characters outnumber LTR characters, it is primarily RTL
  if (rtlCount > ltrCount) {
    return "rtl";
  }

  // Find the first strongly directional character
  for (const char of trimmed) {
    if (RTL_CHAR_TEST.test(char)) {
      return "rtl";
    }
    if (LTR_CHAR_TEST.test(char)) {
      return "ltr";
    }
  }

  return "ltr";
}
