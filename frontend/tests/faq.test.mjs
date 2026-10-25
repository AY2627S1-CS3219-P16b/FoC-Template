import test from "node:test";
import assert from "node:assert/strict";
import { askFaq } from "../src/api/faq.js";

test("public FAQ requests send only the question and return sources", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, "/api/v1/faq/chat");
      assert.deepEqual(options.headers, { "Content-Type": "application/json" });
      assert.deepEqual(JSON.parse(options.body), { question: "Starting credits?" });
      return new Response(JSON.stringify({ status: "answered", answer: "20 credits.", sources: [] }));
    };
    assert.equal((await askFaq("Starting credits?")).answer, "20 credits.");
  } finally { globalThis.fetch = originalFetch; }
});

test("FAQ errors hide backend details and preserve a safe support reference", async () => {
  const originalFetch = globalThis.fetch;
  try {
    for (const [status, pattern] of [[429, /wait a minute/], [503, /Help is unavailable right now/], [422, /1,500/]]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail: "private API credential details",
        request_id: "12345678-1234-1234-1234-123456789abc" }), { status });
      await assert.rejects(() => askFaq("Help"), (error) => {
        assert.match(error.message, pattern);
        assert.doesNotMatch(error.message, /credential/);
        assert.equal(error.requestId, "12345678-1234-1234-1234-123456789abc");
        return true;
      });
    }
    globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
    await assert.rejects(() => askFaq("Help"), /Check your connection/);
  } finally { globalThis.fetch = originalFetch; }
});

test("malformed successful responses cannot become chat messages", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ answer: "Incomplete" }));
    await assert.rejects(() => askFaq("Help"), /incomplete answer/);
  } finally { globalThis.fetch = originalFetch; }
});
