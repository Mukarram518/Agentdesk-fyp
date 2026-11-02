import test, { describe } from "node:test";
import assert from "node:assert/strict";
import {
  generateSlug,
  slugify,
  validateBusinessName,
  validateBusinessSlug,
  SLUG_REGEX,
  type ValidationResult,
} from "../lib/business/slug";

describe("Business Slug Generation", () => {
  test("converts standard business names to lowercase hyphenated slugs", () => {
    assert.strictEqual(generateSlug("Acme Dental Care"), "acme-dental-care");
    assert.strictEqual(generateSlug("AgentDesk FYP"), "agentdesk-fyp");
    assert.strictEqual(generateSlug("Alpha 360 AI Lab"), "alpha-360-ai-lab");
  });

  test("slugify alias behaves identically to generateSlug", () => {
    assert.strictEqual(slugify("Acme Dental Care"), "acme-dental-care");
    assert.strictEqual(slugify("  Alpha Corp  "), "alpha-corp");
  });

  test("trims leading and trailing whitespace", () => {
    assert.strictEqual(generateSlug("   Acme Dental   "), "acme-dental");
    assert.strictEqual(generateSlug("\tMukarram Tech\n"), "mukarram-tech");
  });

  test("collapses runs of spaces and punctuation into a single hyphen", () => {
    assert.strictEqual(
      generateSlug("Acme   ---   Dental...Care!!"),
      "acme-dental-care"
    );
    assert.strictEqual(
      generateSlug("Health & Wellness + Fitness"),
      "health-wellness-fitness"
    );
  });

  test("removes straight and curly apostrophes cleanly without inserting hyphens", () => {
    assert.strictEqual(generateSlug("Mukarram's Bakery"), "mukarrams-bakery");
    assert.strictEqual(
      generateSlug("O’Connor’s Auto Repair"),
      "oconnors-auto-repair"
    );
  });

  test("prevents leading, trailing, or repeated hyphens in output", () => {
    assert.strictEqual(generateSlug("---Leading and Trailing---"), "leading-and-trailing");
    assert.strictEqual(generateSlug("---"), "");
    assert.strictEqual(generateSlug("-a-b-c-"), "a-b-c");
  });

  test("returns empty string when input is empty or contains only whitespace", () => {
    assert.strictEqual(generateSlug(""), "");
    assert.strictEqual(generateSlug("   "), "");
    assert.strictEqual(generateSlug("\n\t  "), "");
  });

  test("returns empty string when input contains only unsupported characters", () => {
    assert.strictEqual(generateSlug("!@#$%^&*()_+="), "");
    assert.strictEqual(generateSlug("??? /// ..."), "");
  });

  test("handles null, undefined, or non-string inputs safely", () => {
    assert.strictEqual(generateSlug(null), "");
    assert.strictEqual(generateSlug(undefined), "");
    // @ts-expect-error Testing runtime resilience
    assert.strictEqual(generateSlug(12345), "");
  });

  test("preserves numbers and alphanumeric segments", () => {
    assert.strictEqual(
      generateSlug("Studio 54 Design 2026"),
      "studio-54-design-2026"
    );
    assert.strictEqual(generateSlug("99 Cents Store"), "99-cents-store");
  });
});

describe("Business Name Validation", () => {
  test("rejects empty, whitespace-only, null, or undefined names", () => {
    const emptyRes = validateBusinessName("");
    assert.strictEqual(emptyRes.isValid, false);
    assert.strictEqual(emptyRes.error, "Business name cannot be empty.");

    const whitespaceRes = validateBusinessName("     ");
    assert.strictEqual(whitespaceRes.isValid, false);
    assert.strictEqual(whitespaceRes.error, "Business name cannot be empty.");

    const nullRes = validateBusinessName(null);
    assert.strictEqual(nullRes.isValid, false);
    assert.strictEqual(nullRes.error, "Business name cannot be empty.");

    const undefRes = validateBusinessName(undefined);
    assert.strictEqual(undefRes.isValid, false);
    assert.strictEqual(undefRes.error, "Business name cannot be empty.");
  });

  test("rejects 1-character name after trimming (below min length 2)", () => {
    const res1 = validateBusinessName("A");
    assert.strictEqual(res1.isValid, false);
    assert.strictEqual(res1.error, "Business name must be at least 2 characters.");

    const res2 = validateBusinessName("  A  ");
    assert.strictEqual(res2.isValid, false);
    assert.strictEqual(res2.error, "Business name must be at least 2 characters.");
  });

  test("accepts minimum boundary of 2 characters", () => {
    const res = validateBusinessName("AB");
    assert.strictEqual(res.isValid, true);
    assert.strictEqual(res.error, null);
    assert.strictEqual(res.cleaned, "AB");

    const resWithSpaces = validateBusinessName("  AB  ");
    assert.strictEqual(resWithSpaces.isValid, true);
    assert.strictEqual(resWithSpaces.error, null);
    assert.strictEqual(resWithSpaces.cleaned, "AB");
  });

  test("accepts maximum boundary of 255 characters", () => {
    const name255 = "A".repeat(255);
    const res = validateBusinessName(name255);
    assert.strictEqual(res.isValid, true);
    assert.strictEqual(res.error, null);
    assert.strictEqual(res.cleaned, name255);
  });

  test("rejects 256 characters (above max length 255)", () => {
    const name256 = "A".repeat(256);
    const res = validateBusinessName(name256);
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(res.error, "Business name cannot exceed 255 characters.");
  });

  test("does not silently truncate input or return modified name when invalid", () => {
    const longName = "B".repeat(300);
    const res = validateBusinessName(longName);
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(res.error, "Business name cannot exceed 255 characters.");
    assert.strictEqual(res.cleaned, undefined);
  });

  test("returns expected ValidationResult structure on valid name", () => {
    const res: ValidationResult = validateBusinessName("  Acme Dental Care  ");
    assert.strictEqual(res.isValid, true);
    assert.strictEqual(res.error, null);
    assert.strictEqual(res.cleaned, "Acme Dental Care");
  });
});

describe("Business Slug Validation", () => {
  test("allows empty or whitespace-only optional slug", () => {
    const undefRes = validateBusinessSlug(undefined);
    assert.strictEqual(undefRes.isValid, true);
    assert.strictEqual(undefRes.error, null);
    assert.strictEqual(undefRes.cleaned, "");

    const nullRes = validateBusinessSlug(null);
    assert.strictEqual(nullRes.isValid, true);
    assert.strictEqual(nullRes.error, null);
    assert.strictEqual(nullRes.cleaned, "");

    const emptyRes = validateBusinessSlug("");
    assert.strictEqual(emptyRes.isValid, true);
    assert.strictEqual(emptyRes.error, null);
    assert.strictEqual(emptyRes.cleaned, "");

    const spacesRes = validateBusinessSlug("    ");
    assert.strictEqual(spacesRes.isValid, true);
    assert.strictEqual(spacesRes.error, null);
    assert.strictEqual(spacesRes.cleaned, "");
  });

  test("accepts valid lowercase alphanumeric slugs with hyphens", () => {
    const validSlugs = [
      "acme",
      "acme-dental",
      "acme-dental-care",
      "alpha-360-lab-2026",
      "a-b-c-d",
      "123-clinic",
    ];

    for (const slug of validSlugs) {
      const res = validateBusinessSlug(slug);
      assert.strictEqual(res.isValid, true, `Slug '${slug}' should be valid`);
      assert.strictEqual(res.error, null);
      assert.strictEqual(res.cleaned, slug);
    }
  });

  test("accepts minimum boundary of 2 characters", () => {
    const res = validateBusinessSlug("ab");
    assert.strictEqual(res.isValid, true);
    assert.strictEqual(res.error, null);
    assert.strictEqual(res.cleaned, "ab");

    const resWithPadding = validateBusinessSlug("  1a  ");
    assert.strictEqual(resWithPadding.isValid, true);
    assert.strictEqual(resWithPadding.error, null);
    assert.strictEqual(resWithPadding.cleaned, "1a");
  });

  test("accepts maximum boundary of 100 characters", () => {
    const slug100 = "a".repeat(100);
    const res = validateBusinessSlug(slug100);
    assert.strictEqual(res.isValid, true);
    assert.strictEqual(res.error, null);
    assert.strictEqual(res.cleaned, slug100);
  });

  test("rejects slug shorter than 2 characters", () => {
    const res = validateBusinessSlug("a");
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(res.error, "Business slug must be at least 2 characters.");

    const resPadded = validateBusinessSlug("  z  ");
    assert.strictEqual(resPadded.isValid, false);
    assert.strictEqual(resPadded.error, "Business slug must be at least 2 characters.");
  });

  test("rejects slug longer than 100 characters", () => {
    const slug101 = "a".repeat(101);
    const res = validateBusinessSlug(slug101);
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(res.error, "Business slug cannot exceed 100 characters.");
  });

  test("rejects uppercase letters", () => {
    const res = validateBusinessSlug("Acme-Dental");
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(
      res.error,
      "Business slug must contain only lowercase alphanumeric characters and hyphens."
    );
  });

  test("rejects underscores", () => {
    const res = validateBusinessSlug("acme_dental");
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(
      res.error,
      "Business slug must contain only lowercase alphanumeric characters and hyphens."
    );
  });

  test("rejects internal spaces", () => {
    const res = validateBusinessSlug("acme dental");
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(
      res.error,
      "Business slug must contain only lowercase alphanumeric characters and hyphens."
    );
  });

  test("rejects consecutive hyphens", () => {
    const res = validateBusinessSlug("acme--dental");
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(
      res.error,
      "Business slug must contain only lowercase alphanumeric characters and hyphens."
    );
  });

  test("rejects leading hyphen", () => {
    const res = validateBusinessSlug("-acme-dental");
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(
      res.error,
      "Business slug must contain only lowercase alphanumeric characters and hyphens."
    );
  });

  test("rejects trailing hyphen", () => {
    const res = validateBusinessSlug("acme-dental-");
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(
      res.error,
      "Business slug must contain only lowercase alphanumeric characters and hyphens."
    );
  });

  test("rejects special characters and punctuation", () => {
    const invalidList = [
      "acme.dental",
      "acme@dental",
      "acme#dental",
      "acme!dental",
      "acme/dental",
    ];

    for (const slug of invalidList) {
      const res = validateBusinessSlug(slug);
      assert.strictEqual(res.isValid, false, `Slug '${slug}' should be rejected`);
      assert.strictEqual(
        res.error,
        "Business slug must contain only lowercase alphanumeric characters and hyphens."
      );
    }
  });

  test("does not silently convert an invalid slug into a different value", () => {
    const invalidSlug = "Invalid_Slug-123!";
    const res = validateBusinessSlug(invalidSlug);
    assert.strictEqual(res.isValid, false);
    assert.strictEqual(res.cleaned, undefined);
  });

  test("SLUG_REGEX matches only strict lowercase alphanumeric hyphens format", () => {
    assert.ok(SLUG_REGEX.test("alpha-beta"));
    assert.ok(SLUG_REGEX.test("a1-b2-c3"));
    assert.strictEqual(SLUG_REGEX.test("-leading"), false);
    assert.strictEqual(SLUG_REGEX.test("trailing-"), false);
    assert.strictEqual(SLUG_REGEX.test("double--hyphen"), false);
    assert.strictEqual(SLUG_REGEX.test("UPPERCASE"), false);
  });
});
