import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";
import { sendAuthenticatedRequest } from "../src/api/client.js";

const store = new Map();
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, String(value)),
  removeItem: (key) => store.delete(key),
};
globalThis.window = { location: { pathname: "/", href: "/" } };

function json(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

beforeEach(() => {
  store.clear();
  store.set("foc_access_token", "old-access");
  store.set("foc_refresh_token", "refresh-1");
  window.location.href = "/";
});

test("an expired access token is refreshed once and the request retried", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options.headers?.Authorization]);
    if (url.endsWith("/users/refresh")) {
      assert.deepEqual(JSON.parse(options.body), { refresh_token: "refresh-1" });
      return json(200, { access_token: "new-access", refresh_token: "refresh-2", user: { id: "u1" } });
    }
    return options.headers.Authorization === "Bearer new-access" ? json(200, { ok: true }) : json(401, {});
  };

  const [first, second] = await Promise.all([
    sendAuthenticatedRequest("/api/v1/orders", { token: "old-access", method: "GET" }),
    sendAuthenticatedRequest("/api/v1/credits/me", { token: "old-access", method: "GET" }),
  ]);

  assert.deepEqual(first, { ok: true });
  assert.deepEqual(second, { ok: true });
  assert.equal(calls.filter(([url]) => url.endsWith("/users/refresh")).length, 1);
  assert.equal(store.get("foc_access_token"), "new-access");
  assert.equal(store.get("foc_refresh_token"), "refresh-2");
});

test("a rejected refresh token ends the session and returns to login", async () => {
  globalThis.fetch = async () => json(401, { detail: "Your session has expired. Please log in again." });

  await assert.rejects(
    sendAuthenticatedRequest("/api/v1/orders", { token: "old-access", method: "GET", errorMessage: "x" }),
    (error) => error.sessionExpired && error.message === "Your session has expired. Please log in again.",
  );
  assert.equal(store.size, 0);
  assert.equal(window.location.href, "/?screen=login&reason=expired");
});

test("a failed refresh because the service is down keeps the session", async () => {
  globalThis.fetch = async (url) => {
    if (url.endsWith("/users/refresh")) throw new TypeError("offline");
    return json(401, {});
  };

  await assert.rejects(
    sendAuthenticatedRequest("/api/v1/orders", { token: "old-access", method: "GET" }),
    (error) => error.status === 0,
  );
  assert.equal(store.get("foc_refresh_token"), "refresh-1");
});

test("other errors are not treated as an expired session", async () => {
  let refreshed = false;
  globalThis.fetch = async (url) => {
    if (url.endsWith("/users/refresh")) refreshed = true;
    return json(403, { detail: "Admin access is required." });
  };

  await assert.rejects(
    sendAuthenticatedRequest("/api/v1/users", { token: "old-access", method: "GET" }),
    (error) => error.status === 403 && error.message === "Admin access is required.",
  );
  assert.equal(refreshed, false);
  assert.equal(store.get("foc_access_token"), "old-access");
});
