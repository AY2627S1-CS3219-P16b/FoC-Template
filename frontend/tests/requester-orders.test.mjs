import test from "node:test";
import assert from "node:assert/strict";
import { listRequesterOrders, loadOrders } from "../src/api/orders.js";
import { isActiveOrder, requesterPollDelay } from "../src/utils/requesterOrders.js";

test("request history fetches only the requested server page and view", async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url) => {
    urls.push(new URL(url, "http://localhost"));
    return Response.json({ items: [], page: 3, total: 42, total_pages: 5 });
  };
  try {
    const result = await listRequesterOrders("test-token", { view: "past", page: 3 });
    assert.equal(result.total, 42);
    assert.equal(urls.length, 1);
    assert.equal(urls[0].pathname, "/api/v1/orders/me");
    assert.deepEqual(Object.fromEntries(urls[0].searchParams), { role: "requester", view: "past", page: "3", page_size: "10" });
  } finally { globalThis.fetch = originalFetch; }
});

test("background order refresh excludes both requester and courier history", async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url) => {
    const parsed = new URL(url, "http://localhost");
    urls.push(parsed);
    const page = Number(parsed.searchParams.get("page"));
    const personal = parsed.pathname.endsWith("/me");
    return Response.json({ items: [{ id: personal ? "mine" : "open", created_at: "2026-10-25T08:00:00Z" }], total_pages: personal ? 2 : 1, page });
  };
  try {
    const result = await loadOrders("test-token");
    const personal = urls.filter((url) => url.pathname.endsWith("/me"));
    assert.equal(personal.length, 4);
    assert.ok(personal.every((url) => url.searchParams.get("view") === "active"));
    assert.deepEqual(new Set(personal.map((url) => url.searchParams.get("role"))), new Set(["requester", "courier"]));
    assert.equal(result.length, 2, "duplicate order IDs are still merged");
  } finally { globalThis.fetch = originalFetch; }
});

test("history is not polled and active processing retains fast updates", () => {
  for (const status of ["COMPLETED", "CANCELLED", "EXPIRED", "REJECTED"]) {
    assert.equal(isActiveOrder({ status }), false);
    assert.equal(requesterPollDelay("all", [{ status }]), null);
  }
  for (const status of ["RESERVING", "CANCELLING", "EXPIRING", "COMPLETING"]) {
    assert.equal(isActiveOrder({ status }), true);
    assert.equal(requesterPollDelay("active", [{ status }]), 1000);
    assert.equal(requesterPollDelay("all", [{ status }]), 1000);
    assert.equal(requesterPollDelay("past", [{ status }]), null);
  }
  assert.equal(requesterPollDelay("active", [{ status: "DELIVERED" }]), 5000);
  assert.equal(requesterPollDelay("active", []), 5000);
  assert.equal(requesterPollDelay("past", []), null);
  assert.equal(requesterPollDelay("all", []), null);
});
