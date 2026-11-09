import test, { describe } from "node:test";
import assert from "node:assert/strict";
import { detectTextDirection } from "../lib/chat/text-direction";

describe("Text Direction Detection (Urdu RTL / English LTR)", () => {
  test("detects pure Urdu text as RTL", () => {
    assert.strictEqual(detectTextDirection("کیا آپ کے پاس ڈاکٹر دستیاب ہیں؟"), "rtl");
    assert.strictEqual(detectTextDirection("میرا نام احمد ہے اور مجھے اپوائنٹمنٹ چاہیے"), "rtl");
    assert.strictEqual(detectTextDirection("سلام! آپ کی کیا سروسز ہیں؟"), "rtl");
  });

  test("detects pure English text as LTR", () => {
    assert.strictEqual(detectTextDirection("What are your business hours?"), "ltr");
    assert.strictEqual(detectTextDirection("Can I book an appointment for tomorrow?"), "ltr");
    assert.strictEqual(detectTextDirection("Hello, I need customer support."), "ltr");
  });

  test("detects mixed text starting with English brand name but mostly Urdu as RTL", () => {
    assert.strictEqual(detectTextDirection("AgentDesk کے کیا فیچرز ہیں؟"), "rtl");
    assert.strictEqual(detectTextDirection("AgentDesk میں نیا اکاؤنٹ کیسے بنائیں؟"), "rtl");
  });

  test("detects mixed text starting with English and mostly English as LTR", () => {
    assert.strictEqual(detectTextDirection("Welcome to AgentDesk شکریہ"), "ltr");
    assert.strictEqual(detectTextDirection("Your appointment is confirmed شکریہ"), "ltr");
  });

  test("detects mixed text starting with Urdu as RTL", () => {
    assert.strictEqual(detectTextDirection("آپ کا AgentDesk اکاؤنٹ بن چکا ہے"), "rtl");
    assert.strictEqual(detectTextDirection("شکریہ! Please visit again."), "rtl");
  });

  test("handles numbers and punctuation preceding Urdu text as RTL", () => {
    assert.strictEqual(detectTextDirection("123. کیا حال ہے؟"), "rtl");
    assert.strictEqual(detectTextDirection("!@# کیا آپ مدد کر سکتے ہیں؟"), "rtl");
    assert.strictEqual(detectTextDirection("   1. اپوائنٹمنٹ بکنگ"), "rtl");
  });

  test("handles numbers and punctuation preceding English text as LTR", () => {
    assert.strictEqual(detectTextDirection("123. Hello world!"), "ltr");
    assert.strictEqual(detectTextDirection("!@# How can I help?"), "ltr");
    assert.strictEqual(detectTextDirection("   1. Appointment booking"), "ltr");
  });

  test("defaults empty, whitespace, and non-string inputs to LTR", () => {
    assert.strictEqual(detectTextDirection(""), "ltr");
    assert.strictEqual(detectTextDirection("   "), "ltr");
    assert.strictEqual(detectTextDirection("\t\n"), "ltr");
    assert.strictEqual(detectTextDirection(null), "ltr");
    assert.strictEqual(detectTextDirection(undefined), "ltr");
    assert.strictEqual(detectTextDirection(12345), "ltr");
  });

  test("defaults purely numeric or punctuation text to LTR", () => {
    assert.strictEqual(detectTextDirection("1234567890"), "ltr");
    assert.strictEqual(detectTextDirection("!@#$%^&*()_+"), "ltr");
    assert.strictEqual(detectTextDirection("--- ... ///"), "ltr");
  });
});
