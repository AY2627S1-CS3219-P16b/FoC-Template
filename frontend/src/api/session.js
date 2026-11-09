// Stores the login session and renews the access token with the refresh token.

const API_BASE_URL = import.meta.env?.VITE_USER_API_URL || "";

export const ACCESS_TOKEN_KEY = "foc_access_token";
export const REFRESH_TOKEN_KEY = "foc_refresh_token";
export const USER_KEY = "foc_user";
export const SESSION_EXPIRED_MESSAGE = "Your session has expired. Please log in again.";

function storage() {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

export function getAccessToken() {
  return storage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
}

export function getRefreshToken() {
  return storage()?.getItem(REFRESH_TOKEN_KEY) ?? null;
}

/** Saves a login or refresh response. */
export function saveSession(session) {
  const store = storage();
  if (!store) return;
  store.setItem(ACCESS_TOKEN_KEY, session.access_token);
  if (session.refresh_token) store.setItem(REFRESH_TOKEN_KEY, session.refresh_token);
  if (session.user) store.setItem(USER_KEY, JSON.stringify(session.user));
}

export function clearSession() {
  const store = storage();
  if (!store) return;
  store.removeItem(ACCESS_TOKEN_KEY);
  store.removeItem(REFRESH_TOKEN_KEY);
  store.removeItem(USER_KEY);
}

let refreshInFlight = null;

/**
 * Exchanges the refresh token for a new access token and returns it, or null
 * when the session cannot be renewed. Concurrent callers share one request,
 * because each refresh token can only be used once.
 */
export function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = requestRefresh().finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

async function requestRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/users/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    // Offline or User Service down: keep the session so a later request can retry.
    const error = new Error("The service is unavailable. Please try again.");
    error.status = 0;
    throw error;
  }

  if (!response.ok) {
    // Another browser tab may have rotated the token while this request ran.
    const latest = getRefreshToken();
    if (latest && latest !== refreshToken) return getAccessToken();
    if (response.status === 401) clearSession();
    return null;
  }

  const session = await response.json();
  saveSession(session);
  return session.access_token;
}

/** Revokes the refresh token on the server and clears the stored session. */
export function logoutSession() {
  const refreshToken = getRefreshToken();
  clearSession();
  if (!refreshToken) return Promise.resolve();
  return fetch(`${API_BASE_URL}/api/v1/users/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    keepalive: true,
  }).then(() => undefined, () => undefined);
}

/** Clears the session and returns to the login screen with an explanation. */
export function endExpiredSession() {
  clearSession();
  if (typeof window !== "undefined" && window.location) {
    window.location.href = `${window.location.pathname}?screen=login&reason=expired`;
  }
}
